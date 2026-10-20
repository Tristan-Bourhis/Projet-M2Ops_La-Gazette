## 4. Veille technologique et choix techniques

Notre architecture privilégie des technologies open source, gratuites et reproductibles, adaptées à un pipeline quotidien automatisé. Les solutions ont été comparées selon leur simplicité, leur fiabilité, leur coût et leur maintenabilité.

| Domaine | Solution retenue | Justification et alternative écartée |
|---|---|---|
| **Collecte** | Python, RSS/Atom, feedparser | Collecte standardisée des métadonnées autorisées, sans scraping intégral. Les API officielles sont une alternative, mais leur disponibilité et leurs conditions d'accès varient selon les éditeurs. |
| **Orchestration** | Cron | Planification quotidienne simple et légère. Prefect offre un meilleur suivi des workflows et des relances, mais ajoute une complexité jugée non nécessaire initialement. |
| **Stockage** | PostgreSQL | Stockage persistant des données brutes et nettoyées, avec contraintes d'intégrité et traçabilité. SQLite est plus léger, mais moins adapté aux écritures concurrentes et à une architecture multiserveur. |
| **Regroupement thématique** | Sentence Transformers + scikit-learn | Les embeddings permettent de regrouper des actualités sémantiquement proches malgré des vocabulaires différents. TF-IDF est plus simple et moins coûteux, mais capture moins bien le sens des textes. |
| **Supervision** | Logs Python, puis Prometheus et Grafana | Les logs assurent le diagnostic, Prometheus conserve les métriques et Grafana permet leur visualisation et les alertes. Les logs seuls seraient insuffisants pour une supervision complète. |
| **Infrastructure** | Docker et Docker Compose | Conteneurisation et configuration reproductible des services. OpenTofu permet un provisionnement plus complet, mais son intérêt dépendra de l'infrastructure de production fournie. |

**Outils complémentaires prévus :** MLflow pour le suivi des expérimentations ML, Jinja2 pour la génération HTML, pytest pour les tests et GitHub Actions pour l'intégration continue.

Ces choix constituent une architecture prévisionnelle, qui sera validée progressivement par les expérimentations et l'intégration des composants.