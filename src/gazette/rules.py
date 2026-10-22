"""Règles d'exclusion : chacune a un identifiant, que le rapport compte.

Documentées dans docs/qualite.md (ce qu'elle écarte, pourquoi, un exemple réel).
L'ordre compte : un item est rejeté par la première règle qui le reconnaît.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from gazette.normalize import MOJIBAKE

FRESHNESS = timedelta(hours=24)
FUTURE_TOLERANCE = timedelta(minutes=10)  # horloges des éditeurs pas tout à fait à l'heure
NEAR_DUPLICATE = 0.8  # Jaccard sur les mots du titre : « même titre à deux mots près »
DAYS = "lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"
CHANNELS = r"tf1|france ?[2-5]|m6|arte|canal\+|c8|w9|tmc|tfx|6ter|rmc story"


def pattern(*parts: str) -> re.Pattern:
    return re.compile("|".join(parts), re.IGNORECASE)


PUBLI = pattern(
    r"contenu[s]? (partenaire|sponsoris)",
    r"publi-?(reportage|r[ée]dactionnel)",
    r"\bsponsoris[ée]",
    r"en partenariat avec",
    r"\bcode promo\b",
    r"\bbons? plans?\b",
)
HOROSCOPE = pattern(r"\bhoroscope", r"\bastrolog", r"\bsignes? du zodiaque")
TV = pattern(
    r"\bprogramme t[ée]l[ée]\b",
    r"\bprogramme tv\b",
    r"\bt[ée]l[ée]film\b",
    r"\bce soir (à|a) la t[ée]l[ée]",
    r"que regarder ce soir",
    rf"\bsur ({CHANNELS}) ce ({DAYS}|soir)",
)
GAMES = pattern(
    r"\bjeux?[- ]concours\b",
    r"\bespace jeux\b",
    r"\bmots[- ]crois[ée]s\b",
    r"\bsudoku\b",
    r"\btentez de gagner\b",
    r"\b[àa] gagner\b",
    r"\bquiz\b",
)
NON_EDITORIAL = pattern(
    r"\bappel [àa] t[ée]moignages?\b",
    r"\bcommentaire de l.[ée]vangile\b",
    r"\bl.essentiel de l.actu",
    r"\bl.actu de ce (" + DAYS + r")\b",
)
TEMPLATE = re.compile(r"\$[a-z_]+\.[a-z_]+|\{\{|\}\}|%s\b", re.IGNORECASE)
BROKEN_ENCODING = re.compile(f"{MOJIBAKE.pattern}|\ufffd")


@dataclass(frozen=True)
class Rule:
    id: str
    ecarte: str
    match: Callable[[dict, datetime], bool]


def title_and_link(item: dict) -> str:
    # Pas l'extrait : « en partenariat avec les Restos du Cœur » figurait dans un vrai
    # article politique (faux positif relevé le 22/10, voir docs/qualite.md).
    return f"{item['titre']} {item['lien']}"


RULES: tuple[Rule, ...] = (
    Rule(
        "R01_publi",
        "publi-reportages, contenus partenaires, bons plans",
        lambda i, _: bool(PUBLI.search(title_and_link(i))),
    ),
    Rule(
        "R02_horoscope", "horoscope et astrologie", lambda i, _: bool(HOROSCOPE.search(i["titre"]))
    ),
    Rule(
        "R03_programme_tv",
        "programmes et promotions d'émissions TV",
        lambda i, _: bool(TV.search(i["titre"])),
    ),
    Rule("R04_jeux", "jeux, concours, quiz", lambda i, _: bool(GAMES.search(i["titre"]))),
    Rule(
        "R05_titre_gabarit",
        "titre resté sous forme de gabarit ($content.Title…)",
        lambda i, _: bool(TEMPLATE.search(i["titre"])),
    ),
    Rule(
        "R06_titre_vide",
        "titre absent ou de moins de 3 mots",
        lambda i, _: len(i["titre"].split()) < 3,
    ),
    Rule(
        "R07_encodage",
        "encodage cassé après réparation (Ã©, â€™, �)",
        lambda i, _: bool(BROKEN_ENCODING.search(f"{i['titre']} {i['extrait']}")),
    ),
    Rule(
        "R08_date_future",
        "date de publication dans le futur",
        lambda i, now: i["publie_le"] is not None and i["publie_le"] > now + FUTURE_TOLERANCE,
    ),
    Rule(
        "R09_perime",
        "sans date, ou publié il y a plus de 24 h",
        lambda i, now: i["publie_le"] is None or i["publie_le"] < now - FRESHNESS,
    ),
    Rule(
        "R10_non_editorial",
        "appels à témoignages, récapitulatifs, rubriques de service",
        lambda i, _: bool(NON_EDITORIAL.search(i["titre"])),
    ),
)
RULE_IDS = tuple(rule.id for rule in RULES) + ("R11_doublon_exact", "R12_doublon_approche")


def first_rule(item: dict, now: datetime) -> str | None:
    """Identifiant de la première règle qui écarte l'item, ou None s'il est gardé."""
    return next((rule.id for rule in RULES if rule.match(item, now)), None)


def jaccard(a: str, b: str) -> float:
    """Similarité de deux clés de titre : mots communs / mots distincts."""
    words_a, words_b = set(a.split()), set(b.split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def find_duplicate(key: str, known: Iterable[tuple[str, str]]) -> tuple[str, str] | None:
    """(règle, id de l'original) si la clé double un titre déjà gardé, sinon None."""
    best: tuple[float, str] | None = None
    for other_id, other_key in known:
        if key == other_key:
            return "R11_doublon_exact", other_id
        score = jaccard(key, other_key)
        if score >= NEAR_DUPLICATE and (best is None or score > best[0]):
            best = (score, other_id)
    return ("R12_doublon_approche", best[1]) if best else None
