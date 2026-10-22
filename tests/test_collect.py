import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from gazette.collect import (
    PAUSE_BETWEEN_SOURCES,
    USER_AGENT,
    MemorySources,
    Source,
    collect_all,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ouest-france.xml"
NOW = datetime(2026, 10, 22, 8, tzinfo=UTC)


def no_wait(_seconds):
    return None


def run(repo, output, transport=None, sleep=no_wait):
    return collect_all(repo, output, transport=transport, clock=lambda: NOW, sleep=sleep)


def ouest_france():
    return MemorySources([Source("Ouest-France", "PQR", "https://www.ouest-france.fr/rss/une")])


def fixture_server(etag=None):
    requests = []

    def handler(request):
        requests.append(request)
        if etag and request.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        headers = {"ETag": etag} if etag else {}
        return httpx.Response(200, content=FIXTURE.read_bytes(), headers=headers)

    return httpx.MockTransport(handler), requests


def test_two_passes_zero_duplicate(tmp_path):
    repo = ouest_france()
    transport, _ = fixture_server()
    first = run(repo, tmp_path, transport)
    second = run(repo, tmp_path, transport)
    assert (first["ecrits"], second["ecrits"]) == (2, 0)
    assert len(list(tmp_path.rglob("*.json"))) == 2


def test_second_pass_is_conditional_and_polite(tmp_path):
    repo = ouest_france()
    transport, requests = fixture_server(etag='"v1"')
    run(repo, tmp_path, transport)
    summary = run(repo, tmp_path, transport)
    assert requests[0].headers["User-Agent"] == USER_AGENT
    assert requests[1].headers["If-None-Match"] == '"v1"'
    assert summary == {
        "sources": 1,
        "ok": 1,
        "echecs": 0,
        "indisponibles": 0,
        "mises_en_sommeil": 0,
        "recus": 0,
        "ecrits": 0,
        "en_sommeil": [],
    }
    assert repo.sources["Ouest-France"].derniere_reussite == NOW


@pytest.fixture
def local_server():
    """Vrai serveur HTTP local : /ok sert la fixture RSS, /panne répond toujours 503."""
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if self.path == "/ok":
                body = FIXTURE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/rss+xml")
            else:
                body = b""
                self.send_response(503)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", hits
    server.shutdown()
    server.server_close()


def test_source_down_503_backoff_then_sleep(tmp_path, local_server):
    """Source en panne (vrai serveur local en 503) pendant que les autres répondent :
    backoff 1/2/4 s, un échec compté par passage, sommeil au 3e."""
    base, hits = local_server
    repo = MemorySources(
        [Source("En panne", "PQR", f"{base}/panne"), Source("OK", "PQN", f"{base}/ok")]
    )
    waits = []
    for expected_failures in (1, 2, 3):
        run(repo, tmp_path, sleep=waits.append)
        assert repo.sources["En panne"].echecs_consecutifs == expected_failures
    assert waits == [1, 2, 4, PAUSE_BETWEEN_SOURCES] * 3
    assert hits.count("/panne") == 4 * 3
    assert repo.sources["En panne"].actif is False
    after = run(repo, tmp_path)
    assert (after["sources"], after["en_sommeil"]) == (1, ["En panne"])


def test_permanent_error_proves_network_works(tmp_path):
    """Un 404 est une réponse : le réseau marche, le 503 de l'autre source est compté."""

    def handler(request):
        if request.url.host == "absent.example.org":
            return httpx.Response(404)
        return httpx.Response(503)

    repo = MemorySources(
        [
            Source("Absente", "PQN", "https://absent.example.org/rss"),
            Source("En panne", "PQR", "https://panne.example.org/rss"),
        ]
    )
    summary = run(repo, tmp_path, httpx.MockTransport(handler))
    assert (summary["echecs"], summary["indisponibles"]) == (2, 0)


def test_network_outage_does_not_put_sources_to_sleep(tmp_path):
    def offline(request):
        raise httpx.ConnectError("Réseau indisponible", request=request)

    repo = MemorySources(
        [
            Source("Ouest-France", "PQR", "https://www.ouest-france.fr/rss/une"),
            Source("Le Monde", "PQN", "https://www.lemonde.fr/rss/une.xml"),
        ]
    )
    for _ in range(5):
        summary = run(repo, tmp_path, httpx.MockTransport(offline))
    assert (summary["ok"], summary["indisponibles"], summary["en_sommeil"]) == (0, 2, [])
    assert all(source.actif for source in repo.sources.values())


def test_three_permanent_errors_put_source_to_sleep(tmp_path):
    repo = ouest_france()
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    for expected_failures in (1, 2, 3):
        run(repo, tmp_path, transport)
        assert repo.sources["Ouest-France"].echecs_consecutifs == expected_failures
    assert repo.sources["Ouest-France"].actif is False
    after = run(repo, tmp_path, transport)
    assert (after["sources"], after["en_sommeil"]) == (0, ["Ouest-France"])


def test_permanent_error_is_not_retried(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    repo = ouest_france()
    summary = run(repo, tmp_path, httpx.MockTransport(handler))
    assert len(calls) == 1
    assert summary["echecs"] == 1
    assert repo.sources["Ouest-France"].echecs_consecutifs == 1


def test_one_broken_source_does_not_block_the_others(tmp_path):
    def handler(request):
        if request.url.host == "casse.example.org":
            return httpx.Response(500)
        return httpx.Response(200, content=FIXTURE.read_bytes())

    repo = MemorySources(
        [
            Source("Cassée", "PQN", "https://casse.example.org/rss"),
            Source("Ouest-France", "PQR", "https://www.ouest-france.fr/rss/une"),
        ]
    )
    summary = run(repo, tmp_path, httpx.MockTransport(handler))
    assert (summary["ok"], summary["echecs"], summary["ecrits"]) == (1, 1, 2)


def test_success_resets_failures(tmp_path):
    repo = ouest_france()
    repo.sources["Ouest-France"].echecs_consecutifs = 2
    transport, _ = fixture_server()
    run(repo, tmp_path, transport)
    assert repo.sources["Ouest-France"].echecs_consecutifs == 0
