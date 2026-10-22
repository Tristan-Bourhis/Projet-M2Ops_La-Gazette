import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from gazette.collect import USER_AGENT, MemorySources, Source, collect_all

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
def down_server():
    """Vrai serveur HTTP local qui répond toujours 503."""
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/rss", hits
    server.shutdown()
    server.server_close()


def test_source_down_503_backoff_without_sleep(tmp_path, down_server):
    """Consigne : un 503 se réessaie (backoff) ; il ne met pas la source en sommeil."""
    url, hits = down_server
    repo = MemorySources([Source("En panne", "PQR", url)])
    waits = []
    for _ in range(3):
        summary = run(repo, tmp_path, sleep=waits.append)
        assert summary["indisponibles"] == 1
    assert waits == [1, 2, 4] * 3
    assert len(hits) == 4 * 3
    assert repo.sources["En panne"].actif is True
    assert repo.sources["En panne"].echecs_consecutifs == 0


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
    assert (summary["ok"], summary["indisponibles"], summary["ecrits"]) == (1, 1, 2)


def test_success_resets_failures(tmp_path):
    repo = ouest_france()
    repo.sources["Ouest-France"].echecs_consecutifs = 2
    transport, _ = fixture_server()
    run(repo, tmp_path, transport)
    assert repo.sources["Ouest-France"].echecs_consecutifs == 0
