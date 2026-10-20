# Validation du TD 2

Contrôles réalisés le 20 octobre 2026 sur la branche `feat/td2-socle`, puis
sur `main` après la fusion de la PR #1.

| Vérification | Résultat |
|---|---|
| `docker compose config --quiet` | Configuration valide |
| `bin/test` | Ruff et format OK ; 23 tests passent sous Python 3.12 |
| Retrait du garde-fou `ensure_enabled` | `bin/check` en local (Python 3.12.7) : Ruff et format OK, 19 tests passent |
| Réseau des tests | Conteneur de tests exécuté avec `network_mode: none` |
| `bin/dev` | PostgreSQL sain ; deux items exportés dans `output/items.json` |
| Première source réelle | Échantillon Ouest-France lu et parsé en JSON dans un conteneur temporaire |
| Fixture versionnée | Structure/dates de cette lecture ; contenus éditoriaux remplacés par des exemples |
| Image finale | Construite, UID/GID 10001 ; export JSON vérifié sans réseau |
| Test volontairement cassé en local | Copie temporaire : attendu 3 items au lieu de 2 ; pytest retourne 1 |
| CI rouge GitHub | Assertion volontairement fausse : 1 échec, 22 succès ; job image ignoré |
| CI verte et publication GHCR | Succès vérifié sur `59bce4d` : lint, 23 tests, build, test de l'image et push |
| Nouveau clone distant | `git clone --branch feat/td2-socle …` puis `bin/dev` : succès dans un projet Compose isolé |
| Fusion dans `main` | PR #1 approuvée par un autre membre, fusionnée (`3cc2fc9`) |
| CI verte sur `main` | Run `39425824042` : lint, tests, build, test de l'image et push réussis |
| Protection de `main` | Ruleset « Protect main » actif : 1 approbation, checks « Lint et tests » et « Build et publication GHCR » requis, branche à jour, ni suppression ni force-push |
| Revue croisée entre équipes | À réaliser par une autre équipe ; aucune revue humaine simulée |

Le test cassé local ne modifie pas la suite livrée. La même assertion a ensuite
été temporairement cassée sur la branche distante, commit `6dba0fb`, puis rétablie.
[Exécution rouge vérifiée](https://github.com/Tristan-Bourhis/Projet-M2Ops_La-Gazette/actions/runs/39420416538) :
le job de qualité échoue dans pytest (lint réussi), et le job image est ignoré.
Cette exécution prouve qu'un test cassé empêche effectivement la publication.

[Exécution verte vérifiée](https://github.com/Tristan-Bourhis/Projet-M2Ops_La-Gazette/actions/runs/39420593446)
sur le commit `59bce4d98fb31ce36260af1088ef48be4c3d6893`.
L'étape « Publier la même image sur chaque push » a réussi ; image publiée :

```text
ghcr.io/tristan-bourhis/projet-m2ops_la-gazette:20261020121327-59bce4d
sha256:450e6e4a11befd05c35415aa56958ac2f47e3460c4934ec0da959133f58d791d
```

Les futurs commits produisent leur propre tag ; cette référence conserve la
preuve de validation du code. Aucun déploiement n'a été effectué.

[Exécution verte sur `main`](https://github.com/Tristan-Bourhis/Projet-M2Ops_La-Gazette/actions/runs/39425824042)
après la fusion de la PR #1 ; image publiée :

```text
ghcr.io/tristan-bourhis/projet-m2ops_la-gazette:20261020125352-3cc2fc9
```

Depuis la fusion, le socle est sur la branche par défaut : le clone du README
ne nécessite plus l'option `--branch`. Un clone neuf de `main` reste à
vérifier par la revue croisée.
Le démarrage depuis un clone neuf a été vérifié par l'assistant sur la même
machine, pas par une seconde équipe : la revue croisée humaine reste distincte.

Compose et la CI rejouent la fixture, sans appel réseau ; la lecture réelle
se lance avec l'option `--live`.

La base est fournie et vérifiée par son healthcheck ; les items sont écrits
en JSON, conformément au périmètre du TD 2. Aucun schéma SQL, ordonnanceur,
serveur web ou déploiement de production n'est prétendu livré.
