import json

import pytest

from gazette.review import export_review


def test_export_preserves_human_answers_and_includes_context(tmp_path):
    run = {
        "id": 7,
        "fenetre_debut": "hier",
        "fenetre_fin": "aujourd'hui",
        "nb_articles": 20,
        "metriques": {},
        "evaluation": {
            "verdict": "candidat",
            "echantillon": [
                {
                    "article_id": str(i),
                    "titre": f"Article {i}",
                    "theme": "Tempête",
                    "voisins": ["Vigilance orange"],
                    "extrait": "Pluies annoncées",
                }
                for i in range(10)
            ],
        },
    }
    result = export_review(run, tmp_path)
    path = tmp_path / "reponses-run-7.json"
    assert len(json.loads(path.read_text())) == 10
    assert all(row["bien_place"] is None for row in json.loads(path.read_text()))
    path.write_text("relecture humaine existante")
    export_review(run, tmp_path)
    assert path.read_text() == "relecture humaine existante"
    assert "Vigilance orange" in (tmp_path / "relecture-run-7.md").read_text()
    assert result["dossier"].endswith("relecture-run-7.md")
    run["evaluation"]["echantillon"] = []
    with pytest.raises(ValueError):
        export_review(run, tmp_path)
