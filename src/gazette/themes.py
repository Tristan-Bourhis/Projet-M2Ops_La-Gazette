"""Thèmes du jour : regroupement BERTopic des articles des dernières 24 h, nommage, run tracé."""

import hashlib
import logging
import os
import statistics
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from gazette.embed import (
    WINDOW,
    Encoder,
    MemoryEmbeddingStore,
    article_text,
    embed_articles,
    load_encoder,
    window_articles,
)

logger = logging.getLogger("gazette.themes")
CONFIG = Path("config/clustering.yaml")
NOISE = -1  # étiquette HDBSCAN des articles rattachés à aucun thème

# (textes, vecteurs, config) -> (étiquette et probabilité par article, mots-clés par thème)
Clusterer = Callable[[list[str], list[list[float]], dict], tuple[list, list, dict]]


class MemoryThemeStore(MemoryEmbeddingStore):
    """Pour les tests : même interface que PostgresThemeStore."""

    def __init__(self, articles: list[dict] = ()):
        super().__init__(articles)
        self.runs: dict[int, dict] = {}
        self.themes: list[dict] = []
        self.affectations: list[dict] = []

    def start_run(self, run):
        run_id = len(self.runs) + 1
        self.runs[run_id] = dict(run, termine_le=None, metriques=None)
        return run_id

    def finish_run(self, run_id, themes, affectations, metriques, at):
        for i, theme in enumerate(themes):
            self.themes.append(dict(theme, id=(run_id, i), run_id=run_id))
        for row in affectations:
            theme = row["theme"]
            self.affectations.append(
                dict(row, run_id=run_id, theme_id=None if theme is None else (run_id, theme))
            )
        self.runs[run_id].update(termine_le=at, metriques=metriques)


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def model_key(config: dict) -> str:
    """Identifiant tracé du modèle : nom@révision (aussi la clé du cache d'embeddings)."""
    return f"{config['modele']['nom']}@{config['modele']['revision']}"


def input_hash(articles: list[dict]) -> str:
    """Empreinte des données d'entrée : mêmes articles = même hash, quel que soit l'ordre."""
    return hashlib.sha256("\n".join(sorted(a["id"] for a in articles)).encode()).hexdigest()


def bertopic_cluster(textes, vecteurs, config):
    """UMAP (cosinus, graine fixée) -> HDBSCAN -> mots-clés c-TF-IDF."""
    # Imports ici : bibliothèques lourdes, inutiles aux tests qui passent un faux regroupement.
    import numpy as np
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    model = BERTopic(
        umap_model=UMAP(**config["umap"], random_state=config["graine"]),
        hdbscan_model=HDBSCAN(**config["hdbscan"], prediction_data=True),
        vectorizer_model=CountVectorizer(
            stop_words=config["mots_cles"]["mots_vides"], token_pattern=config["mots_cles"]["motif"]
        ),
        language="multilingual",  # sinon BERTopic retire tout caractère hors A-Z (accents)
        top_n_words=config["mots_cles"]["nombre"],
    )
    labels, probabilities = model.fit_transform(textes, embeddings=np.array(vecteurs))
    keywords = {
        label: [word for word, _ in model.get_topic(label)] for label in set(labels) - {NOISE}
    }
    return list(labels), [float(p) for p in probabilities], keywords


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norms = sum(x * x for x in a) ** 0.5 * sum(y * y for y in b) ** 0.5
    return dot / norms if norms else 0.0


def central_title(members: list[int], articles: list[dict], vecteurs: list[list[float]]) -> str:
    """Nom lisible d'un thème : le titre de l'article le plus proche du centre du groupe."""
    center = [
        sum(values) / len(members) for values in zip(*(vecteurs[i] for i in members), strict=True)
    ]
    best = max(members, key=lambda i: _cosine(vecteurs[i], center))
    return articles[best]["titre"]


def metrics(labels: list[int], vecteurs: list[list[float]]) -> dict:
    """Métriques du TD : thèmes, taille médiane, part de bruit, silhouette (calculée sans bruit)."""
    sizes = [labels.count(label) for label in set(labels) - {NOISE}]
    silhouette = None
    if len(sizes) > 1:
        from sklearn.metrics import silhouette_score

        kept = [i for i, label in enumerate(labels) if label != NOISE]
        silhouette = round(
            float(
                silhouette_score(
                    [vecteurs[i] for i in kept], [labels[i] for i in kept], metric="cosine"
                )
            ),
            3,
        )
    return {
        "themes": len(sizes),
        "taille_mediane": statistics.median(sizes) if sizes else 0,
        "part_bruit": round(labels.count(NOISE) / len(labels), 3) if labels else 0.0,
        "silhouette": silhouette,
    }


def run_themes(
    store,
    encoder: Encoder,
    config: dict,
    now: datetime,
    cluster: Clusterer = bertopic_cluster,
) -> dict:
    """Un run complet et tracé : fenêtre -> embeddings -> regroupement -> nommage -> stockage.

    Le run est enregistré avant le calcul : s'il plante, il reste en base sans termine_le."""
    articles = window_articles(store, now)
    modele = model_key(config)
    run_id = store.start_run(
        {
            "lance_le": now,
            "fenetre_debut": now - WINDOW,
            "fenetre_fin": now,
            "nb_articles": len(articles),
            "hash_entree": input_hash(articles),
            "modele": modele,
            "parametres": config,
        }
    )
    minimum = config["umap"]["n_neighbors"] + 1
    if len(articles) < minimum:
        raise ValueError(f"{len(articles)} articles sur 24 h : il en faut au moins {minimum}.")

    vecteurs = list(embed_articles(store, articles, modele, encoder, now).values())
    textes = [article_text(a) for a in articles]
    labels, probabilities, keywords = cluster(textes, vecteurs, config)

    groups = sorted(set(labels) - {NOISE}, key=lambda label: -labels.count(label))
    index = {label: position for position, label in enumerate(groups)}
    themes = []
    for label in groups:
        members = [i for i, value in enumerate(labels) if value == label]
        themes.append(
            {
                "nom": central_title(members, articles, vecteurs),
                "mots_cles": keywords[label],
                "taille": len(members),
            }
        )
    affectations = [
        {
            "article_id": article["id"],
            "theme": None if label == NOISE else index[label],
            "probabilite": None if label == NOISE else round(probability, 3),
        }
        for article, label, probability in zip(articles, labels, probabilities, strict=True)
    ]
    result = metrics(labels, vecteurs)
    # Heure réelle de fin (now = début du run, il fixe la fenêtre) : la durée reste lisible.
    store.finish_run(run_id, themes, affectations, result, datetime.now(UTC))
    logger.info("Run %d : %d articles, métriques %s", run_id, len(articles), result)
    return {"run_id": run_id, "nb_articles": len(articles), "metriques": result, "themes": themes}


def themes_markdown(result: dict) -> str:
    """Résumé lisible d'un run : publié en artefact Prefect (onglet Artifacts)."""
    m = result["metriques"]
    lines = [
        f"# Thèmes du jour — run {result['run_id']}",
        "",
        f"{result['nb_articles']} articles publiés dans les dernières 24 h ; {m['themes']} thèmes,"
        f" taille médiane {m['taille_mediane']}, bruit {m['part_bruit']:.0%},"
        f" silhouette {m['silhouette']}.",
        "",
        "| Taille | Mots-clés | Titre le plus central |",
        "|---|---|---|",
    ]
    lines += [
        f"| {t['taille']} | {', '.join(t['mots_cles'])} | {t['nom']} |" for t in result["themes"]
    ]
    return "\n".join(lines) + "\n"


def run_daily_themes(config_path: Path = CONFIG) -> dict:
    """Run du pipeline : lit articles_propres et écrit les tables du TD 5 (DATABASE_URL requis)."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL non défini : les thèmes se calculent sur articles_propres."
        )
    from gazette.db import PostgresThemeStore, connect, migrate

    config = load_config(config_path)
    encoder = load_encoder(config["modele"]["nom"], config["modele"]["revision"])
    with connect(database_url) as conn:
        migrate(conn)
        return run_themes(PostgresThemeStore(conn), encoder, config, datetime.now(UTC))
