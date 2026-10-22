# Dictionnaire de données

## Articles bruts (bronze) : `articles_bruts/`

Un fichier JSON par article, tel que reçu du flux, rangé par source :
`articles_bruts/<source>/<id>.json` (ex. `articles_bruts/le-monde/0f6f27….json`).
Écrit par `src/gazette/collect.py`, jamais modifié ni réécrit ensuite.

| Champ | Type | Sens | Exemple |
|---|---|---|---|
| `id` | texte (64 hex) | SHA-256 de `source` + `lien` normalisé ; nom du fichier | `0f6f2745…` |
| `source` | texte | nom de la source, identique à `sources.csv` | `Le Monde` |
| `lien` | URL | lien de l'article (`<link>`, ou `<guid>` si c'est une URL) | `https://www.lemonde.fr/…` |
| `titre` | texte ≤ 500 | titre, balises HTML retirées | `L’Omnibus X, cheval de Troie…` |
| `resume` | texte ≤ 500 | `<description>` (RSS) ou `<summary>` (Atom), sans HTML | `La Commission européenne…` |
| `publie_le` | date ISO UTC ou `null` | `pubDate`, `dc:date`, `published` ou `updated` | `2026-10-22T03:45:10Z` |
| `recupere_le` | date ISO UTC | moment de notre collecte | `2026-10-22T08:09:45Z` |
| `rubrique` | texte ou `null` | première `<category>` du flux | `Sport` |
| `payload` | objet | balises autorisées, telles que reçues (2 000 car. max par valeur) | `{"pubDate": "Thu, 22 Oct…"}` |

**Clé naturelle et doublons.** Un article est identifié par `(source, lien)`. Le lien est
normalisé avant calcul de l'`id` : domaine en minuscules, ancre `#…` et paramètres `utm_*`
retirés. Le fichier est créé seulement s'il n'existe pas (`os.link`, atomique) : deux
passages de collecte ne créent aucun doublon.

**Bornage.** `payload` ne contient que la liste blanche : RSS `title, link, description,
pubDate, guid, category, dc:date` ; Atom `title, id, published, updated, summary, category,
link`. Jamais `content:encoded` (texte intégral), images (`enclosure`, `media:*`), auteurs
ni commentaires. Un item sans lien exploitable est ignoré et compté dans `ignores`.
Aucun filtre de fraîcheur à ce stade : il appartient au nettoyage (TD 4).

## Table `sources` (PostgreSQL)

Créée par la migration `migrations/001_creer_table_sources.sql`, appliquée une seule fois
(registre `schema_migrations`). Synchronisée avec `sources.csv` au début de chaque collecte.

| Colonne | Type | Sens |
|---|---|---|
| `nom` | text, clé primaire | nom de la source, identique à `sources.csv` |
| `type` | text, `PQR` ou `PQN` | presse quotidienne régionale ou nationale |
| `url_flux` | text | adresse du flux RSS/Atom |
| `actif` | boolean | `false` = source en sommeil, plus collectée |
| `derniere_reussite` | timestamptz | dernière réponse 200 ou 304 |
| `echecs_consecutifs` | integer ≥ 0 | remis à 0 à chaque réussite ; sommeil à 3 |
| `etag` | text | dernier `ETag` reçu, renvoyé en `If-None-Match` |
| `last_modified` | text | dernier `Last-Modified`, renvoyé en `If-Modified-Since` |

**Réveiller une source en sommeil** : corriger son URL dans `sources.csv`. À la collecte
suivante, elle repart (`actif = true`, compteur et ETag remis à zéro).

## Constats sur les flux (22/10/2026)

| Source | Items par flux | ETag / Last-Modified |
|---|---|---|
| Ouest-France | 10 (≈ 40 min de publication) | non |
| Le Monde | 16 | non |
| Le Figaro, DNA | 20 | non |
| La Croix, Libération | 50 | **oui** (réponses 304) |
| La Dépêche du Midi, Midi Libre | 100 | non |

Conséquence : collecte toutes les 30 minutes, sinon on perd des articles d'Ouest-France.
Seules 2 sources sur 8 permettent d'éviter un téléchargement inutile.
`rubrique` est souvent vide (Le Monde n'envoie pas de `<category>`), alors que la rubrique
figure dans l'URL (`/planete/`) : piste pour le TD 4.

## Articles nettoyés (TD 4) : contrat de données

Migration `migrations/002_creer_tables_nettoyage.sql`. Alimentées à chaque passage par la
tâche `nettoyage-et-controles` (`src/gazette/clean.py`), après la collecte.

**`articles_propres`** : un article gardé. `id` (même id que le brut), `source`, `lien`,
`titre` (non vide), `extrait` (≤ 280 car., HTML et entités retirés, encodage réparé),
`publie_le` (UTC, non nul, moins de 24 h au traitement), `recupere_le`, `rubrique`,
`cle_titre` (titre normalisé, pour les doublons), `brut` (chemin du fichier brut), `traite_le`.

**`rejets`** : mêmes champs d'identification, plus `regle` (`R01_publi`…) et `doublon_de`.

**`controles_qualite`** : historique des contrôles (`controle`, `ok`, `valeur`, `seuil`,
`detail`, `execute_le`).

**Traçabilité** : d'un article propre ou rejeté, `brut` donne le fichier
`articles_bruts/<source>/<id>.json`, et `source` la ligne de `sources.csv`.

**Fraîcheur** : un article propre a moins de 24 h au moment de son traitement ; le
traitement suit la collecte (toutes les 30 min).

**Ce qu'on ne stocke pas** : texte intégral, images, auteurs, commentaires, données
personnelles. L'extrait est borné à 280 caractères.

**Rétention** (règle écrite, purge automatique à mettre en place avec l'infrastructure) :

| Donnée | Durée | Ensuite |
|---|---|---|
| `articles_bruts/` | 90 jours | supprimés |
| `articles_propres`, `rejets` | 90 jours | supprimés |
| `controles_qualite`, `rapports/` | 1 an | supprimés |
| éditions publiées (TD 7) | 1 mois en ligne | archivées en stockage froid |
