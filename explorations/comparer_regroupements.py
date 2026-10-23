"""TD 5, reprise : comparer k-means, HDBSCAN et BERTopic sur les articles des dernières 24 h.

Script d'exploration (hors pipeline) : il sert à choisir l'algorithme, pas à produire les thèmes.
Lancer depuis la racine du dépôt, Postgres exposé sur 127.0.0.1:5433 :

    .venv/bin/python explorations/comparer_regroupements.py

Sortie : console + explorations/sorties/comparaison-AAAA-MM-JJ.md
"""

import os
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import psycopg
from bertopic import BERTopic
from hdbscan import HDBSCAN as BertopicHDBSCAN
from psycopg.rows import dict_row
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import silhouette_score
from umap import UMAP

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://gazette:gazette-local-only@127.0.0.1:5433/gazette"
)
MODELE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
GRAINE = 42
K = 15  # k-means : nombre de groupes imposé
TAILLE_MIN = 5  # HDBSCAN et BERTopic : taille minimale d'un thème
SORTIES = Path(__file__).parent / "sorties"

# Mots vides français : sans eux, les mots-clés seraient « de, la, le ».
MOTS_VIDES = """au aux avec ce ces cet cette dans de des du elle elles en et eux il ils je la le les
leur leurs lui ma mais me même mes moi mon ne nos notre nous on ou où par pas pour qu que qui sa se
ses son sur ta te tes toi ton tu un une vos votre vous est sont été être avoir ont a été fait plus
après avant aussi comme dont entre sans sous tout tous toute toutes très deux trois selon été l d
c s n j qu y ça cela ceci si mais donc or ni car alors encore déjà bien fait faire peut ans an
""".split()


def charger_articles() -> list[dict]:
    """Articles propres publiés dans les dernières 24 h (fenêtre du TD 5), avec l'extrait."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(
            "SELECT id, source, titre, extrait, publie_le FROM articles_propres"
            " WHERE publie_le > now() - interval '24 hours' ORDER BY publie_le"
        ).fetchall()


def decrire(labels: np.ndarray, textes: list[str], titres: list[str], vecteurs: np.ndarray):
    """Pour chaque groupe : taille, mots-clés (TF-IDF par groupe), titre le plus central."""
    groupes = sorted(set(labels) - {-1})
    documents = [
        " ".join(t for t, lab in zip(textes, labels, strict=True) if lab == g) for g in groupes
    ]
    tfidf = TfidfVectorizer(stop_words=MOTS_VIDES, token_pattern=r"(?u)\b[^\W\d_]{3,}\b")
    poids = tfidf.fit_transform(documents).toarray()
    mots = tfidf.get_feature_names_out()
    themes = []
    for i, g in enumerate(groupes):
        membres = np.where(labels == g)[0]
        centre = vecteurs[membres].mean(axis=0)
        central = membres[np.argmax(vecteurs[membres] @ centre)]
        themes.append(
            {
                "taille": len(membres),
                "mots_cles": ", ".join(mots[j] for j in poids[i].argsort()[::-1][:5]),
                "titre": titres[central],
            }
        )
    return sorted(themes, key=lambda t: -t["taille"])


def metriques(labels: np.ndarray, vecteurs: np.ndarray) -> dict:
    """Métriques demandées par le TD. Silhouette calculée sans le bruit (étiquette -1)."""
    gardes = labels != -1
    tailles = [int((labels == g).sum()) for g in set(labels) - {-1}]
    silhouette = (
        silhouette_score(vecteurs[gardes], labels[gardes], metric="cosine")
        if len(tailles) > 1
        else float("nan")
    )
    return {
        "themes": len(tailles),
        "taille_mediane": statistics.median(tailles) if tailles else 0,
        "part_bruit": round(float((~gardes).mean()), 3),
        "silhouette": round(float(silhouette), 3),
    }


def kmeans(vecteurs, textes):
    return KMeans(n_clusters=K, random_state=GRAINE, n_init=10).fit_predict(vecteurs)


def hdbscan_seul(vecteurs, textes):
    # Vecteurs normalisés : la distance euclidienne suit alors la similarité cosinus.
    return HDBSCAN(min_cluster_size=TAILLE_MIN).fit_predict(vecteurs)


def bertopic(vecteurs, textes):
    modele = BERTopic(
        umap_model=UMAP(n_neighbors=15, n_components=5, metric="cosine", random_state=GRAINE),
        hdbscan_model=BertopicHDBSCAN(min_cluster_size=TAILLE_MIN, prediction_data=True),
        vectorizer_model=CountVectorizer(stop_words=MOTS_VIDES),
    )
    labels, _ = modele.fit_transform(textes, embeddings=vecteurs)
    return np.array(labels)


def main() -> None:
    articles = charger_articles()
    textes = [f"{a['titre']}. {a['extrait']}" for a in articles]
    titres = [a["titre"] for a in articles]
    print(f"{len(articles)} articles publiés dans les dernières 24 h")

    debut = time.perf_counter()
    vecteurs = SentenceTransformer(MODELE).encode(textes, normalize_embeddings=True)
    print(f"Embeddings : {vecteurs.shape} en {time.perf_counter() - debut:.1f} s ({MODELE})")

    lignes = [
        f"# Comparaison des regroupements — {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        "",
        f"- Articles : {len(articles)} (publiés dans les dernières 24 h)",
        f"- Modèle d'embedding : `{MODELE}`, texte = titre + extrait",
        f"- Paramètres : k-means k={K} ; HDBSCAN et BERTopic taille min={TAILLE_MIN} ;"
        f" graine={GRAINE}",
        "- Silhouette calculée sans le bruit, en distance cosinus (de -1 à 1, plus haut = "
        "groupes plus nets)",
        "",
        "| Méthode | Thèmes | Taille médiane | Part de bruit | Silhouette | Durée |",
        "|---|---|---|---|---|---|",
    ]
    details = []
    for nom, methode in (("k-means", kmeans), ("HDBSCAN", hdbscan_seul), ("BERTopic", bertopic)):
        debut = time.perf_counter()
        labels = methode(vecteurs, textes)
        duree = time.perf_counter() - debut
        m = metriques(labels, vecteurs)
        print(f"{nom:9} {m} en {duree:.1f} s")
        lignes.append(
            f"| {nom} | {m['themes']} | {m['taille_mediane']} | {m['part_bruit']:.0%} |"
            f" {m['silhouette']} | {duree:.1f} s |"
        )
        details += ["", f"## {nom}", "", "| Taille | Mots-clés | Titre le plus central |"]
        details.append("|---|---|---|")
        for t in decrire(labels, textes, titres, vecteurs):
            details.append(f"| {t['taille']} | {t['mots_cles']} | {t['titre']} |")

    SORTIES.mkdir(exist_ok=True)
    sortie = SORTIES / f"comparaison-{datetime.now(UTC):%Y-%m-%d}.md"
    sortie.write_text("\n".join(lignes + details) + "\n", encoding="utf-8")
    print(f"Rapport : {sortie}")


if __name__ == "__main__":
    main()
