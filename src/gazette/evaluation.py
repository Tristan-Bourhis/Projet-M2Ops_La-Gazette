"""Garde-fous sans vérité terrain ; une observation par jour UTC."""

import math
from datetime import timedelta
from pathlib import Path

import yaml


def load_policy():
    return yaml.safe_load(Path("config/evaluation.yaml").read_text())


def evaluate(metrics, history, now, policy):
    s = policy["seuils"]
    reasons = []
    for key, limit, minimum in (
        ("silhouette", s["silhouette_min"], True),
        ("themes", s["themes_min"], True),
        ("taille_mediane", s["taille_mediane_min"], True),
        ("part_bruit", s["part_bruit_max"], False),
        ("part_groupe_max", s["part_groupe_max"], False),
    ):
        value = metrics.get(key)
        if (
            value is None
            or not math.isfinite(value)
            or (value < limit if minimum else value > limit)
        ):
            reasons.append(key)
    d = policy["derive"]

    def drift(m):
        return (
            m.get("part_bruit", 0) > d["part_bruit_max"]
            or m.get("silhouette") is None
            or m["silhouette"] < d["silhouette_min"]
        )

    days = {}
    for run in sorted(history, key=lambda r: r["fenetre_fin"]):
        if run["fenetre_fin"].date() < now.date():
            days[run["fenetre_fin"].date()] = run["metriques"]
    review = drift(metrics) and all(
        now.date() - timedelta(days=i) in days and drift(days[now.date() - timedelta(days=i)])
        for i in range(1, d["jours_consecutifs"])
    )
    return {
        "verdict": "recale" if reasons else "revue" if review else "candidat",
        "raisons": reasons,
        "derive": review,
        "politique": policy,
    }
