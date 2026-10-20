from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from gazette.feed import MAX_FEED_BYTES, FeedError, fetch_feed, parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "ouest-france.xml"


def rss(items: str) -> bytes:
    return (
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
        f"<channel><title>Test</title>{items}</channel></rss>"
    ).encode()


def item(date="Tue, 20 Oct 2026 11:00:00 GMT", link="https://example.org/1") -> str:
    return (
        f"<item><title>Actualité</title><link>{link}</link>"
        f"<pubDate>{date}</pubDate><description>Extrait</description></item>"
    )


def test_recorded_fixture_projection():
    result = parse_feed(FIXTURE.read_bytes())
    assert len(result) == 3  # Sonde temporaire TD 2 : vérifier que la CI devient rouge.
    assert result[0] == {
        "title": "Transports : une nouvelle ligne régionale",
        "excerpt": "Un service régional & accessible.",
        "link": "https://example.org/actualites/1",
        "date": "2026-10-20T11:54:52Z",
    }
    assert result[1]["date"] == "2026-10-20T11:40:30Z"
    assert all(set(row) == {"title", "excerpt", "link", "date"} for row in result)


def test_full_content_and_personal_fields_are_never_exported():
    data = rss(
        "<item><title>Test</title><link>https://example.org/1</link>"
        "<pubDate>Tue, 20 Oct 2026 12:00:00 +0200</pubDate>"
        "<author>private@example.org</author><content:encoded>FULL ARTICLE</content:encoded>"
        f"<description>{'a' * 400}</description></item>"
    )
    result = parse_feed(data)[0]
    assert result["date"] == "2026-10-20T10:00:00Z"
    assert len(result["excerpt"]) == 280
    assert "FULL ARTICLE" not in str(result)
    assert "private@" not in str(result)


def test_missing_summary_does_not_fall_back_to_full_content():
    data = rss(item().replace("<description>Extrait</description>", "")).replace(
        b"</item>", b"<content:encoded>ARTICLE COMPLET</content:encoded></item>"
    )
    assert parse_feed(data)[0]["excerpt"] == ""


@pytest.mark.parametrize("data", [b"", b"<html>Acces refuse</html>", b"<rss><channel>"])
def test_invalid_document_fails(data):
    with pytest.raises(FeedError):
        parse_feed(data)


def test_xml_entities_are_rejected():
    with pytest.raises(FeedError):
        parse_feed(
            b'<!DOCTYPE rss [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
            b'<rss version="2.0"><channel><title>&secret;</title></channel></rss>'
        )


def test_invalid_items_and_duplicates_are_skipped():
    data = rss(
        item()
        + item()
        + item(date="inconnue", link="https://example.org/2")
        + item(link="javascript:alert(1)")
        + item(link="https:///missing-host")
        + item().replace("<title>Actualité</title>", "")
    )
    assert len(parse_feed(data)) == 1


def test_freshness_uses_publication_not_collection_time():
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    data = rss(
        item()
        + item("Mon, 19 Oct 2026 12:00:00 GMT", "https://example.org/old")
        + item("Tue, 20 Oct 2026 12:00:01 GMT", "https://example.org/future")
    )
    assert len(parse_feed(data, now=now)) == 1


def test_atom_and_timezone():
    data = b"""<feed xmlns="http://www.w3.org/2005/Atom">
      <title>Test</title><entry><title>Atom</title>
      <link href="https://example.org/atom"/>
      <published>2026-10-20T13:00:00+02:00</published>
      <summary>Resume</summary></entry></feed>"""
    assert parse_feed(data)[0]["date"] == "2026-10-20T11:00:00Z"


def test_fetch_parse_end_to_end_without_publisher_network():
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=FIXTURE.read_bytes())

    data = fetch_feed("https://www.ouest-france.fr/rss/une", transport=httpx.MockTransport(handler))
    assert len(parse_feed(data)) == 2
    assert requests == ["https://www.ouest-france.fr/rss/une"]


@pytest.mark.parametrize("status", [302, 403, 500])
def test_http_errors_and_redirects_fail(status):
    with pytest.raises(httpx.HTTPStatusError):
        fetch_feed(
            "https://example.org/rss",
            transport=httpx.MockTransport(lambda _: httpx.Response(status)),
        )


def test_http_timeout_fails():
    def handler(request):
        raise httpx.ReadTimeout("Timeout", request=request)

    with pytest.raises(httpx.ReadTimeout):
        fetch_feed("https://example.org/rss", transport=httpx.MockTransport(handler))


def test_response_size_is_bounded():
    with pytest.raises(FeedError, match="2 Mo"):
        fetch_feed(
            "https://example.org/rss",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, content=b"x" * (MAX_FEED_BYTES + 1))
            ),
        )
