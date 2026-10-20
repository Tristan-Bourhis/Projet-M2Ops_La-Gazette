## 4. Veille technologique et choix techniques

Notre architecture privilégie des technologies gratuites, reproductibles et maintenables, adaptées à un pipeline quotidien automatisé. Pour chaque domaine, deux approches ont été comparées selon leur simplicité, leur fiabilité, leur coût et leur complexité d'exploitation.

| Domaine | Solution retenue | Justification et alternative |
|---|---|---|
| **Collecte** | Python, RSS/Atom, feedparser, httpx | Les flux RSS/Atom permettent de récupérer des métadonnées structurées sans collecter les articles intégraux, sous réserve des conditions des éditeurs. Les API officielles constituent une alternative, mais leur disponibilité et leurs restrictions varient selon les sources. |
| **Orchestration** | Cron | Solution légère et suffisante pour planifier un pipeline quotidien. Prefect offre une meilleure gestion des dépendances, relances et états d'exécution, mais introduit une complexité supplémentaire. |
| **Stockage** | PostgreSQL | Base relationnelle permettant de séparer les données brutes et nettoyées, de garantir leur intégrité et de gérer les accès concurrents. SQLite est plus simple à déployer, mais moins adapté à un stockage centralisé avec plusieurs services. |
| **Regroupement thématique** | Sentence Transformers + scikit-learn | Les embeddings sémantiques associés à un algorithme de clustering permettent de rapprocher des actualités formulées différemment. TF-IDF associé à un clustering est plus léger et plus interprétable, mais moins performant pour certaines similarités sémantiques. |
| **Supervision** | Logs Python, puis Prometheus et Grafana | Les logs facilitent le diagnostic. Prometheus et Grafana permettent de suivre les métriques, visualiser les exécutions et mettre en place des alertes. Une supervision limitée aux logs et scripts de vérification serait plus simple, mais moins complète. |
| **Exécution et infrastructure** | Docker et Docker Compose | Permettent une exécution reproductible des services sur les machines de développement. Kubernetes apporte une orchestration plus avancée, mais serait disproportionné à ce stade. La nécessité d'un outil IaC comme OpenTofu sera étudiée selon l'infrastructure fournie. |

**Outils complémentaires prévus :** Pandas et Pandera pour le nettoyage et les contrôles qualité, MLflow pour le suivi des expérimentations ML, Jinja2 pour la génération HTML, Nginx pour la publication, pytest pour les tests et GitHub Actions pour l'intégration continue.

Ces choix constituent une architecture prévisionnelle qui sera validée progressivement par les expérimentations et l'intégration des composants. Le pipeline devra notamment vérifier la fraîcheur des articles (moins de 24 h) et garantir une publication quotidienne à 7 h.