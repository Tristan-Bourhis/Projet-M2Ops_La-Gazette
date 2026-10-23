"""Embeddings : articles propres des dernières 24 h -> vecteurs, en cache par (article, modèle)."""

import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Protocol

logger = logging.getLogger("gazette.embed")
WINDOW = timedelta(hours=24)

# Texte -> vecteurs : le vrai modèle en production, un faux dans les tests (pas de téléchargement).
Encoder = Callable[[list[str]], Sequence[Sequence[float]]]


class EmbeddingStore(Protocol):
    def window_articles(self, start: datetime, end: datetime) -> list[dict]: ...
    def cached_embeddings(self, ids: list[str], modele: str) -> dict[str, list[float]]: ...
    def save_embeddings(self, vectors: dict[str, list[float]], modele: str, at: datetime): ...


class MemoryEmbeddingStore:
    """Pour les tests : même interface que PostgresThemeStore."""

    def __init__(self, articles: list[dict] = ()):
        self.articles = list(articles)
        self.vectors: dict[tuple[str, str], list[float]] = {}

    def window_articles(self, start, end):
        rows = [a for a in self.articles if start < a["publie_le"] <= end]
        return sorted(rows, key=lambda a: (a["publie_le"], a["id"]))

    def cached_embeddings(self, ids, modele):
        return {i: self.vectors[(i, modele)] for i in ids if (i, modele) in self.vectors}

    def save_embeddings(self, vectors, modele, at):
        for article_id, vector in vectors.items():
            self.vectors[(article_id, modele)] = list(vector)


def article_text(article: dict) -> str:
    """Ce que le modèle lit : le titre, puis l'extrait (contexte : lieu, acteurs, sujet)."""
    return f"{article['titre']}. {article['extrait']}" if article["extrait"] else article["titre"]


def window_articles(store: EmbeddingStore, now: datetime) -> list[dict]:
    """Articles propres publiés dans les dernières 24 h : la fenêtre d'un run."""
    return store.window_articles(now - WINDOW, now)


def embed_articles(
    store: EmbeddingStore, articles: list[dict], modele: str, encoder: Encoder, now: datetime
) -> dict[str, list[float]]:
    """Vecteur de chaque article, dans l'ordre des articles ; seuls les absents du cache sont
    calculés puis enregistrés."""
    ids = [a["id"] for a in articles]
    vectors = store.cached_embeddings(ids, modele)
    missing = [a for a in articles if a["id"] not in vectors]
    if missing:
        computed = encoder([article_text(a) for a in missing])
        new = {a["id"]: [float(x) for x in v] for a, v in zip(missing, computed, strict=True)}
        store.save_embeddings(new, modele, now)
        vectors |= new
    logger.info(
        "Embeddings : %d articles, %d déjà en cache, %d calculés (%s)",
        len(ids),
        len(ids) - len(missing),
        len(missing),
        modele,
    )
    return {i: vectors[i] for i in ids}


def load_encoder(name: str, revision: str) -> Encoder:
    """Le modèle sentence-transformers, à une révision figée, sur CPU, vecteurs normalisés."""
    # Import ici : bibliothèque lourde, inutile aux tests qui passent un faux encodeur.
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(name, revision=revision, device="cpu")
    return lambda texts: model.encode(texts, normalize_embeddings=True).tolist()
