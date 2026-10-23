# MLOps : thèmes du jour (TD 5)

Chaque matin, les articles propres des dernières 24 h sont regroupés en thèmes. Chaque
exécution (un **run**) est tracée : données, paramètres, métriques, artefacts. On sait
toujours quel run a produit les thèmes en base.

## Le pipeline

Flow Prefect `themes-du-jour`, déploiement `themes-6h30`, **tous les jours à 6 h 30
(Europe/Paris)**, servi par le conteneur `collecteur` à côté de la collecte (30 min) :

1. **nettoyage** : rattrape les derniers articles bruts (idempotent) ;
2. **fenêtre** : articles de `articles_propres` publiés dans les 24 h précédant le run ;
3. **embeddings** : titre + extrait → vecteur ; seuls les absents du cache sont calculés
   (table `embeddings`) ;
4. **regroupement BERTopic** : UMAP (voisinages en cosinus, 384 → 5 dimensions, graine fixée)
   puis HDBSCAN ; les articles isolés restent hors thème (bruit) ;
5. **nommage** : mots-clés c-TF-IDF + titre de l'article le plus proche du centre du groupe ;
6. **stockage** : `runs`, `themes`, `articles_themes`, et un résumé en artefact Prefect.

Le run est inséré **avant** le calcul : s'il échoue, il reste en base avec `termine_le` vide
et ses thèmes ne comptent pas. Moins de 16 articles sur 24 h : le run s'arrête (UMAP ne
peut pas travailler sur si peu de points).

Code : `src/gazette/embed.py`, `src/gazette/themes.py`, `src/gazette/flows.py`.
Pour lancer un run sans attendre 6 h 30 : bouton *Run* du déploiement dans Prefect, ou
`docker compose exec collecteur prefect deployment run 'themes-du-jour/themes-6h30'`.

## Modèle et paramètres

Tout est dans **`config/clustering.yaml`**, copié tel quel dans `runs.parametres` à chaque run.

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| Modèle | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | modèle multilingue par défaut de BERTopic ; léger (118 M paramètres, 384 dimensions), CPU |
| Révision | `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` | version figée : intégrée à l'image Docker au build, aucun téléchargement au run (`HF_HUB_OFFLINE=1`) |
| `graine` | 42 | UMAP est aléatoire : même graine + mêmes articles = mêmes thèmes |
| `umap` | 15 voisins, 5 dimensions, cosinus | réduit la dimension : HDBSCAN seul sur 384 dimensions met ~70 % des articles en bruit |
| `hdbscan.min_cluster_size` | 5 | taille minimale d'un thème |
| `hdbscan.min_samples` | 5 | exigence de densité : plus haut = plus de bruit |
| `mots_cles` | 5 mots, ≥ 3 lettres, mots vides français + mois et jours | sans eux, « de », « 17 », « octobre » sortaient comme mots-clés |

**Changer un paramètre** : modifier le YAML, reconstruire l'image
(`docker compose up -d --build collecteur`). Les runs suivants portent la nouvelle valeur.
**Changer de modèle** : modifier `nom` et `revision` ; le cache est indexé par
`nom@revision`, les anciens vecteurs ne sont jamais réutilisés.

## Ce qu'un run trace

| Demandé par le TD | Où |
|---|---|
| Fenêtre de données | `runs.fenetre_debut`, `fenetre_fin`, `nb_articles` |
| Hash de l'entrée | `runs.hash_entree` : sha256 des id d'articles triés (mêmes articles = même hash) |
| Modèle et version | `runs.modele` (`nom@revision`) |
| Paramètres | `runs.parametres` (jsonb, contenu du YAML) |
| Métriques | `runs.metriques` : `themes`, `taille_mediane`, `part_bruit`, `silhouette` (cosinus, calculée sans le bruit) |
| Artefacts | `themes` (nom, mots-clés, taille), `articles_themes` (affectation et probabilité ; `theme_id` vide = bruit) |
| Durée | `termine_le - lance_le` |

## Où regarder

**Prefect** (http://127.0.0.1:4200) : *Deployments* → `themes-6h30` → un run → onglet
*Artifacts* : `themes-du-jour` (tableau des thèmes) et `metriques-themes`.

**PostgreSQL** (`docker compose exec postgres psql -U gazette -d gazette`) :

```sql
-- Les derniers runs, leur durée et leurs métriques
SELECT id, lance_le, termine_le - lance_le AS duree, nb_articles, left(hash_entree, 12) AS hash,
       metriques
FROM runs ORDER BY id DESC LIMIT 10;

-- Les thèmes en base et le run qui les a produits (dernier run terminé)
SELECT t.taille, t.mots_cles, t.nom, r.id AS run_id, r.modele, r.parametres
FROM themes t JOIN runs r ON r.id = t.run_id
WHERE r.id = (SELECT max(id) FROM runs WHERE termine_le IS NOT NULL)
ORDER BY t.taille DESC;

-- Les articles d'un thème
SELECT a.source, a.titre, x.probabilite
FROM articles_themes x JOIN articles_propres a ON a.id = x.article_id
WHERE x.theme_id = :theme_id ORDER BY x.probabilite DESC;

-- Les articles en bruit d'un run
SELECT a.source, a.titre FROM articles_themes x JOIN articles_propres a ON a.id = x.article_id
WHERE x.run_id = :run_id AND x.theme_id IS NULL;
```

## Choix de l'algorithme

Comparaison sur 358 articles réels le 23/10 (`explorations/comparer_regroupements.py`,
sortie dans `explorations/sorties/comparaison-2026-10-23.md`), mêmes embeddings pour tous :

| | Thèmes | Taille médiane | Bruit | Silhouette |
|---|---|---|---|---|
| k-means (k = 15) | 15 | 21 | 0 % | 0,09 |
| HDBSCAN seul | 5 | 7 | 68 % | 0,21 |
| **BERTopic** | **17** | 12 | 34 % | 0,15 |

k-means impose k et force chaque article dans un groupe (groupes hétérogènes) ; HDBSCAN seul
met deux tiers des articles en bruit (en 384 dimensions, les distances se ressemblent toutes) ;
BERTopic donne des thèmes cohérents. Choix conforme au cadrage (`docs/cadrage.md`).

## Thèmes du jour : run de référence

**Run 5**, 23/10/2026 à 15:56 (Paris), lancé depuis Prefect (déploiement `themes-6h30`),
9,2 s. 396 articles (hash `7fab6c49af01…`), **24 thèmes**, taille médiane 10, bruit 25 %,
silhouette 0,16. Le run 4, sur les mêmes articles, donne exactement les mêmes métriques.
Les runs 1 à 3 sont des essais de développement lancés hors pipeline.

| Taille | Mots-clés | Titre le plus central |
|---|---|---|
| 35 | france, montpellier, monde, cévennes, critérium | Tour de France 2027 : « Ce n'est pas une stratégie anti-Pogacar »… |
| 21 | trappes, yvelines, fusillade, homme, rue | Fusillade mortelle à Trappes : le parquet national antiterroriste se saisit des faits |
| 20 | commerçants, police, manifestation, violences, lors | Des émeutes du 17 octobre à la crise de régime |
| 20 | tempête, austen, départements, électricité, foyers | Tempête Austen : 23 départements en vigilance orange |
| 18 | prison, bouygues, olivier, sursis, jugé | Violences du 17 octobre : le préfet veut expulser un pilleur |
| 18 | macron, nuñez, emmanuel, mobilisation, élysée | Mouvement social : Laurent Nuñez annonce un dispositif « extrêmement important » |
| 16 | ukraine, trump, donald, guerre, poutine | Ukraine : la petite phrase de l'émissaire de Trump sur Poutine |
| 12 | artificielle, intelligence, utilisateurs, internes, google | Fédération de tir de nouveau victime d'un piratage |
| 12 | manifestations, rassemblements, préfète, manifestation, marge | Manifestation du 24 octobre : des interdictions dans les grandes villes |
| 12 | budget, sociale, gouvernement, rejeté, produits | Budget 2027 : la taxe sur les produits sucrés rejetée |
| 11 | pro, vie, occitanie, toulouse, nolistra | Nos 10 fromageries préférées à Paris |
| 11 | présidentielle, lisnard, sondage, pen, droite | Sondage présidentielle : Mélenchon reprend l'avantage sur Glucksmann |
| 9 | parti, radicaux, gauche, uhroc, crise | Comment lutter contre la polarisation politique en pleine crise sociale |
| 9 | techno, couvre, musique, soirée, festival | Pas de couvre-feu pour la musique à Toulouse |
| 9 | cisjordanie, israéliens, orient, moyen, attaque | Moyen-Orient : « bouclage total » de la Cisjordanie |
| 9 | climatique, tiers, changement, patients, extinction | Les canicules de 2026 ont causé plus de 50 000 morts en Europe |
| 8 | femme, enfermée, balcon, fientes, pigeons | Fientes de pigeons : Dolores, 87 ans, vit les volets fermés |
| 7 | orélien, thélyson, roman, modiano, éléphant | Affaire Thélyson Orélien : l'édition face à l'IA |
| 7 | mirage, près, nancy, âge, décédé | Crash d'un Mirage 2000D près de Nancy |
| 7 | jeunes, léon, xiv, pape, diocèse | Bolloré et Stérin « favorisent la polarisation du catholicisme » |
| 7 | accident, automobiliste, voiture, scooter, gers | Accident de scooter dans le Gers |
| 6 | magnitude, séisme, tibet, morts, région | Séisme de magnitude 7 : au moins 16 morts |
| 6 | trafic, drogue, toulouse, nourrices, longtemps | Trafic de drogue : des « appartements nourrices » à Toulouse |
| 6 | ligue, quelle, suivre, psg, chaîne | Les footballeuses montpelliéraines face au PSG et à l'OL |

Premières remarques (à approfondir au TD 6) : les grands sujets du jour sont bien isolés
(tempête, Trappes, Ukraine, budget, sondages, séisme) ; l'actualité sociale (émeutes,
manifestations, réponse policière, procès) est découpée en 5 thèmes voisins ; certains
groupes sont des fourre-tout (« pro, vie, occitanie » titré par des fromageries parisiennes,
« pigeons » mêlant des faits divers) ; « lors », « quelle », « près » restent des mots-clés
peu discriminants.

## Limites connues

- Image Docker ≈ 3,5 Go : PyTorch CPU (650 Mo), bibliothèques scientifiques, modèle (460 Mo).
  La version CUDA aurait ajouté plusieurs Go.
- Les thèmes dépendent de la base de la machine qui collecte : la machine de référence fait foi.
- Bruit autour de 25 % : non réaffecté (option `reduce_outliers` de BERTopic gardée pour le TD 6).

## Relecture des thèmes (devoir pour le TD 6)

À remplir sur deux journées : ce qui est bon, ce qui est absurde, une hypothèse sur pourquoi.

| Date | Run | Bon | Absurde | Hypothèse |
|---|---|---|---|---|
| | | | | |
