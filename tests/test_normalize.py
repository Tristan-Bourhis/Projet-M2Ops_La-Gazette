from datetime import UTC, datetime

from gazette.normalize import (
    clean_spaces,
    clean_text,
    fix_mojibake,
    normalize_item,
    strip_html,
    title_key,
    to_utc,
    truncate_excerpt,
    unescape_entities,
)


def test_strip_html():
    assert strip_html("<p>Tempête <b>Austen</b></p>").split() == ["Tempête", "Austen"]


def test_unescape_entities():
    assert unescape_entities("Lille &amp; Lens, l&#8217;Europe") == "Lille & Lens, l’Europe"


def test_fix_mojibake_repairs_utf8_read_as_cp1252():
    assert fix_mojibake("Ã‰tÃ© sous la tempÃªte") == "Été sous la tempête"


def test_fix_mojibake_with_a_real_non_breaking_space():
    assert (
        fix_mojibake("Ã‰lection\xa0prÃ©sidentielle Ã\xa0 venir")
        == "Élection\xa0présidentielle à venir"
    )


def test_fix_mojibake_leaves_clean_text_alone():
    assert fix_mojibake("Économie : les prix à la pompe") == "Économie : les prix à la pompe"


def test_clean_spaces():
    assert clean_spaces("  Prix\u00a0Sakharov \n 2026\u202f!  ") == "Prix Sakharov 2026 !"


def test_clean_text_chains_everything():
    assert clean_text(" <i>Ã‰lection</i>&nbsp;prÃ©sidentielle ") == "Élection présidentielle"
    assert clean_text(None) == ""


def test_truncate_excerpt_cuts_on_a_word():
    text = "mot " * 100
    excerpt = truncate_excerpt(text.strip(), limit=50)
    assert len(excerpt) <= 50 and excerpt.endswith("mot…")
    assert truncate_excerpt("court") == "court"


def test_to_utc():
    assert to_utc("2026-10-22T10:35:36+02:00") == datetime(2026, 10, 22, 8, 35, 36, tzinfo=UTC)
    assert to_utc("2026-10-22T08:35:36Z").tzinfo == UTC
    assert to_utc("2026-10-22T08:35:36").tzinfo == UTC  # sans fuseau : on suppose UTC
    assert to_utc("pas une date") is None and to_utc(None) is None


def test_title_key_ignores_prefixes_accents_and_small_words():
    assert title_key("DIRECT. Le prix Sakharov décerné à la CPI") == "prix sakharov decerne cpi"
    assert title_key("EN DIRECT - Tempête Austen") == title_key("Tempête Austen")


def test_normalize_item_keeps_only_republishable_fields():
    raw = {
        "id": "abc",
        "source": "Le Monde",
        "lien": " https://www.lemonde.fr/a ",
        "titre": "<b>Titre</b> d&#8217;essai",
        "resume": "x " * 300,
        "publie_le": "2026-10-22T08:00:00Z",
        "recupere_le": "2026-10-22T09:00:00Z",
        "rubrique": None,
        "payload": {"description": "texte intégral éventuel"},
    }
    item = normalize_item(raw)
    assert item["titre"] == "Titre d’essai"
    assert item["lien"] == "https://www.lemonde.fr/a"
    assert len(item["extrait"]) <= 280
    assert "payload" not in item and item["rubrique"] is None
