from datetime import UTC, datetime, timedelta

from gazette.embed import MemoryEmbeddingStore, article_text, embed_articles, window_articles

NOW = datetime(2026, 10, 23, 6, 30, tzinfo=UTC)
MODELE = "modele-test@rev1"


def articles(n=10, hours_ago=1):
    return [
        {
            "id": f"a{i}",
            "source": "Le Monde",
            "titre": f"Titre {i}",
            "extrait": f"Extrait {i}",
            "publie_le": NOW - timedelta(hours=hours_ago, minutes=i),
        }
        for i in range(n)
    ]


class FakeEncoder:
    """Remplace le modèle : vecteur déterministe, et compte les textes encodés."""

    def __init__(self):
        self.textes = []

    def __call__(self, textes):
        self.textes += textes
        return [[float(len(t)), 1.0] for t in textes]


def test_window_keeps_last_24_hours_only():
    store = MemoryEmbeddingStore(articles(10) + articles(1, hours_ago=25) + articles(1, -1))
    assert len(window_articles(store, NOW)) == 10  # ni l'article d'hier, ni celui du futur


def test_text_is_title_then_excerpt():
    assert article_text({"titre": "Tempête", "extrait": "Vigilance orange."}) == (
        "Tempête. Vigilance orange."
    )
    assert article_text({"titre": "Tempête", "extrait": ""}) == "Tempête"


def test_ten_articles_are_embedded_once_then_read_from_cache():
    store, encoder = MemoryEmbeddingStore(), FakeEncoder()
    dix = articles(10)

    first = embed_articles(store, dix, MODELE, encoder, NOW)
    assert list(first) == [a["id"] for a in dix]  # un vecteur par article, dans l'ordre
    assert len(encoder.textes) == 10

    assert embed_articles(store, dix, MODELE, encoder, NOW) == first
    assert len(encoder.textes) == 10  # rien recalculé

    onze = dix + [{**dix[0], "id": "nouveau"}]
    embed_articles(store, onze, MODELE, encoder, NOW)
    assert len(encoder.textes) == 11  # seul le nouvel article est calculé


def test_other_model_does_not_reuse_cache():
    store, encoder = MemoryEmbeddingStore(), FakeEncoder()
    embed_articles(store, articles(10), MODELE, encoder, NOW)
    embed_articles(store, articles(10), "autre-modele@rev2", encoder, NOW)
    assert len(encoder.textes) == 20
