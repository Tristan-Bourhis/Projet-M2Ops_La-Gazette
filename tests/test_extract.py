from datetime import UTC, datetime
from pathlib import Path

import pytest

from gazette.extract import extract_raw_items
from gazette.feed import FeedError

FIXTURE = Path(__file__).parent / "fixtures" / "ouest-france.xml"
NOW = datetime(2026, 10, 22, 8, tzinfo=UTC)
FIELDS = {
    "id",
    "source",
    "lien",
    "titre",
    "resume",
    "publie_le",
    "recupere_le",
    "rubrique",
    "payload",
}


def rss(items: str) -> bytes:
    return (
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<channel><title>Test</title>{items}</channel></rss>"
    ).encode()


def test_fixture_gives_raw_items_with_all_fields():
    items, ignored = extract_raw_items(FIXTURE.read_bytes(), "Ouest-France", NOW)
    assert ignored == 0
    assert len(items) == 2
    assert all(set(item) == FIELDS for item in items)
    first = items[0]
    assert first["source"] == "Ouest-France"
    assert first["lien"] == "https://example.org/actualites/1"
    assert first["publie_le"] == "2026-10-20T11:54:52Z"
    assert first["recupere_le"] == "2026-10-22T08:00:00Z"
    assert first["payload"]["pubDate"] == "Tue, 20 Oct 2026 11:54:52 GMT"


def test_full_text_images_and_authors_never_kept():
    data = rss(
        "<item><title>T</title><link>https://example.org/1</link>"
        "<pubDate>Wed, 22 Oct 2026 09:00:00 +0200</pubDate><category>Sport</category>"
        "<author>private@example.org</author><content:encoded>ARTICLE COMPLET</content:encoded>"
        '<enclosure url="https://example.org/photo.jpg" type="image/jpeg"/>'
        "<description>&lt;p&gt;Extrait&lt;/p&gt;</description></item>"
    )
    item = extract_raw_items(data, "Test", NOW)[0][0]
    assert "ARTICLE COMPLET" not in str(item)
    assert "private@" not in str(item)
    assert "photo.jpg" not in str(item)
    assert item["resume"] == "Extrait"
    assert item["rubrique"] == "Sport"
    assert item["publie_le"] == "2026-10-22T07:00:00Z"


def test_dc_date_and_missing_date():
    data = rss(
        "<item><title>A</title><link>https://example.org/a</link>"
        "<dc:date>2026-10-22T09:00:00+02:00</dc:date></item>"
        "<item><title>B</title><link>https://example.org/b</link></item>"
    )
    items, _ = extract_raw_items(data, "Test", NOW)
    assert items[0]["publie_le"] == "2026-10-22T07:00:00Z"
    assert items[1]["publie_le"] is None


def test_items_without_link_or_duplicated_are_ignored():
    data = rss(
        "<item><title>A</title><link>https://example.org/a</link></item>"
        "<item><title>A bis</title><link>https://example.org/a#haut</link></item>"
        "<item><title>Sans lien</title></item>"
        '<item><title>Guid</title><guid isPermaLink="true">https://example.org/g</guid></item>'
    )
    items, ignored = extract_raw_items(data, "Test", NOW)
    assert [item["lien"] for item in items] == ["https://example.org/a", "https://example.org/g"]
    assert ignored == 2


def test_atom_feed():
    data = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>T</title>
      <entry><title>Atom</title><id>urn:1</id>
      <link rel="alternate" href="https://example.org/atom"/>
      <updated>2026-10-22T09:00:00+02:00</updated><summary>Resume</summary>
      <category term="Monde"/></entry></feed>"""
    item = extract_raw_items(data, "Test", NOW)[0][0]
    assert item["lien"] == "https://example.org/atom"
    assert item["resume"] == "Resume"
    assert item["rubrique"] == "Monde"
    assert item["publie_le"] == "2026-10-22T07:00:00Z"


@pytest.mark.parametrize("data", [b"", b"<html>Erreur</html>"])
def test_not_a_feed_fails(data):
    with pytest.raises(FeedError):
        extract_raw_items(data, "Test", NOW)
