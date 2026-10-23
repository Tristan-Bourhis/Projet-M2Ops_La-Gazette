# Comparaison des regroupements — 2026-10-23 12:39 UTC

- Articles : 358 (publiés dans les dernières 24 h)
- Modèle d'embedding : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, texte = titre + extrait
- Paramètres : k-means k=15 ; HDBSCAN et BERTopic taille min=5 ; graine=42
- Silhouette calculée sans le bruit, en distance cosinus (de -1 à 1, plus haut = groupes plus nets)

| Méthode | Thèmes | Taille médiane | Part de bruit | Silhouette | Durée |
|---|---|---|---|---|---|
| k-means | 15 | 21 | 0% | 0.089 | 0.1 s |
| HDBSCAN | 5 | 7 | 68% | 0.205 | 0.0 s |
| BERTopic | 17 | 12 | 34% | 0.146 | 4.2 s |

## k-means

| Taille | Mots-clés | Titre le plus central |
|---|---|---|
| 45 | octobre, violences, centre, pillages, manifestations | Comment en est-on arrivé là ? Des émeutes du 17 octobre à la crise de régime, par Dominique Reynié |
| 39 | octobre, manifestations, samedi, mobilisation, macron | «Est-ce qu’on pourra vraiment manifester tranquillement samedi ?» : à Paris, Emmanuel Grégoire face aux inquiétudes des habitants |
| 37 | octobre, homme, blessé, père, accident | Des victimes carbonisées, une démembrée : au procès de l’assassinat du demi-frère d’Amine Kessaci, le récit d’une violence devenue ordinaire |
| 35 | octobre, quelle, samedi, couvre, heure | Couvre-feu à Toulouse : l'hypercentre interdit d'accès dès cette nuit pour plusieurs soirs, voici les informations à connaître |
| 27 | pigeons, thélyson, orélien, fientes, balcon | En attendant Maurice |
| 27 | rugby, france, club, deuxième, ligne | PORTRAIT. "Les Anglais, on ne les a jamais aimés, on ne les aimera jamais !" Le Toulousain du XIII de France Mathieu Jussaume se confie avant le choc contre l'Angleterre, ce samedi, au Mondial australien |
| 25 | gouvernement, taux, obésité, produits, pro | Le Giec dans l’impasse : comment des pays pétroliers font obstacle aux futures décisions politiques |
| 21 | toulouse, trafic, drogue, ariège, commerçants | Trafic de drogue : "Il existe une vingtaine d'appartements nourrices, des gens postulent..." dans ce quartier de Toulouse, des locataires touchent 500 euros par jour |
| 20 | présidentielle, sondage, budget, comptes, mélenchon | SONDAGE Présidentielle 2026 : Jean-Luc Mélenchon reprend l’avantage sur Raphaël Glucksmann, David Lisnard récolte quelques voix |
| 18 | séisme, magnitude, morts, région, tibet | 50 000 morts en l'espace de quelques semaines : "le pire été jamais enregistré" dans les villes européennes à cause de la canicule en 2026 |
| 16 | austen, tempête, orange, départements, vigilance | Tempête Austen : 23 départements du nord et de l’ouest de la France en vigilance orange, près de 289 000 foyers privés d’électricité |
| 13 | trappes, yvelines, verrière, antiterroriste, homme | EN DIRECT - Fusillade mortelle à Trappes : le tireur voulait faire un «carnage», le parquet national antiterroriste se saisit des faits |
| 12 | âge, décédé, mirage, avion, près | Crash d’un avion militaire Mirage 2000D près de Nancy : le deuxième occupant, un navigateur de 44 ans, est également mort |
| 12 | ukraine, guerre, trump, vladimir, poutine | DIRECT. Guerre en Ukraine : des négociations Russie-Ukraine sous médiation américaine "prévues" à Abou Dhabi en novembre |
| 11 | cisjordanie, israéliens, orient, moyen, attaque | Guerre au Moyen-Orient : cinq Israéliens blessés dans une attaque ; « bouclage total » de la Cisjordanie |

## HDBSCAN

| Taille | Mots-clés | Titre le plus central |
|---|---|---|
| 82 | octobre, manifestations, samedi, mobilisation, trappes | Comment en est-on arrivé là ? Des émeutes du 17 octobre à la crise de régime, par Dominique Reynié |
| 16 | austen, tempête, orange, départements, vigilance | Météo. Tempête Austen : 23 départements en vigilance orange, presque 300 000 foyers privés d'électricité |
| 7 | france, étape, tour, montpellier, mende | Tour de France 2027 : pour l’étape Montpellier-Mende, ce sera 4 300 m de dénivelé, des pentes à 17 %… découvrez le parcours magnifique jusqu’à la montée Jalabert |
| 5 | budget, sécurité, taxe, sucrés, rejeté | Budget 2027 : les députés rejettent une taxe sur les produits sucrés |
| 5 | cisjordanie, israéliens, armée, attaque, cinq | Guerre au Moyen-Orient : cinq Israéliens blessés dans une attaque ; « bouclage total » de la Cisjordanie |

## BERTopic

| Taille | Mots-clés | Titre le plus central |
|---|---|---|
| 29 | france, montpellier, tour, étape, ligne | Tour de France 2027 : "Cette étape est une des plus marquantes", Stéphane Goubert analyse la 14e étape entre Montpellier et Mende |
| 28 | budget, sociale, gouvernement, produits, rejeté | Le Giec dans l’impasse : comment des pays pétroliers font obstacle aux futures décisions politiques |
| 21 | mirage, mort, femme, octobre, cinéma | Crash d’un avion militaire Mirage 2000D près de Nancy : le deuxième occupant, un navigateur de 44 ans, est également mort |
| 17 | tempête, austen, orange, vigilance, départements | Tempête Austen : 23 départements du nord et de l’ouest de la France en vigilance orange, près de 289 000 foyers privés d’électricité |
| 16 | trappes, yvelines, verrière, homme, interpellé | EN DIRECT - Fusillade mortelle à Trappes : le tireur voulait faire un «carnage», le parquet national antiterroriste se saisit des faits |
| 16 | homme, prison, octobre, seine, dépôt | Violences du 17 octobre : dans les Hauts-de-Seine, le préfet veut expulser un pilleur et ses proches de leur logement social |
| 14 | ukraine, trump, guerre, donald, vladimir | Vladimir Poutine est un "humaniste" : la petite phrase de l'émissaire spécial de Trump sur l'Ukraine suscite la colère de Kiev et choque même le camp républicain aux Etats-Unis |
| 12 | fibre, gaudens, usine, excellence, artificielle | 19 000 documents et 64 000 photos piratés : un an après les vols d’armes, la Fédération de tir de nouveau victime d’un piratage |
| 12 | octobre, ville, émeutes, ultragauche, violences | Comment en est-on arrivé là ? Des émeutes du 17 octobre à la crise de régime, par Dominique Reynié |
| 11 | samedi, octobre, manifestations, préfète, mobilisation | Manifestation du 24 octobre : des interdictions dans les grandes villes… Toutes les informations du jeudi 22 octobre |
| 11 | macron, emmanuel, lycéennes, élysée, organisations | EN DIRECT – Mouvement social : Raid, BRI, GIGN... Laurent Nuñez annonce un dispositif «extrêmement important» avec «beaucoup, beaucoup, beaucoup de fermeté» |
| 10 | présidentielle, sondage, mélenchon, lisnard, pen | SONDAGE Présidentielle 2026 : Jean-Luc Mélenchon reprend l’avantage sur Raphaël Glucksmann, David Lisnard récolte quelques voix |
| 9 | parti, sociale, politique, président, sébastien | Partis politiques à Matignon : pas d’union sacrée face aux violences |
| 9 | cisjordanie, moyen, israéliens, orient, attaque | Guerre au Moyen-Orient : cinq Israéliens blessés dans une attaque ; « bouclage total » de la Cisjordanie |
| 8 | pro, occitanie, restaurant, chanvre, zonages | "Un potentiel financier plus élevé" : comment le chanvre est en train de structurer une nouvelle filière agricole et industrielle en Ariège |
| 6 | techno, musique, samedi, end, week | Pas de couvre-feu pour la musique à Toulouse qui va jouer toute la nuit de samedi à dimanche, à la Cave Poésie, pour les 24 heures de l'accordéon |
| 6 | drogue, trafic, toulouse, nourrices, longtemps | Trafic de drogue : "Il existe une vingtaine d'appartements nourrices, des gens postulent..." dans ce quartier de Toulouse, des locataires touchent 500 euros par jour |
