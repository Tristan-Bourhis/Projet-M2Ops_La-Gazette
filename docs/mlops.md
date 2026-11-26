# MLOps : évaluation, registre et promotion

## Pipeline quotidien

À 6 h 30 (Europe/Paris), Prefect nettoie les articles, lit **la ligne production du
registre**, charge son encodeur et ses paramètres, puis regroupe les dernières 24 h.
Aucun changement de fichier YAML ne modifie directement la production.
Sans production initialisée, le pipeline s'arrête explicitement.

Après regroupement : silhouette cosinus hors bruit, nombre et tailles des groupes,
taille médiane, bruit et taille du plus grand groupe / nombre total d'articles.
L'évaluation précède l'écriture des thèmes. Un verdict `recale` ou `revue` conserve
les métriques et diagnostics sur le run et n'insère ni thème ni affectation.
Les runs CI ne publient jamais de thèmes, même acceptés.
Un manque d’articles est enregistré comme `recale`. Un incident de calcul laisse un run inachevé (`termine_le` NULL), donc non publié.

La politique versionnée dans `config/evaluation.yaml` impose : silhouette ≥ 0,05,
bruit ≤ 60 %, au moins deux groupes, médiane ≥ 3 et plus grand groupe ≤ 50 %.
Ces valeurs initiales s'appuient sur le run historique ci-dessous et restent à
valider par l'équipe. La politique est copiée dans le registre et dans chaque évaluation.

La dérive compare les journées UTC : bruit > 45 % ou silhouette < 0,10 pendant
**deux jours consécutifs** déclenche `revue`. Seul le dernier run quotidien terminé
de chaque journée est retenu, y compris les runs recalés. Les essais CI ne comptent
pas ; une journée manquante rompt la séquence. Les garde-fous ont priorité sur
`revue`, mais `evaluation.derive` conserve le signal. La réaction attendue est une
relecture, puis éventuellement une PR de paramètres ou d'encodeur.

## Registre et consultation

Migration `005_cycle_modele.sql`. `versions_modele` contient version (SHA-256 des
paramètres et de la politique), run validant, paramètres, politique, statut,
date et auteur de promotion. Un index garantit une seule production. Les bascules
utilisent une transaction et un verrou PostgreSQL ; `promotions_modele` garde
l'historique, y compris le retour arrière. Une même configuration est idempotente.

```sql
SELECT version, run_id, parametres, politique, promue_le, par_qui
FROM versions_modele WHERE statut = 'production';

SELECT id, fenetre_fin, metriques, evaluation->>'verdict' AS verdict,
       evaluation->'derive' AS derive, publie FROM runs ORDER BY id DESC LIMIT 10;

-- Derniers thèmes réellement publiés, même si un essai CI s'est terminé depuis.
SELECT t.* FROM themes t WHERE run_id =
  (SELECT id FROM runs WHERE publie AND termine_le IS NOT NULL ORDER BY id DESC LIMIT 1);

SELECT * FROM promotions_modele ORDER BY id DESC;
```

## Circuit CI et installation initiale

1. Modifier `config/clustering.yaml` ou `config/evaluation.yaml` dans une PR.
2. Le job **Évaluation hier** construit l'image candidate et exécute
   `python -m gazette.mlops evaluate` sur la journée UTC d'hier. La base CI reçoit
   métriques, échantillon et candidat ; l'artefact `evaluation-hier` garde le résultat.
   Une absence de données suffisantes ou un verdict défavorable fait échouer le job.
3. Le responsable relit l'échantillon et les résultats, puis fusionne la PR.
4. Le push sur la branche par défaut passe les tests et le build. Sur le runner dédié,
   `bin/deploy-model` construit le commit fusionné, le réévalue avec la base locale,
   promeut uniquement s'il passe, puis relance le collecteur. L'auteur GitHub est tracé.
   La réévaluation au merge évite de promouvoir aveuglément un ancien résultat de PR.

**Installation locale de la CI :**

- Un runner GitHub dédié à ce dépôt porte les labels `self-hosted` et
  `gazette-production`. Il tourne sur le poste de collecte, avec accès à Docker.
- Le job `evaluation-local` s'exécute seulement pour les PR internes au dépôt.
  `bin/evaluate-ci` exporte un snapshot transactionnel de la base locale,
  le restaure dans un PostgreSQL jetable sans port exposé, construit le candidat
  puis évalue la journée UTC d'hier. Le clone est détruit même en cas d'échec.
  Aucune connexion CI ne modifie la base de collecte.
- Le job obligatoire `Évaluation hier` échoue si l'évaluation réelle échoue ou
  est ignorée. Une PR externe doit être reprise sur une branche interne après revue.
  Les contributions externes doivent être soumises à l'approbation d'exécution
  des workflows GitHub ; le runner local n'est pas destiné au code non approuvé.
- L'artefact public ne contient que métriques, politique et verdict. Le corpus,
  les titres et l'échantillon restent sur le poste.
- Évaluation et déploiement partagent un groupe de concurrence : une opération
  locale de CI à la fois. Le déploiement s'exécute sur la branche par défaut,
  dans l'environnement `production`.
- Le script utilise `projetm2ops` (surcharge `GAZETTE_PROJECT`) pour retrouver les
  volumes existants. Aucune base distante, aucun secret `EVALUATION_DATABASE_URL`
  et aucune synchronisation nocturne ne sont nécessaires.

Le déploiement conserve les encodeurs dans `/data/modeles` sur le volume du
collecteur. Chaque image y ajoute sa révision embarquée au démarrage, ce qui permet
le retour au précédent encodeur hors ligne. Ne pas supprimer ce volume.
Le changement est actif au démarrage du prochain run, sans relecture du YAML local.
Un run déjà engagé termine avec les paramètres qu'il avait lus.

La bascule du registre est atomique ; la relance Docker est une opération distincte.
Après relance, le script exécute un regroupement réel en relisant la production.
En cas d'échec, il restaure la version et l'image précédentes, avec une action
`compensation-deploiement` tracée, puis fait échouer le job.

## Relecture humaine enregistrée

Chaque run évalué conserve dix articles (ordre déterministe des identifiants), leur
titre, extrait, source et le nom du thème proposé, y compris le bruit. Exporter l'échantillon :

```sql
SELECT evaluation->'echantillon' FROM runs WHERE id = 123;
```

Créer `relecture.json`, un tableau contenant exactement ces dix identifiants :

```json
[{"article_id": "identifiant", "bien_place": true, "commentaire": "Même événement que le thème"}]
```

L'exemple montre un élément ; il en faut dix. Le jugement doit venir d'une personne.
Puis, dans un environnement avec `DATABASE_URL` et le fichier disponible :

```sh
python -m gazette.mlops review --run 123 --actor prenom --file relecture.json
```

La table `relectures_modele` conserve auteur, date et résultats ; une nouvelle
relecture ajoute une trace. Une relecture ne transforme pas un run recalé en candidat.

## Retour arrière

Dans le conteneur en service (adapter le nom de projet Compose si nécessaire) :

```sh
docker compose -p projetm2ops exec collecteur python -m gazette.mlops status
docker compose -p projetm2ops exec collecteur python -m gazette.mlops rollback --actor prenom
docker compose -p projetm2ops exec collecteur python -m gazette.mlops status
# La version précédente est maintenant celle qui était actuelle : retour à l'actuelle.
docker compose -p projetm2ops exec collecteur python -m gazette.mlops rollback --actor prenom
```

Le rollback vise la version précédant la dernière bascule. Sans précédente, il échoue
sans modification. Pour une version précise déjà validée :
`python -m gazette.mlops promote --version SHA256 --actor prenom` (opération de secours).
Le compte ayant accès en écriture au registre est donc un compte privilégié.

Test effectué sur PostgreSQL 17 isolé : `test_registry_roundtrip_and_review` crée
A (graine 42), puis B (43), promeut A puis B, exécute la commande CLI de rollback vers A puis vers B. Les paramètres
et les quatre événements sont vérifiés. Cela valide le registre sur une vraie base,
pas un déploiement distant ni une relecture humaine réelle. Les tables de test sont
nettoyées après le test ; cette procédure fournit une trace durable en exploitation.

## Référence historique TD 5

Les résultats ci-dessous sont antérieurs aux nouveaux seuils et au registre.

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
Les runs 1 à 3 sont des essais de développement lancés hors pipeline. Les runs 4 à 6 ont été
déclenchés à la main **via le déploiement Prefect**, donc par le pipeline ; le premier run
programmé est celui du 24/10 à 6 h 30.

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

## Vérification de cette implémentation

Exécution sur l'image complète et une base PostgreSQL `gazette_test` distincte :
112 tests réussis, aucun ignoré. Après ajout des tests de compensation et de
fenêtre historique, **115 tests réussissent sur GitHub Actions**, aucun ignoré,
en 28,67 secondes ([job de validation](https://github.com/Tristan-Bourhis/Projet-M2Ops_La-Gazette/actions/runs/45839472795/job/139977022981)).
Le test BERTopic de reproductibilité est réellement exécuté, avec deux
avertissements UMAP attendus (graine fixée, calcul séquentiel). Ruff et actionlint passent.
Les tests contrôlent les garde-fous et le rollback CLI ; les runs de reprise
ci-dessous évaluent le vrai corpus. Le raccordement du runner reste à terminer.

## Dossier de relecture locale

Exporter sans préremplir les jugements :

```sh
python -m gazette.mlops review-export --run 123 --file /data/relecture
```

Le dossier contient le titre, l'extrait, la source et le lien de chaque article,
le thème proposé, ses mots-clés et jusqu'à cinq autres titres du groupe.
La personne répond oui/non et justifie chaque réponse. Un cas incertain est
discuté avant de renseigner le booléen définitif. Un export répété ne remplace
pas un fichier de réponses déjà rempli. Les dossiers restent dans `output/`
ou `/data`, hors Git ; aucune relecture réelle n'est produite par les tests.

## Amorçage sur le poste de Tristan — 26 novembre 2026

Les huit flux RSS répondent après reprise, avec 331 articles propres disponibles
à 13 h 41 UTC. Le run 1 évalue les 85 articles disponibles de la journée du 25/11 :
2 thèmes, silhouette 0,073, bruit 16,5 %, plus grand groupe 53/85 = 62,35 %.
Verdict **recale**, aucun thème publié : le garde-fou à 50 % fonctionne sur des
données réelles. Cette reprise ne reconstitue pas tous les articles qui auraient
été collectés si la machine avait tourné toute la veille.
Les seuils ne sont pas abaissés pour faire passer ce run.

Le run 2 d'amorçage couvre les dernières 24 heures, du 25/11 à 13:46:07 UTC au
26/11 à 13:46:07 UTC : **331 articles, 16 thèmes, silhouette 0,15, bruit 16 %,
plus grand groupe 43/331 = 12,99 %**. Verdict `candidat`. Version :
`95275f0d558752a3f9c40cbdb3d3f39905dc03abdccecdd59cd58c614e599f38`.
Aucun paramètre ni seuil n'a été modifié entre les deux évaluations ; seul
le corpus diffère. Dossier humain : `output/relecture-run-2.md`, réponses vierges
`output/reponses-run-2.json`. La version reste candidate en attendant cette revue.

Les déploiements locaux `collecte-toutes-les-30-min` et `themes-6h30` sont servis
par le collecteur permanent. Le passage Prefect de reprise
`ba8ac945-99a7-4668-b9c6-20907d4c3dfc` collecte et nettoie bien, puis termine en
échec sur `C03_taux_rejet_par_source` à cause des anciens fichiers périmés traités
ce jour. Ce signal documenté n'interrompt pas le service ni sa planification.
Tant que la première version n'est pas promue, le regroupement quotidien refuse
de choisir implicitement une configuration : c'est un arrêt explicite prévu.

## Relecture humaine du run 2

Tristan a relu l'échantillon et validé les articles 1, 2, 4, 5, 7, 8, 9 et 10.
Les articles 3 et 6 sont signalés à revoir : l'article 3 porte sur les élections
espagnoles mais reste en bruit ; pour l'article 6, Tristan propose « Insolite ».
Les dix jugements, leurs commentaires et les deux `theme_suggere` sont enregistrés
dans `relectures_modele` avec l'auteur `Tristan`. Le retour original et le formulaire
rempli sont conservés dans `output/`, hors Git. Huit validations sur dix décrivent
cet échantillon, sans constituer une mesure de précision sur tout le corpus.

« Insolite » est pour l'instant une suggestion éditoriale de la relecture. Elle
n'est pas appliquée automatiquement aux articles en bruit. Les thèmes calculés,
les métriques et le verdict historique restent intacts. Une rubrique éditoriale
peut compléter le regroupement, avec une attribution explicite et tracée ; sa
création ne doit pas être présentée comme un groupe découvert par HDBSCAN.

## Mise en service et retour arrière réels — 26 novembre 2026

La version A `95275f0d5587…` a été promue pour l'amorçage local après la relecture
de Tristan. Le flow Prefect `11512db3-750a-484a-a9eb-ca8973f25841` a produit
le run 4, accepté et publié : le pipeline lit effectivement le registre.

Une modification unique et motivée a ensuite été évaluée : UMAP passe de 15
à 10 voisins pour mieux séparer les sujets dans le petit corpus de la veille.
Aucun seuil n'est modifié et aucune recherche automatique n'est exécutée.
Le run 3 sur les mêmes 85 articles d'hier passe : 2 groupes, bruit 32,9 %,
silhouette 0,088 et plus grand groupe 42,35 %. Version B :
`283e984d1bf56dae3a40745054e8de515ddb04ee3fb74cfaa868717761865b1d`.

Le registre local contient les événements 1 à 4 : initialisation A, promotion B,
rollback B→A, rollback A→B. Les commandes CLI ont été exécutées sur la base
de collecte, pas uniquement dans les tests. Le run 5 après restauration de B
a publié 21 thèmes pour 332 articles, silhouette 0,179, bruit 26,2 %, plus grand
groupe 9,04 %. Traces locales : `output/rollback-reel.txt` et
`output/production-apres-rollback.log`. L'amorçage et cette démonstration locale
ne sont pas présentés comme une promotion effectuée par GitHub Actions.

Le script exact du futur job CI (`bin/evaluate-ci`) a été exécuté localement avec
le candidat B : snapshot, restauration isolée, build, évaluation de la veille et
nettoyage réussis. Le résultat reproduit le run 3. Les tests supplémentaires
vérifient la compensation de déploiement et l'absence de textes de presse dans
les logs publics. La validation locale ne remplace pas l'exécution du job
d'évaluation par GitHub Actions.

Le script de déploiement complet a ensuite réussi localement : réévaluation de
la veille (run 6), redémarrage du collecteur et regroupement de vérification
(run 7 : 357 articles, 21 thèmes, verdict candidat et publication effective).
La production active est B. La connexion du plugin GitHub refuse les écritures
avec HTTP 403 ; GitHub CLI a donc été authentifié par le propriétaire et la
[PR nº 9](https://github.com/Tristan-Bourhis/Projet-M2Ops_La-Gazette/pull/9) est ouverte.
La protection `Protect main` impose une approbation indépendante et les contrôles CI.

## Activation GitHub préparée

La configuration suivante est préparée ; son application attend l'autorisation
explicite du propriétaire après le refus du contrôle automatique d'autorisation :

- Runner `gazette-tristan-local`, label `gazette-production`, dans `output/runner`,
  exécuté avec le compte local et son accès Docker. Le service utilisateur systemd
  est décrit par `infra/gazette-runner.service.in` ; démarrage à l'ouverture de session.
- Ajout du contrôle obligatoire `Évaluation hier` à `Protect main`, en conservant
  l'approbation indépendante, les deux contrôles existants et l'interdiction de force push.
- Environnement `production` limité aux branches protégées.
- Approbation d'un mainteneur pour les workflows de toutes les contributions externes
  (`all_external_contributors`). L'évaluation locale reste réservée aux PR internes.

L'auto-merge n'est pas modifié. L'enregistrement du runner et ces réglages restent
distincts de la publication du code. Garder le poste allumé, connecté et la session
ouverte tant que ce poste héberge temporairement la production et le runner.
