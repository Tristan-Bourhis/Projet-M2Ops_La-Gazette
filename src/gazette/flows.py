"""Orchestration Prefect : collecte et nettoyage toutes les 30 min ; thèmes du jour à 6 h 30."""

import logging
from pathlib import Path

from prefect import flow, get_run_logger, serve, task
from prefect.artifacts import create_markdown_artifact, create_table_artifact
from prefect.schedules import Cron

from gazette.clean import run_cleaning
from gazette.collect import run_collection
from gazette.themes import run_daily_themes, themes_markdown

INTERVAL_SECONDS = 30 * 60
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("gazette").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)


@task(name="nettoyage-et-controles")
def nettoyage(bruts: str, rapports: str, sources: str) -> dict:
    """Après chaque collecte : articles_propres, rejets, rapport, contrôles, alerte."""
    result = run_cleaning(Path(bruts), Path(rapports), Path(sources))
    # Chiffres publiés dans l'orchestrateur : onglet « Artifacts » du run.
    create_markdown_artifact(
        key="rapport-qualite", markdown=result["rapport_markdown"], description="Rapport du jour"
    )
    create_table_artifact(
        key="controles-qualite", table=result["controles"], description="Contrôles du passage"
    )
    create_table_artifact(
        key="metriques-qualite",
        table=[{"metrique": k, "valeur": v} for k, v in result["metriques"].items()],
        description="Métriques du passage",
    )
    return result


# Pas de retries : un échec compterait deux fois ; le run suivant (30 min) sert de reprise.
@flow(name="collecte")
def collecte(
    sources: str = "sources.csv",
    output: str = "/data/articles_bruts",
    rapports: str = "/data/rapports",
) -> dict:
    summary = run_collection(Path(sources), Path(output))
    get_run_logger().info("Bilan de la collecte : %s", summary)
    # Le nettoyage tourne même si une source a échoué : les autres articles comptent.
    cleaning = nettoyage(output, rapports, sources)
    get_run_logger().info(
        "Bilan du nettoyage : %s",
        {k: cleaning[k] for k in ("entres", "gardes", "rejetes", "par_regle")},
    )
    if not summary["sources"] and not summary["en_sommeil"]:
        raise RuntimeError("Aucune source active : vérifier sources.csv.")
    if summary["sources"] and not summary["ok"]:
        raise RuntimeError(
            "Aucune source n'a répondu (réseau de la machine ?) : run marqué en échec."
        )
    if summary["en_sommeil"]:
        # Run en rouge tant qu'une source dort : l'alerte reste visible dans Prefect
        # jusqu'à la réparation (corriger l'URL dans sources.csv).
        raise RuntimeError(
            f"Source(s) en sommeil après 3 échecs : {', '.join(summary['en_sommeil'])}."
            " Vérifier l'URL dans sources.csv."
        )
    failed = [check["id"] for check in cleaning["controles"] if not check["ok"]]
    if failed:
        raise RuntimeError(f"Contrôle(s) qualité en échec : {', '.join(failed)}.")
    return summary | {"nettoyage": {k: cleaning[k] for k in ("entres", "gardes", "rejetes")}}


@task(name="regroupement-thematique")
def regroupement(config: str) -> dict:
    """Embeddings, BERTopic, nommage ; le run est tracé dans la table runs."""
    result = run_daily_themes(Path(config))
    create_markdown_artifact(
        key="themes-du-jour", markdown=themes_markdown(result), description="Thèmes du jour"
    )
    create_table_artifact(
        key="metriques-themes",
        table=[{"metrique": k, "valeur": v} for k, v in result["metriques"].items()],
        description=f"Métriques du run {result['run_id']}",
    )
    return result


@flow(name="themes-du-jour")
def themes_du_jour(
    sources: str = "sources.csv",
    output: str = "/data/articles_bruts",
    rapports: str = "/data/rapports",
    config: str = "config/clustering.yaml",
) -> dict:
    # Nettoyage d'abord (il ne traite que les nouveaux bruts) : on regroupe des données à jour.
    nettoyage(output, rapports, sources)
    result = regroupement(config)
    get_run_logger().info(
        "Run %s : %s articles, %s", result["run_id"], result["nb_articles"], result["metriques"]
    )
    return {k: result[k] for k in ("run_id", "nb_articles", "metriques")}


if __name__ == "__main__":
    serve(
        collecte.to_deployment(name="collecte-toutes-les-30-min", interval=INTERVAL_SECONDS),
        # Une fois par jour : « thèmes du jour » = un seul run, prêt pour la publication de 7 h.
        themes_du_jour.to_deployment(
            name="themes-6h30", schedule=Cron("30 6 * * *", timezone="Europe/Paris")
        ),
    )
