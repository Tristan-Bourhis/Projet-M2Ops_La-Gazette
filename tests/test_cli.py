import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from gazette.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "ouest-france.xml"


def test_cli_writes_json(tmp_path):
    target = tmp_path / "nested" / "items.json"
    assert main(["--input", str(FIXTURE), "--output", str(target)]) == 0
    result = json.loads(target.read_text())
    assert len(result) == 2
    assert result[0]["link"] == "https://example.org/actualites/1"


def test_failure_preserves_previous_output(tmp_path):
    target = tmp_path / "items.json"
    target.write_text('["previous"]')
    invalid = tmp_path / "invalid.xml"
    invalid.write_text("<html>error</html>")
    assert main(["--input", str(invalid), "--output", str(target)]) == 1
    assert json.loads(target.read_text()) == ["previous"]


def test_live_source_reads_and_writes(monkeypatch, tmp_path):
    sources = tmp_path / "sources.csv"
    with sources.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["nom", "acces"])
        writer.writeheader()
        writer.writerow(dict(nom="Test", acces="https://example.org/rss"))
    monkeypatch.setattr("gazette.cli.fetch_feed", lambda _: FIXTURE.read_bytes())

    class FrozenDatetime:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 10, 20, 12, tzinfo=UTC)

    monkeypatch.setattr("gazette.cli.datetime", FrozenDatetime)
    target = tmp_path / "items.json"
    assert (
        main(["--sources", str(sources), "--source", "Test", "--live", "--output", str(target)])
        == 0
    )
    assert len(json.loads(target.read_text())) == 2
