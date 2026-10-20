# La gazette

Pipeline pédagogique de veille de presse régionale et nationale. Le TD 2 pose
le socle : lecture d'un flux RSS/Atom, export JSON, PostgreSQL de développement,
tests et construction/publication d'une image. Le cadrage est dans
[docs/cadrage.md](docs/cadrage.md).

## Démarrer en deux commandes

Prérequis : Git, Docker Engine ou Docker Desktop avec Docker Compose disponible
et moteur démarré. Aucune installation locale de Python ou PostgreSQL nécessaire.

```sh
git clone https://github.com/Tristan-Bourhis/Projet-M2Ops_La-Gazette.git && cd Projet-M2Ops_La-Gazette
bin/dev
```

`bin/dev` construit l'application, attend que PostgreSQL soit sain, lit la fixture
Ouest-France et écrit `output/items.json`. Le traitement termine avec le code 0 ;
ce n'est pas un serveur web. Les deux items fictifs de la fixture ont les champs
`title`, `excerpt`, `link`, `date` (UTC).

```sh
bin/test                       # lint, format et tests dans Docker, sans réseau à l'exécution
docker compose up --build      # variante directe : app ponctuelle + PostgreSQL
docker compose logs app
docker compose down            # arrête les services ; conserve les données
```

Le JSON produit par `docker compose up` est dans le volume `gazette-output`.
Pour le copier vers l'hôte :

```sh
mkdir -p output
docker compose run --rm --no-deps app cat /data/items.json > output/items.json
```

PostgreSQL est provisionné pour les prochains TD ; le TD 2 écrit uniquement
du JSON et n'utilise pas encore la base. Aucun port PostgreSQL n'est exposé.
Les identifiants présents dans Compose sont réservés au développement local.
Les volumes persistent ; `docker compose down --volumes` les supprime.

## Première source et conditions d'utilisation

La source sélectionnée est **Ouest-France**, référencée dans `sources.csv`.
La [fixture](tests/fixtures/README.md) est issue d'une lecture ponctuelle :
structure et dates conservées, contenus et liens d'articles remplacés par des
exemples fictifs. Le démarrage et la CI la rejouent sans contacter l'éditeur.

Pour lire le flux réel, reconstruire l'image puis exécuter :

```sh
docker compose build app
docker compose run --rm app python -m gazette --live --source Ouest-France
```

Les redirections et erreurs HTTP font échouer la lecture ; aucun
contournement n'est effectué. La lecture est limitée à 2 Mo et les extraits
à 280 caractères ; aucun article lié n'est téléchargé. Cette limite de longueur
est un choix technique, pas une permission juridique de reproduction.
Les dates absentes, liens invalides et doublons sont écartés. En mode réseau,
les publications futures ou âgées de 24 h ou plus sont également écartées.
Une erreur ou un flux sans item exploitable conserve le précédent JSON.

## Développement et CI

```text
src/gazette/          CLI, récupération HTTP, parseur, export JSON
tests/fixtures/      exemple RSS normalisé et provenance
tests/              tests du parseur, du réseau simulé et de la CLI
infra/              documentation de l'environnement Compose
docs/               cadrage, architecture, stratégie CI et validation
bin/                dev, test et contrôles communs à la CI
.github/workflows/   lint → tests → build → publication GHCR
```

Chaque push déclenche la CI et, si les contrôles passent, publie l'image
`ghcr.io/tristan-bourhis/projet-m2ops_la-gazette:YYYYMMDDHHMMSS-sha`.
L'heure du tag est UTC et `sha` correspond aux sept premiers caractères du commit.
Les pull requests construisent et testent également l'image, sans publication.
Il n'y a pas de déploiement automatique ni de tag mutable `latest`.
Le workflow utilise `GITHUB_TOKEN` avec `packages: write`, sans secret à ajouter.
La politique du dépôt ou de l'organisation doit permettre cette publication.
Le registre peut exiger une connexion pour tirer une image privée.

Les versions Python directes et transitives sont figées dans `requirements.lock`
et `requirements-dev.lock`. Les fichiers `.in` décrivent les dépendances directes.
Python 3.12 est commun à Docker et à la CI.

Pour contribuer : [CONTRIBUTING.md](CONTRIBUTING.md).
Stratégie : [docs/ci-cd.md](docs/ci-cd.md).
Validation et limites : [docs/validation-td2.md](docs/validation-td2.md).
