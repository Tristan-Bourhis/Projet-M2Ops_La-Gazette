"""PostgreSQL : migrations versionnées et état des sources (table sources)."""

import csv
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from gazette.collect import SLEEP_AFTER_FAILURES, Source

MIGRATIONS = Path("migrations")
MIGRATION_LOCK = 20261022  # verrou : deux conteneurs ne migrent jamais en même temps


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=True, row_factory=dict_row)


def migrate(conn: psycopg.Connection, directory: Path = MIGRATIONS) -> list[str]:
    """Applique, dans l'ordre et une seule fois, les fichiers NNN_*.sql."""
    conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK,))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY, appliquee_le timestamptz NOT NULL DEFAULT now())"
        )
        applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
        done = []
        for path in sorted(directory.glob("*.sql")):
            if path.name in applied:
                continue
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            done.append(path.name)
        return done
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK,))


class PostgresSources:
    """Même interface que MemorySources, mais l'état survit entre deux collectes."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def active_sources(self) -> list[Source]:
        rows = self.conn.execute("SELECT * FROM sources WHERE actif ORDER BY nom")
        return [Source(**row) for row in rows]

    def record_success(self, nom, at, etag, last_modified):
        self.conn.execute(
            "UPDATE sources SET derniere_reussite = %s, echecs_consecutifs = 0,"
            " etag = %s, last_modified = %s WHERE nom = %s",
            (at, etag, last_modified, nom),
        )

    def record_failure(self, nom):
        row = self.conn.execute(
            "UPDATE sources SET echecs_consecutifs = echecs_consecutifs + 1,"
            " actif = echecs_consecutifs + 1 < %s WHERE nom = %s RETURNING *",
            (SLEEP_AFTER_FAILURES, nom),
        ).fetchone()
        return Source(**row)

    def sleeping_sources(self):
        rows = self.conn.execute(
            "SELECT nom FROM sources WHERE NOT actif AND echecs_consecutifs >= %s ORDER BY nom",
            (SLEEP_AFTER_FAILURES,),
        )
        return [row["nom"] for row in rows]


def sync_sources(conn: psycopg.Connection, csv_path: Path) -> None:
    """sources.csv fait foi pour la liste : ajoute les nouvelles, garde l'état des autres.

    Changer l'URL d'une source dans le CSV la réveille (actif, compteur et ETag remis à zéro).
    Une source retirée du CSV est désactivée, pas supprimée : son historique reste.
    """
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with conn.transaction():
        for row in rows:
            conn.execute(
                """
                INSERT INTO sources (nom, type, url_flux) VALUES (%s, %s, %s)
                ON CONFLICT (nom) DO UPDATE SET
                    type = EXCLUDED.type,
                    url_flux = EXCLUDED.url_flux,
                    actif = sources.actif OR sources.url_flux <> EXCLUDED.url_flux,
                    echecs_consecutifs = CASE WHEN sources.url_flux <> EXCLUDED.url_flux
                        THEN 0 ELSE sources.echecs_consecutifs END,
                    etag = CASE WHEN sources.url_flux <> EXCLUDED.url_flux
                        THEN NULL ELSE sources.etag END,
                    last_modified = CASE WHEN sources.url_flux <> EXCLUDED.url_flux
                        THEN NULL ELSE sources.last_modified END
                """,
                (row["nom"], row["type"], row["acces"].strip()),
            )
        conn.execute(
            "UPDATE sources SET actif = false WHERE NOT (nom = ANY(%s))",
            ([row["nom"] for row in rows],),
        )


class PostgresCleanStore:
    """Tables articles_propres, rejets et controles_qualite (migration 002)."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def known_ids(self):
        rows = self.conn.execute("SELECT id FROM articles_propres UNION ALL SELECT id FROM rejets")
        return {row["id"] for row in rows}

    def recent_keys(self, since):
        rows = self.conn.execute(
            "SELECT id, cle_titre FROM articles_propres WHERE publie_le >= %s", (since,)
        )
        return [(row["id"], row["cle_titre"]) for row in rows]

    def save(self, kept, rejected, at):
        with self.conn.transaction(), self.conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO articles_propres (id, source, lien, titre, extrait, publie_le,"
                " recupere_le, rubrique, cle_titre, brut, traite_le) VALUES (%(id)s, %(source)s,"
                " %(lien)s, %(titre)s, %(extrait)s, %(publie_le)s, %(recupere_le)s, %(rubrique)s,"
                " %(cle_titre)s, %(brut)s, %(traite_le)s) ON CONFLICT (id) DO NOTHING",
                [row | {"traite_le": at} for row in kept],
            )
            cursor.executemany(
                "INSERT INTO rejets (id, source, lien, titre, publie_le, regle, doublon_de, brut,"
                " traite_le) VALUES (%(id)s, %(source)s, %(lien)s, %(titre)s, %(publie_le)s,"
                " %(regle)s, %(doublon_de)s, %(brut)s, %(traite_le)s) ON CONFLICT (id) DO NOTHING",
                [row | {"traite_le": at} for row in rejected],
            )

    def day_rows(self, day):
        rows = self.conn.execute(
            "SELECT id, source, titre, NULL::text AS regle FROM articles_propres"
            " WHERE (traite_le AT TIME ZONE 'UTC')::date = %(day)s"
            " UNION ALL SELECT id, source, titre, regle FROM rejets"
            " WHERE (traite_le AT TIME ZONE 'UTC')::date = %(day)s",
            {"day": day},
        )
        return list(rows)

    def clean_since(self, since):
        rows = self.conn.execute(
            "SELECT id, source, titre, publie_le, traite_le FROM articles_propres"
            " WHERE traite_le >= %s",
            (since,),
        )
        return list(rows)

    def record_checks(self, checks, at):
        with self.conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO controles_qualite (execute_le, controle, ok, valeur, seuil, detail)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                [(at, c.id, c.ok, c.valeur, c.seuil, c.detail) for c in checks],
            )

    def failing_checks(self):
        rows = self.conn.execute(
            "SELECT DISTINCT ON (controle) controle, ok FROM controles_qualite"
            " ORDER BY controle, execute_le DESC, id DESC"
        )
        return {row["controle"] for row in rows if not row["ok"]}
