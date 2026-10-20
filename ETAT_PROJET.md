# État du projet

Dernière mise à jour : 20 octobre 2026 (fin du TD 2).

## Avancement des TD

| TD | Sujet | État | Preuves |
|---|---|---|---|
| 1 | Cadrage | Terminé | `docs/cadrage.md`, `docs/Schema-architecture-pipeline.png`, `sources.csv` |
| 2 | Socle | Terminé, sauf revue croisée | PR #1 fusionnée, CI verte sur `main`, `docs/validation-td2.md` |
| 3 | Collecte | À faire | — |
| 4 | Qualité | À faire | — |
| 5 | MLOps 1 | À faire | — |
| 6 | MLOps 2 | À faire | — |
| 7 | Livraison | À faire | — |
| 8 | Monitoring | À faire | — |
| 9 | IaC | À faire | — |
| 10 | Soutenance | À faire | — |

## Stack

En place (TD 2) :

- Python 3.12, httpx, feedparser, defusedxml ; dépendances figées dans les `.lock`.
- Ruff et pytest.
- Docker multi-étapes (utilisateur non root 10001) et Docker Compose (app + PostgreSQL).
- GitHub Actions : lint → tests → build → push GHCR, tag `YYYYMMDDHHMMSS-sha`.

Prévue dans le cadrage, non validée en pratique : Prefect (orchestration et
supervision), JSON brut + PostgreSQL propre, Pandas et Pandera, BERTopic,
Jinja2, Nginx, OpenTofu selon l'infrastructure fournie.

## Décisions

| Date | Décision | Référence |
|---|---|---|
| 2026-10-20 | Choix techniques prévisionnels du cadrage | `docs/cadrage.md` |
| 2026-10-20 | Première source : Ouest-France ; fixture aux contenus fictifs | `tests/fixtures/README.md` |
| 2026-10-20 | 8 sources (4 PQR, 4 PQN) retenues ; CGU consultées, usage limité aux titres, extraits, liens et dates | `sources.csv` |
| 2026-10-20 | `main` protégée : PR, 1 approbation, CI verte obligatoire | `CONTRIBUTING.md`, `docs/validation-td2.md` |

## Responsabilités

À compléter par l'équipe (membre → composantes).

## Problèmes ouverts

- Fréquences de `sources.csv` mesurées une seule fois (20 octobre 2026) ;
  certains flux ne couvrent que quelques heures (Ouest-France : ≈ 40 min),
  à prendre en compte pour la fréquence de collecte au TD 3.
- Fixture : contenus fictifs, donc les variantes réelles des flux ne sont pas couvertes.
- Revue croisée avec une autre équipe : non réalisée.
- Chaque membre doit avoir fait un commit passé par la CI via une PR.

## Prochaines étapes

1. Revue croisée et retour consigné dans `docs/validation-td2.md`.
2. Un commit par membre via une PR.
3. Pour le TD 3 : étudier le format des flux et leurs en-têtes HTTP (`curl -I`).
