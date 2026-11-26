"""Dossier de relecture : contexte du run, dix jugements laissés à la personne."""

import json
from pathlib import Path


def export_review(run, directory: Path):
    evaluation = run.get("evaluation") or {}
    sample = evaluation.get("echantillon", [])
    if len(sample) != 10:
        raise ValueError("Ce run ne contient pas un échantillon de dix articles.")
    directory.mkdir(parents=True, exist_ok=True)
    template = directory / f"reponses-run-{run['id']}.json"
    # Ne jamais effacer les réponses d'une personne lors d'un nouvel export.
    if not template.exists():
        template.write_text(
            json.dumps(
                [
                    {"article_id": row["article_id"], "bien_place": None, "commentaire": ""}
                    for row in sample
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    lines = [
        f"# Relecture humaine — run {run['id']}",
        "",
        f"Fenêtre : {run['fenetre_debut']} → {run['fenetre_fin']}",
        f"Articles : {run['nb_articles']} ; verdict automatique : {evaluation['verdict']}.",
        f"Métriques : `{json.dumps(run['metriques'], ensure_ascii=False)}`",
        "",
        "Lire le titre et l'extrait, puis comparer le sujet au thème et aux articles voisins.",
        "Ouvrir le lien source si le contexte ne suffit pas. Pour un article en bruit, juger",
        "s'il est raisonnable de le laisser hors thème. Ne pas évaluer la véracité de l'article.",
        "Pour chaque numéro, répondre **oui / non / incertain**, avec une phrase de justification.",
        "Un cas incertain doit être discuté avant l'enregistrement définitif (oui ou non).",
        "Les voisins sont un contexte, pas des réponses attendues. Aucun jugement n'est prérempli.",
        "Juger le regroupement à partir du texte fourni au modèle.",
        "",
    ]
    for number, row in enumerate(sample, 1):
        lines += [
            f"## {number}. {row['titre']}",
            "",
            f"Identifiant : `{row['article_id']}`",
            f"Source : {row.get('source', '')}",
            f"Lien : {row.get('lien', '')}",
            "",
            f"**Extrait :** {row.get('extrait', '')}",
            "",
            f"**Thème proposé :** {row['theme'] or 'Bruit — aucun thème'}",
            f"**Mots-clés :** {', '.join(row.get('mots_cles', []))}",
            "",
            "**Autres articles du même groupe :**",
            "",
        ]
        lines += [f"- {title}" for title in row.get("voisins", [])] or ["Aucun (bruit)."]
        lines += ["", "**Ton avis :** oui / non / incertain — justification : …", ""]
    report = directory / f"relecture-run-{run['id']}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return {"dossier": str(report), "reponses": str(template)}
