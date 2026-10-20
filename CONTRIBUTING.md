# Contribuer à La gazette

`main` doit rester déployable : aucun travail direct dessus. Créer une branche
par sujet : `feat/td2-socle`, `fix/parser-date`, `docs/cadrage`.
Ouvrir une pull request ciblée vers `main` et expliquer le problème, le changement
et les vérifications réalisées.

Utiliser des commits `type: description` : `feat`, `fix`, `test`, `docs`, `ci`,
`chore`. Exemple : `feat: ajouter le socle Docker et la collecte RSS`.
Ne pas versionner de secrets, fichiers `.env`, résultats de collecte ou articles
complets. Les fixtures de presse sont minimisées et leurs contenus remplacés par
des exemples fictifs si les droits de redistribution ne sont pas établis.

Avant une PR, lancer `bin/test` puis `bin/dev`. Un autre membre de l'équipe
relit les changements et les résultats de CI. Un mainteneur disposant des droits
d'écriture fusionne après cet accord et une CI verte ; l'auteur ne valide pas
seul sa propre PR. Privilégier le squash merge, puis supprimer la branche.

La protection de `main` doit imposer une approbation et les contrôles
« Lint et tests » et « Build et publication GHCR ». Cette convention n'active
pas à elle seule les règles GitHub : leur état réel est indiqué dans
`docs/validation-td2.md`. Toute configuration d'infrastructure ultérieure doit
être décrite et versionnée avant son application.

Pour la revue croisée, une autre équipe clone la branche et lance `bin/dev`
sur sa propre machine, puis `bin/test`. Elle consigne OS, version Docker,
résultat et éventuel bug dans la PR. Ne pas déclarer cette revue faite avant
son retour.

## Mise à jour des dépendances

Modifier les fichiers `requirements*.in`, résoudre les dépendances avec
Python 3.12 dans un conteneur propre, puis enregistrer les versions exactes de
tous les paquets dans les deux fichiers `.lock`. Réexécuter `bin/test` et
`bin/dev` avant de proposer la mise à jour. Les changements de version restent
dans une PR dédiée.
