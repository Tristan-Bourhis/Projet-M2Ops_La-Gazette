ALTER TABLE runs ADD COLUMN evaluation jsonb;
ALTER TABLE runs ADD COLUMN publie boolean NOT NULL DEFAULT false;
UPDATE runs SET publie = true WHERE termine_le IS NOT NULL;
CREATE TABLE versions_modele (
    version text PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES runs(id),
    statut text NOT NULL CHECK (statut IN ('candidat', 'production', 'archive')),
    parametres jsonb NOT NULL,
    politique jsonb NOT NULL,
    promue_le timestamptz,
    par_qui text
);
CREATE UNIQUE INDEX une_production ON versions_modele(statut) WHERE statut = 'production';
CREATE TABLE promotions_modele (
    id bigserial PRIMARY KEY,
    precedente text REFERENCES versions_modele(version),
    version text NOT NULL REFERENCES versions_modele(version),
    action text NOT NULL CHECK (action IN ('promotion', 'rollback')),
    par_qui text NOT NULL,
    execute_le timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE relectures_modele (
    id bigserial PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES runs(id),
    par_qui text NOT NULL,
    resultat jsonb NOT NULL,
    execute_le timestamptz NOT NULL DEFAULT now()
);
