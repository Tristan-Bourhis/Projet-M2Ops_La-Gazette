# Validation du TD 2

Contrôles réalisés le 20 octobre 2026 sur la branche `feat/td2-socle`.

| Vérification | Résultat |
|---|---|
| `docker compose config --quiet` | Configuration valide |
| `bin/test` | Ruff et format OK ; 23 tests passent sous Python 3.12 |
| Réseau des tests | Conteneur de tests exécuté avec `network_mode: none` |
| `bin/dev` | PostgreSQL sain ; deux items exportés dans `output/items.json` |
| Première source réelle | Échantillon Ouest-France lu et parsé en JSON dans un conteneur temporaire |
| Fixture versionnée | Structure/dates de cette lecture ; contenus éditoriaux remplacés par des exemples |
| Image finale | Construite, UID/GID 10001 ; export JSON vérifié sans réseau |
| Test volontairement cassé en local | Copie temporaire : attendu 3 items au lieu de 2 ; pytest retourne 1 |
| CI rouge GitHub | Assertion volontairement fausse : 1 échec, 22 succès ; job image ignoré |
| CI verte et publication GHCR | Vérification distante en cours après rétablissement de l'assertion |
| Protection de `main` | Non activée lors de la lecture de l'API GitHub ; conventions écrites dans CONTRIBUTING |
| Revue croisée entre équipes | À réaliser par une autre équipe ; aucune revue humaine simulée |

Le test cassé local ne modifie pas la suite livrée. La même assertion a ensuite
été temporairement cassée sur la branche distante, commit `6dba0fb`, puis rétablie.
[Exécution rouge vérifiée](https://github.com/Tristan-Bourhis/Projet-M2Ops_La-Gazette/actions/runs/39420416538) :
le job de qualité échoue dans pytest (lint réussi), et le job image est ignoré.
Cette exécution prouve qu'un test cassé empêche effectivement la publication.

La lecture réelle ponctuelle ne vaut pas autorisation d'exploitation collective.
Les sources restent désactivées ; seule la fixture fictive est utilisée
automatiquement par Compose et la CI.

La base est fournie et vérifiée par son healthcheck ; les items sont écrits
en JSON, conformément au périmètre du TD 2. Aucun schéma SQL, ordonnanceur,
serveur web ou déploiement de production n'est prétendu livré.
