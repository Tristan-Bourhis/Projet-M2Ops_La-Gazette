# Infrastructure de développement

La définition exécutable est `../docker-compose.yml`, à la racine pour permettre
`docker compose up` sans option supplémentaire.

| Service | Rôle | Persistance | Démarrage |
|---|---|---|---|
| app | Traitement ponctuel : `python -m gazette` (TD 2) ou `python -m gazette.collect` | volume gazette-output, `/data` | après PostgreSQL sain |
| collecteur | Flow Prefect `collecte`, toutes les 30 min | volume gazette-output, `/data/articles_bruts` | après PostgreSQL et Prefect sains ; `restart: unless-stopped` |
| prefect-server | Planning, historique et logs des runs ; UI sur `127.0.0.1:4200` | volume prefect-data | test `/api/health` |
| postgres | Table `sources` (état des flux) | volume postgres-data | test pg_isready |
| tests | Ruff et pytest | aucune | profil `test`, réseau coupé |

L'application et le collecteur s'exécutent avec UID/GID 10001, sans privilèges
supplémentaires, racine en lecture seule (écriture uniquement dans `/data` et `/tmp`).
Le conteneur final contient Python et les seules dépendances d'exécution ; les outils
de test restent dans la cible `test`.

Le compte PostgreSQL `gazette` et son mot de passe sont locaux au réseau Compose.
La base n'est pas publiée sur un port hôte ; l'interface Prefect n'écoute que sur
`127.0.0.1`. Aucun secret de production n'est configuré. Les volumes sont conservés
lors d'un simple `down`.

Le schéma de la base évolue par migrations SQL versionnées (`../migrations/`),
appliquées au début de chaque collecte, une seule fois chacune (table
`schema_migrations`, verrou consultatif contre les applications concurrentes).

En attendant l'infrastructure de production (TD 4 ou 6), la collecte tourne sur le
poste d'un membre de l'équipe, qui doit rester allumé : voir `ETAT_PROJET.md`.
Le déploiement, les métriques et les tableaux de bord viendront aux prochains TD.

## Runner CI local (TD 6)

Le runner officiel est préparé dans `output/runner` (non versionné). Après
l'authentification GitHub du propriétaire, son enregistrement doit utiliser les
labels `self-hosted,gazette-production` et le dépôt `Tristan-Bourhis/Projet-M2Ops_La-Gazette`.
Le modèle d'unité utilisateur `gazette-runner.service.in` est prévu pour maintenir
le processus actif ; remplacer `@RUNNER_DIR@` par le chemin absolu avant installation.
Le runner ne doit pas être annoncé opérationnel tant que GitHub ne le voit pas
`online` et que le workflow n'a pas réellement tourné.

L'évaluation utilise un clone PostgreSQL jetable ; seul le résumé numérique
est exporté vers GitHub. La branche par défaut déploie sur les volumes `projetm2ops`
existants. Les PR de forks ne peuvent pas satisfaire l'évaluation locale : les
changements approuvés doivent être repris sur une branche interne.
