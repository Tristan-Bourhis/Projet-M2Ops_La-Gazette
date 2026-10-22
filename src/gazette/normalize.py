"""Normalisation : une fonction pure par transformation, appliquée à chaque item brut."""

import html
import re
import unicodedata
from datetime import UTC, datetime

EXCERPT_MAX = 280
TAG = re.compile(r"<[^>]+>")
SPACES = re.compile(r"\s+")
# Octets de continuation UTF-8 (0x80-0xBF) tels qu'ils s'affichent en Windows-1252.
CONTINUATION = re.escape(bytes(range(0x80, 0xC0)).decode("cp1252", errors="ignore"))
MOJIBAKE = re.compile(f"[ÂÃ][{CONTINUATION}]|â€")
# Préfixes éditoriaux qui changent d'une version à l'autre d'un même article.
EDITORIAL_PREFIXES = re.compile(
    r"^(en direct|direct|replay|video|vidéo|carte|entretien|decryptage|décryptage|recit|récit"
    r"|temoignages|témoignages|portraits?|reportage|rencontre|exclusif|sondage)\s*[.:\-–]\s*",
    re.IGNORECASE,
)
STOPWORDS = frozenset(
    "le la les l un une des de du d au aux a à et ou en dans sur par pour pas ne ce cette ces"
    " qui que qu est son sa ses leur leurs il elle ils elles on se s plus avec sans".split()
)


def strip_html(text: str) -> str:
    """Retire les balises HTML : « <b>Titre</b> » -> « Titre »."""
    return TAG.sub(" ", text)


def unescape_entities(text: str) -> str:
    """Décode les entités HTML : « &amp; » -> « & », « &#8217; » -> « ’ »."""
    return html.unescape(text)


def fix_mojibake(text: str) -> str:
    """Répare l'UTF-8 lu comme du Windows-1252 : « Ã©tÃ© » -> « été ». Sinon, inchangé."""
    if not MOJIBAKE.search(text):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Texte mixte (une vraie espace insécable, un « ’ » correct…) : mot par mot.
        # « à » abîmé devient « Ã » + insécable : on ne coupe pas après un « Ã ».
        return "".join(_fix_word(part) for part in re.split(r"(?<!Ã)(\s)", text))


def _fix_word(word: str) -> str:
    try:
        return word.encode("cp1252").decode("utf-8") if MOJIBAKE.search(word) else word
    except (UnicodeEncodeError, UnicodeDecodeError):
        return word


def clean_spaces(text: str) -> str:
    """Espaces insécables et retours à la ligne ramenés à une espace simple, bords coupés."""
    return SPACES.sub(" ", text.replace("\xa0", " ").replace("\u202f", " ")).strip()


def clean_text(text: str | None) -> str:
    """Enchaîne les transformations de texte, dans l'ordre où les problèmes se superposent."""
    if not text:
        return ""
    return clean_spaces(fix_mojibake(strip_html(unescape_entities(text))))


def truncate_excerpt(text: str, limit: int = EXCERPT_MAX) -> str:
    """Extrait court : coupé au dernier mot entier avant la limite, suivi de « … »."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return f"{cut}…"


def to_utc(value: str | None) -> datetime | None:
    """Date ISO 8601 -> datetime UTC. Absente ou illisible -> None (la règle R08 tranchera)."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def title_key(title: str) -> str:
    """Clé de comparaison : sans préfixe éditorial, accents, ponctuation ni mots vides."""
    title = EDITORIAL_PREFIXES.sub("", title.strip())
    decomposed = unicodedata.normalize("NFKD", title.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    words = re.findall(r"[a-z0-9]+", plain)
    return " ".join(word for word in words if word not in STOPWORDS)


def normalize_item(raw: dict) -> dict:
    """Item brut -> item normalisé. Ne garde que ce qu'on a le droit de republier."""
    title = clean_text(raw.get("titre"))
    return {
        "id": raw["id"],
        "source": raw["source"],
        "lien": raw["lien"].strip(),
        "titre": title,
        "extrait": truncate_excerpt(clean_text(raw.get("resume"))),
        "publie_le": to_utc(raw.get("publie_le")),
        "recupere_le": to_utc(raw.get("recupere_le")),
        "rubrique": clean_text(raw.get("rubrique")) or None,
        "cle_titre": title_key(title),
    }
