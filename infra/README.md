# Infrastructure de développement

La définition exécutable est `../docker-compose.yml`, à la racine pour permettre
`docker compose up` sans option supplémentaire.

| Service | Rôle | Persistance | Démarrage |
|---|---|---|---|
| app | Traitement RSS → JSON, une exécution | volume gazette-output, `/data` | après PostgreSQL sain |
| postgres | Base pour les prochains TD | volume postgres-data | test pg_isready |
| tests | Ruff et pytest | aucune | profil `test`, réseau coupé |

L'application s'exécute avec UID/GID 10001, sans privilèges supplémentaires,
avec racine en lecture seule dans Compose. Le volume de sortie est préparé pour
cet utilisateur dans l'image. Le conteneur final contient Python et les seules
dépendances d'exécution ; les outils de test restent dans la cible `test`.

Le compte PostgreSQL `gazette` et son mot de passe sont locaux au réseau Compose.
La base n'est pas publiée sur un port hôte. Aucun secret de production n'est
configuré dans ce socle. Les volumes sont conservés lors d'un simple `down`.
La base ne reçoit pas encore les items : son schéma et les écritures viendront
avec les étapes suivantes.

L'ordonnanceur, le déploiement, les métriques et tableaux de bord seront ajoutés
dans des fichiers versionnés lors des prochains TD.
