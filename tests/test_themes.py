import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gazette.themes import (
    MemoryThemeStore,
    central_title,
    input_hash,
    load_config,
    metrics,
    model_key,
    run_themes,
    themes_markdown,
)

NOW = datetime(2026, 10, 23, 6, 30, tzinfo=UTC)
CONFIG = load_config(Path(__file__).parents[1] / "config" / "clustering.yaml")
# 16 articles : 6 sur la tempête, 6 sur l'Ukraine, 4 isolés (bruit).
LABELS = [0] * 6 + [1] * 6 + [-1] * 4


def articles():
    return [
        {
            "id": f"a{i:02}",
            "source": "Le Monde",
            "titre": f"Titre {i}",
            "extrait": "Extrait",
            "publie_le": NOW - timedelta(minutes=10 + i),
        }
        for i in range(len(LABELS))
    ]


def expected(texte):
    """Groupe attendu d'un article, lu dans son texte (« Titre 7. Extrait » -> LABELS[7])."""
    return LABELS[int(texte.split()[1].rstrip("."))]


def encoder(textes):
    # Vecteurs bien séparés selon le groupe attendu de chaque article.
    vectors = {0: [1.0, 0.0, 0.0], 1: [0.0, 1.0, 0.0], -1: [0.0, 0.0, 1.0]}
    return [vectors[expected(t)] for t in textes]


def fake_cluster(textes, vecteurs, config):
    keywords = {0: ["tempête", "vigilance"], 1: ["ukraine", "guerre"]}
    return [expected(t) for t in textes], [0.9] * len(textes), keywords


def test_run_is_traced_with_data_params_metrics_and_artifacts():
    store = MemoryThemeStore(articles())
    result = run_themes(store, encoder, CONFIG, NOW, cluster=fake_cluster)

    run = store.runs[result["run_id"]]
    assert run["lance_le"] == NOW and run["termine_le"] > NOW
    assert run["nb_articles"] == 16 and run["hash_entree"] == input_hash(articles())
    assert run["fenetre_debut"] == NOW - timedelta(hours=24)
    assert run["modele"] == model_key(CONFIG) and run["parametres"]["graine"] == 42
    assert set(run["parametres"]["bibliotheques"]) >= {"bertopic", "umap-learn", "hdbscan"}
    assert run["metriques"]["themes"] == 2
    assert run["metriques"]["part_bruit"] == 0.25
    assert run["metriques"]["silhouette"] == 1.0  # groupes parfaitement séparés

    assert [t["mots_cles"] for t in store.themes] == [
        ["tempête", "vigilance"],
        ["ukraine", "guerre"],
    ]
    noise = [a for a in store.affectations if a["theme_id"] is None]
    assert len(store.affectations) == 16 and len(noise) == 4  # le bruit est gardé
    assert all(a["probabilite"] is None for a in noise)


def test_input_hash_ignores_order_but_not_text():
    assert input_hash(articles()) == input_hash(list(reversed(articles())))
    assert input_hash(articles()) != input_hash(articles()[1:])
    changed = articles()
    changed[0]["extrait"] = "Extrait corrigé"
    assert input_hash(articles()) != input_hash(changed)  # même id, texte différent


def test_central_title_is_closest_to_group_center():
    arts = [{"titre": "excentré"}, {"titre": "central"}, {"titre": "autre bord"}]
    vecteurs = [[1.0, 0.0], [0.7, 0.7], [0.0, 1.0]]
    assert central_title([0, 1, 2], arts, vecteurs) == "central"


def test_metrics_without_themes():
    assert metrics([-1, -1], [[1.0], [1.0]]) == {
        "themes": 0,
        "taille_mediane": 0,
        "part_bruit": 1.0,
        "silhouette": None,
    }


def test_too_few_articles_leaves_an_unfinished_run():
    store = MemoryThemeStore(articles()[:3])
    with pytest.raises(ValueError, match="il en faut au moins"):
        run_themes(store, encoder, CONFIG, NOW, cluster=fake_cluster)
    assert store.runs[1]["termine_le"] is None and store.themes == []


def test_bertopic_is_reproducible_with_fixed_seed():
    pytest.importorskip("bertopic")
    from gazette.themes import bertopic_cluster

    rng = random.Random(0)
    centers = [[rng.gauss(0, 1) for _ in range(16)] for _ in range(3)]
    vecteurs = [[c + rng.gauss(0, 0.05) for c in center] for center in centers for _ in range(12)]
    sujets = ["tempête vigilance", "ukraine guerre", "budget assemblée"]
    textes = [f"{sujets[i // 12]} article" for i in range(36)]

    first = bertopic_cluster(textes, vecteurs, CONFIG)
    second = bertopic_cluster(textes, vecteurs, CONFIG)
    assert first[0] == second[0]  # même graine, mêmes données : mêmes thèmes
    assert len(set(first[0]) - {-1}) == 3


def test_markdown_summary_lists_themes_of_the_run():
    result = run_themes(MemoryThemeStore(articles()), encoder, CONFIG, NOW, cluster=fake_cluster)
    markdown = themes_markdown(result)
    assert "run 1" in markdown and "bruit 25%" in markdown
    assert "| 6 | tempête, vigilance |" in markdown
