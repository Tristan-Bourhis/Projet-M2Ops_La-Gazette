"""Orchestration Prefect : collecte, puis nettoyage et contrôles, toutes les 30 minutes."""

import logging
from pathlib import Path

from prefect import flow, get_run_logger, task
from prefect.artifacts import create_markdown_artifact, create_table_artifact

from gazette.clean import run_cleaning
from gazette.collect import run_collection

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


if __name__ == "__main__":
    collecte.serve(name="collecte-toutes-les-30-min", interval=INTERVAL_SECONDS)
