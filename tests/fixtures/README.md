# Fixture Ouest-France

Source choisie dans `sources.csv` : `https://www.ouest-france.fr/rss/une`.
Lecture ponctuelle du 20 octobre 2026 à 11:55:26 UTC ; deux entrées retenues.
Structure RSS et dates conservées ; titres, extraits et liens d'articles remplacés
par des exemples fictifs avant inclusion dans Git. Aucun texte intégral,
auteur, image ou commentaire n'est conservé.

Cette fixture est un exemple normalisé issu d'une lecture réelle, pas une copie
intégrale du flux. Elle permet de rejouer le parseur sans réseau et sans publier
les contenus de presse dont les droits ne sont pas établis.
Les assertions portent sur les exemples fictifs et les dates enregistrées.
Le mode fixture ignore volontairement l'âge des articles pour ne pas faire
échouer la CI au bout de 24 h ; le mode `--live` applique le filtre temporel.
