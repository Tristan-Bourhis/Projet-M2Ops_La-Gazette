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
