"""Lecture bornée de RSS/Atom et projection des seules métadonnées."""

import calendar
import logging
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse

import feedparser
import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

MAX_FEED_BYTES = 2_000_000
MAX_EXCERPT_CHARS = 280
logger = logging.getLogger(__name__)


class FeedError(ValueError):
    """Flux absent, invalide ou trop volumineux."""


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"p", "br", "div", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif tag in {"p", "div", "li"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value: str, limit: int) -> str:
    parser = _Text()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())[:limit]


def fetch_feed(url: str, *, transport: httpx.BaseTransport | None = None) -> bytes:
    if urlparse(url).scheme != "https":
        raise FeedError("Le flux doit utiliser HTTPS.")
    # Pas de proxy implicite, de cookies, de redirection ni de lecture des articles liés.
    with httpx.Client(
        timeout=httpx.Timeout(20.0),
        follow_redirects=False,
        trust_env=False,
        transport=transport,
        headers={"User-Agent": "LaGazette-TD2/0.1 (RSS metadata reader)"},
    ) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_FEED_BYTES:
                    raise FeedError("Flux supérieur à 2 Mo.")
                chunks.append(chunk)
    return b"".join(chunks)


def parse_feed(data: bytes, *, now: datetime | None = None) -> list[dict[str, str]]:
    """Sans `now`, rejoue une fixture ; avec `now`, impose une fraîcheur < 24 h."""
    if len(data) > MAX_FEED_BYTES:
        raise FeedError("Flux supérieur à 2 Mo.")
    if now is not None and now.tzinfo is None:
        raise FeedError("L'heure de référence doit inclure un fuseau.")
    try:
        root = ElementTree.fromstring(data, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise FeedError("Le document n'est pas un flux XML sûr et valide.") from error
    atom = "{http://www.w3.org/2005/Atom}"
    if root.tag == "rss":
        raw_entries = root.findall("./channel/item")
    elif root.tag == atom + "feed":
        raw_entries = root.findall(atom + "entry")
    else:
        raise FeedError("Seuls les flux RSS 2.0 et Atom sont acceptés.")
    parsed = feedparser.parse(data)
    if parsed.bozo or not parsed.get("version"):
        raise FeedError("Le document n'est pas un flux RSS/Atom valide.")
    items = []
    seen = set()
    skipped = 0
    for entry, raw in zip(parsed.entries, raw_entries, strict=True):
        title = plain_text(entry.get("title", ""), 500)
        if root.tag == "rss":
            link = (raw.findtext("link") or "").strip()
            summary = raw.find("description")
        else:
            links = raw.findall(atom + "link")
            link = next(
                (
                    node.get("href", "")
                    for node in links
                    if node.get("rel", "alternate") == "alternate"
                ),
                "",
            ).strip()
            summary = raw.find(atom + "summary")
        # feedparser peut synthétiser summary à partir de content:encoded :
        # le champ explicite du XML est donc la seule source autorisée ici.
        excerpt = ""
        if summary is not None:
            excerpt = (summary.text or "") + "".join(
                ElementTree.tostring(child, encoding="unicode") for child in summary
            )
        publication = entry.get("published_parsed")
        if not title or not urlparse(link).netloc or urlparse(link).scheme not in {"https", "http"}:
            skipped += 1
            continue
        if not publication:
            skipped += 1
            continue
        try:
            published = datetime.fromtimestamp(calendar.timegm(publication), UTC)
        except (ValueError, OverflowError):
            skipped += 1
            continue
        if now is not None and not now - timedelta(hours=24) < published <= now:
            skipped += 1
            continue
        if link in seen:
            skipped += 1
            continue
        seen.add(link)
        items.append(
            {
                "title": title,
                # Ne jamais utiliser content:encoded, auteurs, images ou commentaires.
                "excerpt": plain_text(excerpt, MAX_EXCERPT_CHARS),
                "link": link,
                "date": published.isoformat().replace("+00:00", "Z"),
            }
        )
    logger.info("Flux analysé : %d items conservés, %d écartés", len(items), skipped)
    return items
