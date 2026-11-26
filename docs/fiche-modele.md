# Fiche modèle — thèmes quotidiens de La Gazette

Le modèle regroupe les articles de presse par proximité sémantique. Il fournit un
thème, une probabilité HDBSCAN, des mots-clés et un titre représentatif. Il ne juge
ni la véracité ni l'importance des informations. Les articles isolés restent en bruit.

## Données et méthode

Entrées : titre et extrait des articles RSS nettoyés dans `articles_propres`, sur
24 heures. Les textes intégraux ne sont pas nécessaires. Les sources, doublons et
règles de nettoyage sont décrits dans `docs/donnees.md` et `docs/qualite.md`.
L'empreinte des identifiants et textes et la fenêtre sont enregistrées sur chaque run.

Encodeur : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, révision
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, CPU. UMAP réduit les embeddings en
5 dimensions ; HDBSCAN identifie les groupes ; c-TF-IDF extrait leurs mots-clés.
Graine initiale : 42. Les paramètres exacts en service sont ceux du registre.
Le regroupement est ajusté chaque jour ; l'encodeur préentraîné n'est pas réentraîné.

## Évaluation et décisions

Sans vérité terrain, la silhouette cosinus sur les embeddings (hors bruit), la part
de bruit, les tailles des groupes et la taille relative du plus grand groupe servent
de garde-fous. Les seuils initiaux de `config/evaluation.yaml` sont une proposition
fondée sur la référence du 23/10 : silhouette 0,16, bruit 25 %, 24 thèmes. Ils doivent
être discutés par l'équipe et évoluer par PR, jamais abaissés uniquement pour faire passer un run.

Un dépassement des garde-fous produit `recale`. Deux journées consécutives avec
bruit > 45 % ou silhouette < 0,10 produisent `revue` si les garde-fous passent.
Les deux verdicts bloquent la publication. Une silhouette indéfinie échoue.
La revue conduit à vérifier les sources, le nettoyage et dix affectations, puis,
si nécessaire, à proposer de nouveaux paramètres ou un encodeur dans une PR.
Il n'y a ni optimisation automatique ni expérimentation A/B.

Le responsable de l'équipe qui approuve et fusionne la PR décide de la promotion.
La CI réévalue, applique la bascule et enregistre l'identité GitHub. Les relectures
sont enregistrées séparément avec auteur, date, dix jugements et commentaires ;
elles éclairent la revue de PR, sans être un verrou automatique de promotion.
Aucune relecture humaine réelle n'a été inventée lors de l'implémentation.

## Limites

La silhouette ne prouve pas la cohérence éditoriale. Deux thèmes voisins peuvent
être séparés, des faits divers sans rapport peuvent être réunis, et les mots-clés
peuvent contenir des termes génériques. Dix articles ne constituent pas une étude
statistique. L'échantillon déterministe peut sous-représenter un groupe ou une source.
Un changement de sujets peut expliquer une dérive sans dégradation du modèle.
Moins de 16 articles avec les paramètres initiaux ne permettent pas le regroupement.
La reproductibilité dépend aussi des versions des bibliothèques, tracées sur le run.

## Exploitation

Voir `docs/mlops.md` : registre, promotion, journal et retour arrière. Le retour
arrière rétablit les paramètres et la politique précédents pour le prochain run ;
il ne recalcule pas les thèmes historiques et ne restaure pas le code applicatif.

La relecture humaine de reprise du run 2 a été réalisée par Tristan : huit
affectations validées et deux signalées à revoir (articles 3 et 6). Le dossier exporté
comporte dix articles, leur contexte de groupe et un formulaire vide. Les réponses
sont enregistrées après son retour ; un résultat automatique positif ne doit
pas être présenté comme une validation éditoriale humaine.
