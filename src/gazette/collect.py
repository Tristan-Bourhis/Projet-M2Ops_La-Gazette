"""Collecte multi-sources : polie, avec reprise, mise en sommeil et journaux structurés."""

import argparse
import csv
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx

from gazette.bronze import write_raw_item
from gazette.extract import extract_raw_items
from gazette.feed import MAX_FEED_BYTES, FeedError

logger = logging.getLogger("gazette.collecte")

USER_AGENT = "LaGazette/0.3 (projet etudiant Efrei M2 ; lecture RSS de metadonnees)"
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
BACKOFF_SECONDS = (1, 2, 4)
SLEEP_AFTER_FAILURES = 3
PAUSE_BETWEEN_SOURCES = 1.0
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class TransientError(Exception):
    """Erreur passagère : on réessaie avec une attente croissante."""


class PermanentError(Exception):
    """Erreur durable : inutile de réessayer tout de suite."""


@dataclass
class Source:
    nom: str
    type: str
    url_flux: str
    actif: bool = True
    derniere_reussite: datetime | None = None
    echecs_consecutifs: int = 0
    etag: str | None = None
    last_modified: str | None = None


class SourceRepository(Protocol):
    def active_sources(self) -> list[Source]: ...

    def record_success(
        self, nom: str, at: datetime, etag: str | None, last_modified: str | None
    ) -> None: ...

    def record_failure(self, nom: str) -> Source: ...

    def sleeping_sources(self) -> list[str]: ...


class MemorySources:
    """État des sources en mémoire (tests, et premier jet avant PostgreSQL)."""

    def __init__(self, sources: list[Source]):
        self.sources = {source.nom: source for source in sources}

    @classmethod
    def from_csv(cls, path: Path) -> "MemorySources":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        return cls([Source(row["nom"], row["type"], row["acces"].strip()) for row in rows])

    def active_sources(self) -> list[Source]:
        return [source for source in self.sources.values() if source.actif]

    def record_success(self, nom, at, etag, last_modified):
        source = self.sources[nom]
        source.derniere_reussite = at
        source.echecs_consecutifs = 0
        source.etag = etag
        source.last_modified = last_modified

    def record_failure(self, nom):
        source = self.sources[nom]
        source.echecs_consecutifs += 1
        if source.echecs_consecutifs >= SLEEP_AFTER_FAILURES:
            source.actif = False
        return source

    def sleeping_sources(self):
        return sorted(
            source.nom
            for source in self.sources.values()
            if not source.actif and source.echecs_consecutifs >= SLEEP_AFTER_FAILURES
        )


@dataclass
class FetchResult:
    status: int
    body: bytes = b""
    etag: str | None = None
    last_modified: str | None = None


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(20.0),
        follow_redirects=False,
        trust_env=False,
        transport=transport,
        headers={"User-Agent": USER_AGENT},
    )


def fetch_conditional(
    client: httpx.Client, url: str, etag: str | None = None, last_modified: str | None = None
) -> FetchResult:
    parsed = urlparse(url)
    local_test = parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS
    if parsed.scheme != "https" and not local_test:
        raise PermanentError("Le flux doit utiliser HTTPS.")
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    try:
        with client.stream("GET", url, headers=headers) as response:
            status = response.status_code
            if status == 304:
                return FetchResult(
                    304,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                )
            if status in TRANSIENT_STATUSES:
                raise TransientError(f"HTTP {status}")
            if status != 200:
                target = response.headers.get("Location")
                suffix = f" vers {target} : mettre à jour sources.csv" if target else ""
                raise PermanentError(f"HTTP {status}{suffix}")
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_FEED_BYTES:
                    raise PermanentError("Flux supérieur à 2 Mo.")
                chunks.append(chunk)
            return FetchResult(
                200,
                b"".join(chunks),
                response.headers.get("ETag"),
                response.headers.get("Last-Modified"),
            )
    except httpx.TransportError as error:
        raise TransientError(f"{type(error).__name__} : {error}") from error


def log_event(level: int, event: str, **fields) -> None:
    timestamp = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    record = {"ts": timestamp, "evenement": event, **fields}
    logger.log(level, json.dumps(record, ensure_ascii=False, default=str))


def fetch_with_backoff(
    client: httpx.Client, source: Source, sleep: Callable[[float], None]
) -> FetchResult:
    for attempt, delay in enumerate((*BACKOFF_SECONDS, None), start=1):
        try:
            return fetch_conditional(client, source.url_flux, source.etag, source.last_modified)
        except TransientError as error:
            if delay is None:
                raise
            log_event(
                logging.WARNING,
                "nouvel_essai",
                source=source.nom,
                tentative=attempt,
                attente_s=delay,
                erreur=str(error),
            )
            sleep(delay)
    raise AssertionError("inatteignable")


def collect_source(
    client: httpx.Client,
    repo: SourceRepository,
    source: Source,
    output: Path,
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
) -> dict:
    started = time.monotonic()
    record = {"source": source.nom, "statut": "ok", "http": None, "recus": 0, "ecrits": 0}
    record["ignores"] = 0
    try:
        result = fetch_with_backoff(client, source, sleep)
        record["http"] = result.status
        now = clock()
        if result.status == 304:
            record["statut"] = "inchange"
            etag = result.etag or source.etag
            last_modified = result.last_modified or source.last_modified
        else:
            items, ignored = extract_raw_items(result.body, source.nom, now)
            written = sum(write_raw_item(output, item) for item in items)
            record.update(recus=len(items) + ignored, ecrits=written)
            record["ignores"] = ignored + len(items) - written
            etag, last_modified = result.etag, result.last_modified
        repo.record_success(source.nom, now, etag, last_modified)
        record["echecs_consecutifs"] = 0
        level = logging.INFO
    except (TransientError, PermanentError, FeedError) as error:
        state = repo.record_failure(source.nom)
        record["statut"] = "echec" if state.actif else "sommeil"
        record["erreur"] = str(error)
        record["echecs_consecutifs"] = state.echecs_consecutifs
        level = logging.WARNING if state.actif else logging.ERROR
    record["duree_ms"] = round((time.monotonic() - started) * 1000)
    log_event(level, "source", **record)
    if record["statut"] == "sommeil":
        log_event(
            logging.ERROR,
            "source_mise_en_sommeil",
            source=source.nom,
            action="vérifier l'URL du flux puis remettre actif = true",
        )
    return record


def collect_all(
    repo: SourceRepository,
    output: Path,
    *,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    sources = repo.active_sources()
    records = []
    with make_client(transport) as client:
        for index, source in enumerate(sources):
            if index:
                sleep(PAUSE_BETWEEN_SOURCES)
            records.append(collect_source(client, repo, source, output, clock, sleep))
    summary = {
        "sources": len(sources),
        "ok": sum(r["statut"] in {"ok", "inchange"} for r in records),
        "echecs": sum(r["statut"] == "echec" for r in records),
        "mises_en_sommeil": sum(r["statut"] == "sommeil" for r in records),
        "recus": sum(r["recus"] for r in records),
        "ecrits": sum(r["ecrits"] for r in records),
        "en_sommeil": repo.sleeping_sources(),
    }
    log_event(logging.INFO, "collecte_terminee", **summary)
    return summary


def run_collection(sources_csv: Path, output: Path) -> dict:
    """Avec DATABASE_URL : état dans PostgreSQL (migré, synchronisé). Sinon : en mémoire."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return collect_all(MemorySources.from_csv(sources_csv), output)
    from gazette.db import PostgresSources, connect, migrate, sync_sources

    with connect(database_url) as conn:
        applied = migrate(conn)
        if applied:
            log_event(logging.INFO, "migrations_appliquees", versions=applied)
        sync_sources(conn, sources_csv)
        return collect_all(PostgresSources(conn), output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collecter les sources actives.")
    parser.add_argument("--sources", type=Path, default=Path("sources.csv"))
    parser.add_argument("--output", type=Path, default=Path("/data/articles_bruts"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Les lignes "HTTP Request: ..." de httpx doublonnent nos journaux JSON.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    summary = run_collection(args.sources, args.output)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
