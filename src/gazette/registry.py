"""Registre PostgreSQL : bascules atomiques et journal conservé."""

import hashlib
import json

from psycopg.types.json import Jsonb

LOCK = 20261126


def version_key(config, policy):
    return hashlib.sha256(json.dumps([config, policy], sort_keys=True).encode()).hexdigest()


class Registry:
    def __init__(self, conn):
        self.conn = conn

    def production(self):
        row = self.conn.execute(
            "SELECT * FROM versions_modele WHERE statut = 'production'"
        ).fetchone()
        if not row:
            raise ValueError("Aucune production : évaluer puis promouvoir une première version.")
        return row

    def candidate(self, run_id, config, policy):
        run = self.conn.execute("SELECT * FROM runs WHERE id = %s", (run_id,)).fetchone()
        if (
            not run
            or not run["termine_le"]
            or not run["evaluation"]
            or run["evaluation"]["verdict"] != "candidat"
            or run["evaluation"]["politique"] != policy
            or {k: v for k, v in run["parametres"].items() if k != "bibliotheques"} != config
        ):
            raise ValueError("Run incomplet, recalé ou paramètres différents.")
        version = version_key(config, policy)
        self.conn.execute(
            "INSERT INTO versions_modele(version, run_id, statut, parametres, politique)"
            " VALUES (%s, %s, 'candidat', %s, %s) ON CONFLICT (version) DO NOTHING",
            (version, run_id, Jsonb(config), Jsonb(policy)),
        )
        return version

    def activate(self, version, actor, action="promotion"):
        if not actor.strip():
            raise ValueError("Auteur requis.")
        with self.conn.transaction():
            self.conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
            current = self.conn.execute(
                "SELECT version FROM versions_modele WHERE statut = 'production'"
            ).fetchone()
            old = current["version"] if current else None
            if action == "rollback":
                previous = self.conn.execute(
                    "SELECT precedente FROM promotions_modele ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not previous or not previous["precedente"]:
                    raise ValueError("Aucune version précédente.")
                version = previous["precedente"]
            target = self.conn.execute(
                "SELECT * FROM versions_modele WHERE version = %s", (version,)
            ).fetchone()
            if not target:
                raise ValueError("Version inconnue.")
            if old == version:
                return version
            self.conn.execute(
                "UPDATE versions_modele SET statut = 'archive' WHERE statut = 'production'"
            )
            self.conn.execute(
                "UPDATE versions_modele SET statut = 'production', promue_le = now(), par_qui = %s"
                " WHERE version = %s",
                (actor, version),
            )
            self.conn.execute(
                "INSERT INTO promotions_modele(precedente, version, action, par_qui)"
                " VALUES (%s, %s, %s, %s)",
                (old, version, action, actor),
            )
        return version

    def review(self, run_id, actor, results):
        run = self.conn.execute("SELECT evaluation FROM runs WHERE id = %s", (run_id,)).fetchone()
        evaluation = (run or {}).get("evaluation") or {}
        expected = {r["article_id"] for r in evaluation.get("echantillon", [])}
        if (
            not actor.strip()
            or len(expected) != 10
            or len(results) != 10
            or {r.get("article_id") for r in results} != expected
            or any(
                type(r.get("bien_place")) is not bool or not r.get("commentaire") for r in results
            )
        ):
            raise ValueError("Relecture : dix articles, booléen et commentaire requis.")
        self.conn.execute(
            "INSERT INTO relectures_modele(run_id, par_qui, resultat) VALUES (%s, %s, %s)",
            (run_id, actor, Jsonb(results)),
        )
