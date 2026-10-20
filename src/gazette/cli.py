import argparse
import csv
import json
import logging
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

from gazette.feed import MAX_FEED_BYTES, FeedError, fetch_feed, parse_feed

logger = logging.getLogger(__name__)


def find_source(path: Path, name: str) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    matches = [row for row in rows if row.get("nom") == name]
    if len(matches) != 1 or not matches[0].get("acces"):
        raise FeedError(f"Source absente, ambiguë ou sans URL : {name}")
    return matches[0]


def ensure_enabled(source: dict[str, str]) -> None:
    notes = source.get("notes", "")
    conditions = source.get("conditions", "")
    if not re.search(r"(?:^|[;.\s])activation=OUI(?:[;.\s]|$)", notes):
        raise FeedError("Source désactivée dans sources.csv ; utiliser la fixture locale.")
    if not re.search(r"statut_droits=AUTORISÉ(?:[;.\s]|$)", notes + " " + conditions):
        raise FeedError("L'autorisation de cette source n'est pas renseignée dans sources.csv.")


def write_json(path: Path, items: list[dict[str, str]]) -> None:
    """Remplacement atomique : une erreur ne détruit pas la précédente sortie."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(items, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lire une source RSS et écrire ses métadonnées JSON."
    )
    parser.add_argument("--sources", type=Path, default=Path("sources.csv"))
    parser.add_argument("--source", default="Ouest-France")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--input", type=Path, help="Fixture RSS locale ; aucun appel réseau")
    mode.add_argument("--live", action="store_true", help="Lecture HTTPS d'une source autorisée")
    parser.add_argument("--output", type=Path, default=Path("/data/items.json"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        source = find_source(args.sources, args.source)
        if args.live:
            ensure_enabled(source)
            data = fetch_feed(source["acces"])
            now = datetime.now(UTC)
        else:
            path = args.input or Path("tests/fixtures/ouest-france.xml")
            with path.open("rb") as stream:
                data = stream.read(MAX_FEED_BYTES + 1)
            now = None
        items = parse_feed(data, now=now)
        if not items:
            raise FeedError("Aucun item exploitable ; la sortie précédente est conservée.")
        write_json(args.output, items)
        logger.info("Source %s : %d items écrits dans %s", source["nom"], len(items), args.output)
        return 0
    except (OSError, ValueError, httpx.HTTPError, csv.Error) as error:
        logger.error("%s", error)
        return 1
