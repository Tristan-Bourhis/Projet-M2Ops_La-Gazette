-- Migration 001 : état de chaque source de presse.
CREATE TABLE sources (
    nom                text PRIMARY KEY,
    type               text NOT NULL CHECK (type IN ('PQR', 'PQN')),
    url_flux           text NOT NULL,
    actif              boolean NOT NULL DEFAULT true,
    derniere_reussite  timestamptz,
    echecs_consecutifs integer NOT NULL DEFAULT 0 CHECK (echecs_consecutifs >= 0),
    etag               text,
    last_modified      text
);
COMMENT ON TABLE sources IS
    'Sources RSS/Atom : actif = false après 3 échecs consécutifs (mise en sommeil).';
