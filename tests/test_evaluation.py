from copy import deepcopy
from datetime import timedelta

import pytest
from test_themes import CONFIG, NOW, articles, encoder, fake_cluster

from gazette.evaluation import evaluate, load_policy
from gazette.themes import MemoryThemeStore, metrics, run_themes

GOOD = {
    "silhouette": 0.16,
    "themes": 4,
    "part_bruit": 0.25,
    "part_groupe_max": 0.30,
    "taille_mediane": 8,
}


@pytest.mark.parametrize(
    "key,value",
    [
        ("silhouette", None),
        ("silhouette", float("nan")),
        ("themes", 1),
        ("part_bruit", 0.8),
        ("part_groupe_max", 0.9),
        ("taille_mediane", 1),
    ],
)
def test_guardrails(key, value):
    assert evaluate(GOOD | {key: value}, [], NOW, load_policy())["verdict"] == "recale"


def test_drift_requires_previous_calendar_day_and_ignores_same_day():
    m = GOOD | {"part_bruit": 0.5}
    history = [{"fenetre_fin": NOW - timedelta(days=1), "metriques": m}]
    assert evaluate(m, history, NOW, load_policy())["verdict"] == "revue"
    for delta in [timedelta(hours=1), timedelta(days=2)]:
        history[0]["fenetre_fin"] = NOW - delta
        assert evaluate(m, history, NOW, load_policy())["verdict"] == "candidat"


def test_rejected_and_ci_runs_do_not_publish():
    store = MemoryThemeStore(articles())
    run_themes(store, encoder, CONFIG, NOW, cluster=fake_cluster)
    previous = deepcopy(store.themes)
    policy = load_policy()
    policy["seuils"]["silhouette_min"] = 1.1
    result = run_themes(store, encoder, CONFIG, NOW, cluster=fake_cluster, policy=policy)
    assert result["evaluation"]["verdict"] == "recale"
    assert store.themes == previous
    assert store.runs[2]["termine_le"] is not None
    run_themes(store, encoder, CONFIG, NOW, cluster=fake_cluster, publish=False)
    assert store.themes == previous
    assert len(store.runs[3]["evaluation"]["echantillon"]) == 10


def test_singletons_have_undefined_silhouette():
    assert metrics([0, 1], [[1.0, 0.0], [0.0, 1.0]])["silhouette"] is None
