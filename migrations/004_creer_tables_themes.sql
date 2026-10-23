-- Migration 004 : thèmes du jour (TD 5). Cache des embeddings, runs tracés, thèmes et affectations.

-- Un vecteur par (article, modèle) : jamais recalculé ; changer de modèle n'en réutilise aucun.
CREATE TABLE embeddings (
    article_id  text NOT NULL REFERENCES articles_propres (id) ON DELETE CASCADE,
    modele      text NOT NULL,                 -- nom@révision, ex. paraphrase-multilingual-…@86741b4
    vecteur     real[] NOT NULL,
    calcule_le  timestamptz NOT NULL,
    PRIMARY KEY (article_id, modele)
);

-- Un run = une exécution du regroupement : données, paramètres, métriques.
-- termine_le vide : run interrompu, ses thèmes ne comptent pas.
CREATE TABLE runs (
    id             bigserial PRIMARY KEY,
    lance_le       timestamptz NOT NULL,
    termine_le     timestamptz,
    fenetre_debut  timestamptz NOT NULL,       -- articles publiés entre ces deux dates
    fenetre_fin    timestamptz NOT NULL,
    nb_articles    integer NOT NULL,
    hash_entree    text NOT NULL,              -- sha256 des id d'articles triés
    modele         text NOT NULL,
    parametres     jsonb NOT NULL,             -- contenu de config/clustering.yaml
    metriques      jsonb                       -- themes, taille_mediane, part_bruit, silhouette
);
CREATE INDEX runs_termine_le ON runs (termine_le DESC);

CREATE TABLE themes (
    id         bigserial PRIMARY KEY,
    run_id     bigint NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    nom        text NOT NULL,                  -- titre d'article le plus proche du centre
    mots_cles  text[] NOT NULL,                -- c-TF-IDF, du plus au moins discriminant
    taille     integer NOT NULL CHECK (taille > 0)
);
CREATE INDEX themes_run_id ON themes (run_id);

-- Tous les articles du run, bruit compris (theme_id vide).
CREATE TABLE articles_themes (
    run_id       bigint NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    article_id   text NOT NULL REFERENCES articles_propres (id) ON DELETE CASCADE,
    theme_id     bigint REFERENCES themes (id) ON DELETE CASCADE,
    probabilite  real CHECK (probabilite BETWEEN 0 AND 1),
    PRIMARY KEY (run_id, article_id)
);
CREATE INDEX articles_themes_theme_id ON articles_themes (theme_id);

COMMENT ON TABLE embeddings IS 'Cache des vecteurs (TD 5). Supprimés avec l''article (rétention 90 jours).';
COMMENT ON TABLE runs IS 'Exécutions du regroupement, tracées (TD 5). Rétention : 1 an.';
COMMENT ON TABLE themes IS 'Thèmes produits par un run (TD 5).';
COMMENT ON TABLE articles_themes IS 'Affectation article → thème par run ; theme_id vide = bruit.';
