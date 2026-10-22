"""Projection d'un flux RSS/Atom en articles bruts (bronze), sans texte intégral."""

import calendar
from datetime import UTC, datetime

import feedparser
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from gazette.bronze import item_id
from gazette.feed import MAX_FEED_BYTES, FeedError, plain_text

ATOM = "{http://www.w3.org/2005/Atom}"
DC_DATE = "{http://purl.org/dc/elements/1.1/}date"
MAX_RAW_CHARS = 2_000
MAX_SUMMARY_CHARS = 500
# Liste blanche : seules ces balises entrent dans payload. Tout le reste est ignoré
# (content:encoded, images, enclosure, auteurs, commentaires...).
RSS_FIELDS = {"title", "link", "description", "pubDate", "guid", "category"}
ATOM_FIELDS = {"title", "id", "published", "updated", "summary", "category", "link"}


def _payload(raw, atom: bool) -> dict:
    values: dict[str, list[str]] = {}
    for child in raw:
        if atom:
            if not child.tag.startswith(ATOM):
                continue
            name = child.tag[len(ATOM) :]
            if name not in ATOM_FIELDS:
                continue
            if name == "link":
                if child.get("rel", "alternate") != "alternate":
                    continue
                value = child.get("href", "")
            elif name == "category":
                value = child.get("term", "")
            else:
                value = child.text or ""
        else:
            if child.tag == DC_DATE:
                name = "dc:date"
            elif child.tag in RSS_FIELDS:
                name = child.tag
            else:
                continue
            value = child.text or ""
        values.setdefault(name, []).append(value.strip()[:MAX_RAW_CHARS])
    return {name: found[0] if len(found) == 1 else found for name, found in values.items()}


def _first(value) -> str:
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def _valid_link(link: str) -> bool:
    return (
        link.startswith(("https://", "http://"))
        and len(link.split("/")) > 2
        and bool(link.split("/")[2])
    )


def extract_raw_items(data: bytes, source: str, now: datetime) -> tuple[list[dict], int]:
    """Renvoie (articles bruts, nombre d'items ignorés faute de lien exploitable)."""
    if len(data) > MAX_FEED_BYTES:
        raise FeedError("Flux supérieur à 2 Mo.")
    try:
        root = ElementTree.fromstring(data, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise FeedError("Le document n'est pas un flux XML sûr et valide.") from error
    atom = root.tag == ATOM + "feed"
    if root.tag == "rss":
        raw_entries = root.findall("./channel/item")
    elif atom:
        raw_entries = root.findall(ATOM + "entry")
    else:
        raise FeedError("Seuls les flux RSS 2.0 et Atom sont acceptés.")
    # feedparser sert à interpréter les dates (tous formats, tous fuseaux).
    # Un flux légèrement imparfait (bozo) est accepté : le tri se fera au nettoyage.
    entries = feedparser.parse(data).entries
    if len(entries) != len(raw_entries):
        raise FeedError("Nombre d'items incohérent entre les deux lectures du flux.")
    collected_at = now.astimezone(UTC).isoformat().replace("+00:00", "Z")
    items, seen, ignored = [], set(), 0
    for entry, raw in zip(entries, raw_entries, strict=True):
        payload = _payload(raw, atom)
        link = _first(payload.get("link")).strip()
        if not _valid_link(link):
            guid = _first(payload.get("guid") or payload.get("id")).strip()
            link = guid if _valid_link(guid) else ""
        if not link:
            ignored += 1
            continue
        identifier = item_id(source, link)
        if identifier in seen:
            ignored += 1
            continue
        seen.add(identifier)
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        published = None
        if parsed:
            moment = datetime.fromtimestamp(calendar.timegm(parsed), UTC)
            published = moment.isoformat().replace("+00:00", "Z")
        summary = _first(payload.get("description") or payload.get("summary"))
        category = _first(payload.get("category")).strip()
        items.append(
            {
                "id": identifier,
                "source": source,
                "lien": link,
                "titre": plain_text(_first(payload.get("title")), 500),
                "resume": plain_text(summary, MAX_SUMMARY_CHARS),
                "publie_le": published,
                "recupere_le": collected_at,
                "rubrique": category or None,
                "payload": payload,
            }
        )
    return items, ignored
