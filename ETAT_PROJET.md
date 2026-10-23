# État du projet

Dernière mise à jour : 23 octobre 2026 (début du TD 5).

## Avancement des TD

| TD | Sujet | État | Preuves |
|---|---|---|---|
| 1 | Cadrage | Terminé | `docs/cadrage.md`, `docs/Schema-architecture-pipeline.png`, `sources.csv` |
| 2 | Socle | Terminé, sauf revue croisée | PR #1 fusionnée, CI verte sur `main`, `docs/validation-td2.md` |
| 3 | Collecte | Terminé | PR #3 et PR de finitions, collecte Prefect toutes les 30 min, `docs/donnees.md`, `docs/exploitation.md` |
| 4 | Qualité | Terminé (PR #7 fusionnée) | `docs/qualite.md`, migrations 002-003, alerte Discord déclenchée le 22/10 |
| 5 | MLOps 1 | Terminé, en revue | `docs/mlops.md`, migration 004, flow `themes-du-jour` (6 h 30), run de référence n° 5 du 23/10 |
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
- Prefect 3.9 : flow `collecte` toutes les 30 min, flow `themes-du-jour` à 6 h 30,
  UI sur `localhost:4200`.
- Thèmes : sentence-transformers (modèle intégré à l'image), BERTopic (UMAP + HDBSCAN),
  PyTorch CPU ; paramètres dans `config/clustering.yaml`, runs tracés en base.
- Stockage brut : un fichier JSON par article dans `articles_bruts/` ;
  table `sources` dans PostgreSQL (migrations versionnées).
- GitHub Actions : lint → tests → build → push GHCR, tag `YYYYMMDDHHMMSS-sha`.

Prévue dans le cadrage, non validée en pratique : Pandas et Pandera,
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
| 2026-10-22 | Nettoyage dans le même flow que la collecte (tâche `nettoyage-et-controles`), juste après elle | `src/gazette/flows.py` |
| 2026-10-22 | Règles lisibles (regex, seuils) dans `rules.py`, pas de modèle ; un identifiant par règle (R01 à R12) | `docs/qualite.md` |
| 2026-10-22 | Doublon approché : Jaccard ≥ 0,8 sur les mots du titre normalisé, fenêtre de 48 h ; on garde le plus ancien | `src/gazette/rules.py` |
| 2026-10-22 | Contrôles de données en assertions maison plutôt que Pandera (prévu au cadrage) : 4 faits simples, pas de dépendance de plus | `docs/qualite.md` |
| 2026-10-22 | Alertes vers un webhook Discord (`ALERT_WEBHOOK_URL` dans `.env`, jamais commité) ; une alerte par passage au rouge, renvoyée tant qu'elle n'est pas partie | `src/gazette/quality.py` |
| 2026-10-22 | Rétention : 90 jours pour le brut, `articles_propres` et `rejets` ; 1 an pour contrôles et rapports | `docs/donnees.md` |
| 2026-10-23 | Regroupement : BERTopic (choix du cadrage, suggéré par l'enseignant), sur nos propres embeddings mis en cache ; graine UMAP fixée ; paramètres dans `config/clustering.yaml`. À confirmer par la comparaison k-means / HDBSCAN / BERTopic sur un vrai jeu d'articles | `docs/cadrage.md` |
| 2026-10-23 | Embeddings : `sentence-transformers`, modèle multilingue léger sur CPU (`paraphrase-multilingual-MiniLM-L12-v2`) ; PyTorch en version CPU pour garder une image légère | `requirements.in` |
| 2026-10-23 | Modèle intégré à l'image au build, à une révision figée : version connue et tracée, aucun téléchargement au run (conteneur en lecture seule) | `Dockerfile` |
| 2026-10-23 | Nom d'un thème : mots-clés c-TF-IDF (colonne `mots_cles`) + titre d'article le plus proche du centre du groupe | `docs/cadrage.md` |
| 2026-10-23 | Traçage des runs dans une table `runs` PostgreSQL (fenêtre, nombre d'articles, hash de l'entrée, modèle et version, paramètres, métriques), référencée par `themes.run_id` ; résumé publié en artefact Prefect. Pas de MLflow : un service de plus pour le même besoin | `docs/mlops.md` |
| 2026-10-23 | Regroupement une fois par jour à 6 h 30 (Europe/Paris), flow `themes-du-jour` : nettoyage (idempotent) → embeddings → regroupement → stockage. Un seul run fait « les thèmes du jour », prêts pour la publication de 7 h | `src/gazette/flows.py` |
| 2026-10-23 | BERTopic confirmé par la comparaison sur 358 articles réels (k-means : groupes fourre-tout ; HDBSCAN seul : 68 % de bruit) | `docs/mlops.md`, `explorations/` |
| 2026-10-23 | BERTopic en `language="multilingual"` : en mode anglais par défaut, il retirait les accents des mots-clés | `src/gazette/themes.py` |
| 2026-10-23 | Bruit gardé comme bruit (pas de réaffectation) ; probabilité d'appartenance stockée pour le TD 6 | `docs/mlops.md` |
| 2026-10-23 | Compilateur dans l'étage de build Docker : `hdbscan` n'a pas de paquet précompilé pour Linux ARM | `Dockerfile` |

## Responsabilités

| Membre | Composantes |
|---|---|
| Riad | Collecte (TD 3) : collecteur, stockage brut, table `sources`, orchestration Prefect |
| Samy | Nettoyage et qualité (TD 4) : normalisation, règles d'exclusion, `articles_propres`, rapport, contrôles et alertes |
| _à compléter_ | |

## Problèmes ouverts

- **Alertes** : la machine qui fait tourner la collecte doit avoir un `.env` avec
  `ALERT_WEBHOOK_URL`, sinon chaque passage rouge logue `alerte_non_envoyee` (et réessaie).

- **Exécution de la collecte** : elle tourne sur le poste de Riad, qui doit rester
  allumé ; décider qui la fait tourner jusqu'à l'infrastructure de production.
- Seules La Croix et Libération envoient `ETag` / `Last-Modified` : les 6 autres
  flux sont retéléchargés en entier à chaque passage.
- `rubrique` souvent vide (Le Monde n'envoie pas de `<category>`).
- Compteurs cumulés (articles par source et par jour) : à exposer au TD 8 (monitoring).
- Fixture : contenus fictifs, donc les variantes réelles des flux ne sont pas couvertes.
- Revue croisée avec une autre équipe : non réalisée.
- Chaque membre doit avoir fait un commit passé par la CI via une PR.
- Image Docker ≈ 3,5 Go depuis le TD 5 (PyTorch CPU, modèle intégré) : build plus long.
- Thèmes : actualité sociale découpée en plusieurs thèmes voisins, quelques groupes
  fourre-tout, ≈ 25 % de bruit ; à évaluer au TD 6.

## Prochaines étapes

1. TD 4 (reste à faire) : lire le rapport 3 matins de suite et noter ce qu'on en tire dans `docs/qualite.md`.
2. TD 5 : laisser tourner `themes-du-jour` chaque jour ; relire les thèmes de deux journées et remplir la grille de `docs/mlops.md` (matière du TD 6).
3. Procédures d'exploitation : `docs/exploitation.md`. Limite : avec une seule source dans `sources.csv`, ses erreurs passagères ne seraient jamais comptées.
4. Revue croisée et retour consigné dans `docs/validation-td2.md`.
5. Un commit par membre via une PR.
