# État du projet

Dernière mise à jour : 22 octobre 2026 (fin du TD 3).

## Avancement des TD

| TD | Sujet | État | Preuves |
|---|---|---|---|
| 1 | Cadrage | Terminé | `docs/cadrage.md`, `docs/Schema-architecture-pipeline.png`, `sources.csv` |
| 2 | Socle | Terminé, sauf revue croisée | PR #1 fusionnée, CI verte sur `main`, `docs/validation-td2.md` |
| 3 | Collecte | Terminé | PR #3 et PR de finitions, collecte Prefect toutes les 30 min, `docs/donnees.md`, `docs/exploitation.md` |
| 4 | Qualité | À faire | — |
| 5 | MLOps 1 | À faire | — |
| 6 | MLOps 2 | À faire | — |
| 7 | Livraison | À faire | — |
| 8 | Monitoring | À faire | — |
| 9 | IaC | À faire | — |
| 10 | Soutenance | À faire | — |

## Stack

En place :

- Python 3.12, httpx, feedparser, defusedxml, psycopg ; dépendances figées dans les `.lock`.
- Ruff et pytest ; tests PostgreSQL exécutés en CI sur une base jetable.
- Docker multi-étapes (utilisateur non root 10001) et Docker Compose
  (app, collecteur, prefect-server, PostgreSQL).
- Prefect 3.9 : flow `collecte` toutes les 30 min, UI sur `localhost:4200`.
- Stockage brut : un fichier JSON par article dans `articles_bruts/` ;
  table `sources` dans PostgreSQL (migrations versionnées).
- GitHub Actions : lint → tests → build → push GHCR, tag `YYYYMMDDHHMMSS-sha`.

Prévue dans le cadrage, non validée en pratique : Pandas et Pandera, BERTopic,
Jinja2, Nginx, OpenTofu selon l'infrastructure fournie.

## Décisions

| Date | Décision | Référence |
|---|---|---|
| 2026-10-20 | Choix techniques prévisionnels du cadrage | `docs/cadrage.md` |
| 2026-10-20 | Première source : Ouest-France ; fixture aux contenus fictifs | `tests/fixtures/README.md` |
| 2026-10-20 | 8 sources (4 PQR, 4 PQN) retenues | `sources.csv` |
| 2026-10-20 | `main` protégée : PR, 1 approbation, CI verte obligatoire | `CONTRIBUTING.md`, `docs/validation-td2.md` |
| 2026-10-22 | Orchestrateur : Prefect (consigne : Prefect ou Airflow ; Airflow jugé trop lourd) | `src/gazette/flows.py` |
| 2026-10-22 | Collecte toutes les 30 min : le flux Ouest-France ne couvre qu'≈ 40 min | `docs/donnees.md` |
| 2026-10-22 | Brut = un JSON par article, clé (source, lien) ; aucun filtre avant le TD 4 | `docs/donnees.md` |
| 2026-10-22 | Sommeil après 3 échecs consécutifs (404, flux cassé, ou 5xx/timeout quand les autres sources répondent) ; run Prefect en échec tant qu'une source dort | `src/gazette/collect.py`, `flows.py` |
| 2026-10-22 | Erreurs passagères décidées en fin de passage : comptées si au moins une source a obtenu une réponse HTTP (la source est en panne), ignorées sinon (la machine est hors ligne) ; proposé par la revue de l'équipe | `src/gazette/collect.py`, `docs/exploitation.md` |
| 2026-10-22 | Pas de `retries` sur le flow : le run suivant (30 min) sert de reprise | `src/gazette/flows.py` |
| 2026-10-22 | Dépendances psycopg et Prefect ajoutées dans la PR de la collecte (exception à la règle « PR dédiée » : nécessaires à la fonctionnalité) | PR #3 |

## Responsabilités

| Membre | Composantes |
|---|---|
| Riad | Collecte (TD 3) : collecteur, stockage brut, table `sources`, orchestration Prefect |
| Samy | Nettoyage et qualité (TD 4) : normalisation, règles d'exclusion, `articles_propres`, rapport, contrôles et alertes |
| _à compléter_ | |

## Problèmes ouverts

- **Exécution de la collecte** : elle tourne sur le poste de Riad, qui doit rester
  allumé ; décider qui la fait tourner jusqu'à l'infrastructure de production.
- Seules La Croix et Libération envoient `ETag` / `Last-Modified` : les 6 autres
  flux sont retéléchargés en entier à chaque passage.
- `rubrique` souvent vide (Le Monde n'envoie pas de `<category>`).
- Compteurs cumulés (articles par source et par jour) : à exposer au TD 8 (monitoring).
- Fixture : contenus fictifs, donc les variantes réelles des flux ne sont pas couvertes.
- Revue croisée avec une autre équipe : non réalisée.
- Chaque membre doit avoir fait un commit passé par la CI via une PR.

## Prochaines étapes

1. TD 4 : brancher le webhook d'alerte (`.env`), déclencher l'alerte une fois, lire le rapport 3 matins et ajuster une règle (`docs/qualite.md`).
2. Procédures d'exploitation : `docs/exploitation.md`. Limite : avec une seule source dans `sources.csv`, ses erreurs passagères ne seraient jamais comptées.
3. Revue croisée et retour consigné dans `docs/validation-td2.md`.
4. Un commit par membre via une PR.
