"""Tests sur un vrai PostgreSQL : lancés seulement si TEST_DATABASE_URL est défini."""

import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from gazette.collect import collect_all

psycopg = pytest.importorskip("psycopg")
from psycopg.conninfo import conninfo_to_dict  # noqa: E402

from gazette.db import PostgresSources, connect, migrate, sync_sources  # noqa: E402

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL non défini")
FIXTURE = Path(__file__).parent / "fixtures" / "ouest-france.xml"
MIGRATIONS = Path(__file__).parents[1] / "migrations"
NOW = datetime(2026, 10, 22, 8, tzinfo=UTC)


@pytest.fixture
def conn(tmp_path):
    # Ces tests suppriment les tables : jamais sur la base de la collecte.
    if not conninfo_to_dict(URL).get("dbname", "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL doit viser une base dont le nom finit par _test.")
    with connect(URL) as connection:
        connection.execute(
            "DROP TABLE IF EXISTS rejets, articles_propres, controles_qualite, sources,"
            " schema_migrations"
        )
        yield connection
        connection.execute(
            "DROP TABLE IF EXISTS rejets, articles_propres, controles_qualite, sources,"
            " schema_migrations"
        )


def write_csv(path, url="https://www.ouest-france.fr/rss/une"):
    path.write_text(f"nom,type,acces\nOuest-France,PQR,{url}\n", encoding="utf-8")
    return path


def test_migrations_are_applied_once(conn):
    assert migrate(conn, MIGRATIONS) == [
        "001_creer_table_sources.sql",
        "002_creer_tables_nettoyage.sql",
        "003_alerte_envoyee.sql",
    ]
    assert migrate(conn, MIGRATIONS) == []


def test_state_survives_between_runs(conn, tmp_path):
    migrate(conn, MIGRATIONS)
    sources = write_csv(tmp_path / "sources.csv")
    sync_sources(conn, sources)

    def down(request):
        return httpx.Response(404)

    for _ in range(3):
        collect_all(
            PostgresSources(conn),
            tmp_path / "out",
            transport=httpx.MockTransport(down),
            clock=lambda: NOW,
            sleep=lambda _s: None,
        )
    row = conn.execute("SELECT * FROM sources").fetchone()
    assert (row["actif"], row["echecs_consecutifs"]) == (False, 3)
    assert PostgresSources(conn).sleeping_sources() == ["Ouest-France"]

    # Corriger l'URL dans le CSV réveille la source.
    sync_sources(conn, write_csv(sources, "https://www.ouest-france.fr/rss/nouveau"))
    row = conn.execute("SELECT * FROM sources").fetchone()
    assert (row["actif"], row["echecs_consecutifs"]) == (True, 0)
    assert PostgresSources(conn).sleeping_sources() == []


def test_source_removed_from_csv_is_disabled_not_asleep(conn, tmp_path):
    migrate(conn, MIGRATIONS)
    sources = write_csv(tmp_path / "sources.csv")
    sync_sources(conn, sources)
    sources.write_text("nom,type,acces\nLe Monde,PQN,https://www.lemonde.fr/rss/une.xml\n")
    sync_sources(conn, sources)
    actifs = {row["nom"]: row["actif"] for row in conn.execute("SELECT nom, actif FROM sources")}
    assert actifs == {"Ouest-France": False, "Le Monde": True}
    assert PostgresSources(conn).sleeping_sources() == []


def test_success_is_recorded(conn, tmp_path):
    migrate(conn, MIGRATIONS)
    sync_sources(conn, write_csv(tmp_path / "sources.csv"))

    def ok(request):
        return httpx.Response(200, content=FIXTURE.read_bytes(), headers={"ETag": '"v1"'})

    collect_all(
        PostgresSources(conn),
        tmp_path / "out",
        transport=httpx.MockTransport(ok),
        clock=lambda: NOW,
        sleep=lambda _s: None,
    )
    row = conn.execute("SELECT * FROM sources").fetchone()
    assert row["derniere_reussite"] == NOW
    assert row["etag"] == '"v1"'


def test_clean_store_on_postgres(conn, tmp_path):
    import json
    from datetime import timedelta

    from gazette.clean import process
    from gazette.db import PostgresCleanStore

    migrate(conn, MIGRATIONS)
    raw = tmp_path / "articles_bruts" / "le-monde"
    raw.mkdir(parents=True)
    for id_, titre in [("a1", "Tempête Austen : dix départements en vigilance"), ("a2", "Vidéo")]:
        item = {
            "id": id_,
            "source": "Le Monde",
            "lien": f"https://e.fr/{id_}",
            "titre": titre,
            "resume": "x",
            "publie_le": (NOW - timedelta(hours=1)).isoformat(),
            "recupere_le": NOW.isoformat(),
            "rubrique": None,
        }
        (raw / f"{id_}.json").write_text(json.dumps(item), encoding="utf-8")
    store = PostgresCleanStore(conn)
    result = process(store, tmp_path / "articles_bruts", tmp_path / "r", ["Le Monde"], NOW)
    assert (result["gardes"], result["rejetes"]) == (1, 1)
    assert conn.execute("SELECT regle FROM rejets").fetchone()["regle"] == "R06_titre_vide"
    assert store.alerted_checks() == set()
    assert process(store, tmp_path / "articles_bruts", tmp_path / "r", [], NOW)["entres"] == 0
