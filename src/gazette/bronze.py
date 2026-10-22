"""Stockage brut (bronze) : un fichier JSON par article, jamais écrit deux fois."""

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_link(link: str) -> str:
    """Même article, même lien : domaine en minuscules, sans ancre ni traceurs utm_*."""
    parts = urlsplit(link.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), "")
    )


def item_id(source: str, link: str) -> str:
    """Clé naturelle (source, lien) transformée en identifiant stable."""
    key = f"{source}\n{normalize_link(link)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def slugify(text: str) -> str:
    """« Dernières Nouvelles d'Alsace » -> « dernieres-nouvelles-d-alsace »."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", without_accents.lower()).strip("-")


def write_raw_item(directory: Path, item: dict) -> bool:
    """Écrit l'article s'il est nouveau. Renvoie True si écrit, False s'il existait déjà."""
    target = directory / slugify(item["source"]) / f"{item['id']}.json"
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False
    ) as stream:
        json.dump(item, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    try:
        # os.link échoue si la cible existe : jamais d'écrasement, même si deux
        # collectes tournent en même temps.
        os.link(temporary, target)
    except FileExistsError:
        return False
    finally:
        temporary.unlink(missing_ok=True)
    return True
