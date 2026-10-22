-- Migration 002 : articles nettoyés, rejets et historique des contrôles de qualité.
CREATE TABLE articles_propres (
    id          text PRIMARY KEY,              -- même id que l'item brut (traçabilité)
    source      text NOT NULL,
    lien        text NOT NULL,
    titre       text NOT NULL CHECK (titre <> ''),
    extrait     text NOT NULL CHECK (char_length(extrait) <= 280),
    publie_le   timestamptz NOT NULL,
    recupere_le timestamptz,
    rubrique    text,
    cle_titre   text NOT NULL,                 -- titre normalisé, pour le dédoublonnage
    brut        text NOT NULL,                 -- articles_bruts/<source>/<id>.json
    traite_le   timestamptz NOT NULL
);
CREATE INDEX articles_propres_publie_le ON articles_propres (publie_le);
CREATE INDEX articles_propres_traite_le ON articles_propres (traite_le);

CREATE TABLE rejets (
    id          text PRIMARY KEY,
    source      text NOT NULL,
    lien        text NOT NULL,
    titre       text NOT NULL,
    publie_le   timestamptz,
    regle       text NOT NULL,                 -- R01_publi, R11_doublon_exact…
    doublon_de  text REFERENCES articles_propres (id),
    brut        text NOT NULL,
    traite_le   timestamptz NOT NULL
);
CREATE INDEX rejets_traite_le ON rejets (traite_le);

CREATE TABLE controles_qualite (
    id         bigserial PRIMARY KEY,
    execute_le timestamptz NOT NULL,
    controle   text NOT NULL,
    ok         boolean NOT NULL,
    valeur     double precision NOT NULL,
    seuil      double precision NOT NULL,
    detail     text NOT NULL
);
CREATE INDEX controles_qualite_dernier ON controles_qualite (controle, execute_le DESC);

COMMENT ON TABLE articles_propres IS 'Articles gardés après nettoyage (TD 4). Rétention : 90 jours.';
COMMENT ON TABLE rejets IS 'Articles écartés, avec la règle qui les a écartés. Rétention : 90 jours.';
