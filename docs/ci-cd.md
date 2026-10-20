1. GitHub Actions exécute `.github/workflows/ci.yml` à chaque push et pull request.
2. Python 3.12 et les dépendances figées alignent CI et environnement Docker.
3. Ruff contrôle le code et son format ; une erreur arrête le job.
4. Pytest teste le parseur, la CLI et les erreurs HTTP avec fixture et réseau simulé.
5. Le job image dépend du succès complet du job lint/tests.
6. Docker construit une image multi-étapes, exécutée par l'utilisateur 10001.
7. Un test de l'image vérifie l'utilisateur et l'export JSON hors réseau.
8. Chaque push publie cette même image sur GHCR avec GITHUB_TOKEN ; les PR ne publient pas.
9. Le tag UTC YYYYMMDDHHMMSS-sha et les labels OCI identifient le commit exact.
10. Aucun déploiement au TD 2 ; main nécessite revue et CI verte, puis déploiement aux TD suivants.
