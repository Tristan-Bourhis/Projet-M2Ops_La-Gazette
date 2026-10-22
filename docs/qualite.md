# Qualité des données

## Dix pollueurs relevés dans les données brutes (22/10/2026)

Relevés à la main dans `articles_bruts/` (476 items, 8 sources), avant d'écrire les règles.

| # | Source | Titre (extrait) | Problème | Règle |
|---|---|---|---|---|
| 1 | DNA | « Vidéo. $content.TitleNoTags » | gabarit de CMS non remplacé | R05 |
| 2 | La Dépêche | « La Dépêche du Midi lance son espace jeux : à vos neurones… » | autopromotion, jeux, publié le 16/10 | R04 |
| 3 | La Dépêche | « Wanted : … le nouveau jeu lancé sur M6 ce jeudi soir » | programme TV | R03 |
| 4 | Ouest-France | « « Harceleurs » : le téléfilm de France 2… » | programme TV | R03 |
| 5 | Midi Libre | « Appel à témoignages : Vous êtes à découvert ? » | pas un article | R10 |
| 6 | La Croix | « Feu, foi, baptême. Commentaire de l'Évangile du jeudi » | rubrique de service quotidienne | R10 |
| 7 | Midi Libre | « … L'essentiel de l'actu en région » | récapitulatif d'autres articles | R10 |
| 8 | La Dépêche | « CARTE. Prix des carburants : tarifs, stations… » | page de service, publiée le 17/09 | R09 |
| 9 | Le Monde | « Le virus Shamonda détecté pour la première fois chez un humain… » | identique au titre de Libération : dépêche reprise | R11 |
| 10 | Libération | « Le prix Sakharov 2026 attribué à la Cour pénale internationale… » | même titre qu'Ouest-France à deux mots près | R12 |

## Règles d'exclusion

Code : `src/gazette/rules.py` ; tests : `tests/test_rules.py` (un exemple réel par règle).
Un item est écarté par la **première** règle qui le reconnaît, dans cet ordre. Les rejetés
vont dans la table `rejets` avec l'identifiant de la règle.

| Règle | Ce qu'elle écarte | Pourquoi | Exemple |
|---|---|---|---|
| `R01_publi` | publi-reportage, contenu sponsorisé, bons plans (titre ou URL) | ce n'est pas du journalisme | URL en `/publi-reportage/` |
| `R02_horoscope` | horoscope, astrologie | hors actualité | « Horoscope du jeudi » |
| `R03_programme_tv` | téléfilm, programme TV, « sur M6 ce soir » | promotion, pas un sujet | pollueurs 3, 4 |
| `R04_jeux` | jeux-concours, espace jeux, quiz, mots croisés | hors actualité | pollueur 2 |
| `R05_titre_gabarit` | titre resté en gabarit (`$content.…`, `{{ }}`) | titre inutilisable | pollueur 1 |
| `R06_titre_vide` | titre absent ou de moins de 3 mots | rien à afficher | « Vidéo » |
| `R07_encodage` | encodage encore cassé après réparation (`Ã©`, `â€`) | illisible | « lâ€™essence » |
| `R08_date_future` | publié dans le futur (tolérance 10 min) | date fausse | +1 jour |
| `R09_perime` | sans date ou publié il y a plus de 24 h | contrainte « moins de 24 h » | pollueur 8 |
| `R10_non_editorial` | appel à témoignages, commentaire de l'Évangile, « l'essentiel de l'actu » | pas un article | pollueurs 5, 6, 7 |
| `R11_doublon_exact` | même titre normalisé qu'un article gardé (48 h) | dépêche reprise à l'identique | pollueur 9 |
| `R12_doublon_approche` | titre à Jaccard ≥ 0,8 d'un article gardé (48 h) | même titre à deux mots près | pollueur 10 |

Doublons : on garde le **plus ancien** ; le rejet garde `doublon_de` (l'id de l'original), donc
l'édition pourra citer toutes les sources d'une même dépêche.

## Ajustements

| Date | Règle | Changement | Pourquoi |
|---|---|---|---|
| 22/10 | `R01_publi` | ne lit plus l'extrait, seulement titre et URL | faux positif : « En partenariat avec les Restos du Cœur » dans un vrai article politique (La Dépêche, débat LCI) |
| 22/10 | `R05` avant `R06` | gabarit testé avant « titre trop court » | « Vidéo. $content.TitleNoTags » était compté comme titre vide : le rapport disait mal pourquoi |

## Résultat sur les données du 22/10

476 entrés, 398 gardés, 78 rejetés (16 %) : `R09_perime` 67, `R10_non_editorial` 4,
`R03_programme_tv` 2, `R12_doublon_approche` 2, `R04_jeux` 1, `R05_titre_gabarit` 1,
`R11_doublon_exact` 1. Le gros des rejets vient de La Dépêche et Midi Libre, dont les flux
de 100 items remontent au-delà de 24 h.

## Contrôles de données (après chaque passage)

Code : `src/gazette/quality.py`. Ce sont des faits vérifiés sur les vraies données, pas des
tests de code. **Assertions maison plutôt que Pandera** : quatre faits simples, sans
dépendance de plus ; Pandera, prévu au cadrage, se justifierait avec un schéma plus riche.

| Contrôle | Fait vérifié | Seuil |
|---|---|---|
| `C01_aucune_date_future` | aucun article propre (24 h) daté dans le futur | 0 |
| `C02_aucun_titre_vide` | aucun article propre (24 h) sans titre | 0 |
| `C03_taux_rejet_par_source` | rejet ≤ 80 % par source sur la journée (dès 10 items) | 0,8 |
| `C04_aucune_source_muette` | chaque source de `sources.csv` a un article propre depuis 12 h | 0 |

Chaque passage : résultats dans la table `controles_qualite`, logs JSON, et artefacts
Prefect (rapport, contrôles, métriques). Quand un contrôle **passe** au rouge, une alerte
part vers le webhook `ALERT_WEBHOOK_URL` (Discord ou Slack) ; pas de nouvelle alerte tant
qu'il reste rouge. Le run Prefect passe aussi en échec.

## Alerte déclenchée pour de vrai (22/10/2026)

- 14:48 : alerte de test reçue dans le salon Discord de l'équipe (`--alerte-test`).
- Puis vrai déclenchement : un article propre passé à une date future en base,
  Quick run → `C01_aucune_date_future` en échec, run Prefect rouge, message reçu :
  « La gazette : 1 contrôle(s) qualité en échec • C01_aucune_date_future : 1da5eedd8966 ».
- Date remise en état, run suivant vert. Une seule alerte envoyée : pas de répétition
  tant que le contrôle reste rouge.