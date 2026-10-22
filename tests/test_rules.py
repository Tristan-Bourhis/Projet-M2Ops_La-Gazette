"""Une règle, un test, avec un exemple réel relevé dans articles_bruts le 22/10/2026."""

from datetime import UTC, datetime, timedelta

import pytest

from gazette.normalize import title_key
from gazette.rules import RULE_IDS, find_duplicate, first_rule, jaccard

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


def item(titre="Tempête Austen : dix départements en vigilance orange", **fields):
    base = {
        "titre": titre,
        "extrait": "Un extrait d'article ordinaire.",
        "lien": "https://www.example.fr/actualite/article-123",
        "publie_le": NOW - timedelta(hours=2),
    }
    return base | fields


@pytest.mark.parametrize(
    ("rule", "example"),
    [
        ("R01_publi", item("Contenu sponsorisé : les meilleures offres de la rentrée")),
        ("R01_publi", item(lien="https://www.example.fr/publi-reportage/offre-123")),
        ("R02_horoscope", item("Horoscope du jeudi 22 octobre : ce que les astres vous réservent")),
        (
            "R03_programme_tv",
            item("« Harceleurs » : le téléfilm de France 2 est-il inspiré d’une histoire vraie ?"),
        ),
        (
            "R03_programme_tv",
            item("Wanted : on vous présente le nouveau jeu lancé sur M6 ce jeudi soir"),
        ),
        ("R04_jeux", item("La Dépêche du Midi lance son espace jeux : à vos neurones, jouez !")),
        ("R05_titre_gabarit", item("Vidéo. $content.TitleNoTags")),
        ("R06_titre_vide", item("")),
        ("R06_titre_vide", item("Vidéo")),
        ("R07_encodage", item("Le prix de lâ€™essence")),
        ("R08_date_future", item(publie_le=NOW + timedelta(days=1))),
        ("R09_perime", item(publie_le=NOW - timedelta(days=35))),
        ("R09_perime", item(publie_le=None)),
        ("R10_non_editorial", item("Appel à témoignages : Vous êtes à découvert ?")),
        ("R10_non_editorial", item("Feu, foi, baptême. Commentaire de l’Évangile du jeudi")),
        (
            "R10_non_editorial",
            item("Miss Lozère, une erreur du GPS… L’essentiel de l’actu en région"),
        ),
    ],
)
def test_rule_rejects_its_example(rule, example):
    assert first_rule(example, NOW) == rule


@pytest.mark.parametrize(
    "titre",
    [
        "Tempête Austen : dix départements en vigilance orange vendredi",
        "Jeux Olympiques d'hiver : la note salée des ruptures conventionnelles",  # pas R04
        "Présidentielle 2027 : un nouveau débat sur LCI ce jeudi",  # pas R03 : LCI, pas de « soir »
        "Un samedi sous le soleil",  # chronique courte mais légitime
    ],
)
def test_real_news_is_kept(titre):
    assert first_rule(item(titre), NOW) is None


def test_partnership_in_the_excerpt_is_not_publi():
    # Faux positif relevé le 22/10 : un vrai article politique « en partenariat avec les Restos ».
    news = item(extrait="LCI organise un débat. En partenariat avec les Restos du Cœur, …")
    assert first_rule(news, NOW) is None


def test_small_clock_drift_is_tolerated():
    assert first_rule(item(publie_le=NOW + timedelta(minutes=5)), NOW) is None


def test_exact_duplicate_from_another_source():
    original = "Le virus Shamonda détecté pour la première fois chez un humain, un patient mort"
    known = [("libe-1", title_key(original))]
    assert find_duplicate(title_key(original), known) == ("R11_doublon_exact", "libe-1")


def test_near_duplicate_two_words_apart():
    known = [
        (
            "of-1",
            title_key(
                "Le Prix Sakharov 2026 est accordé à la Cour pénale internationale,"
                " un pied de nez à Donald Trump"
            ),
        )
    ]
    key = title_key(
        "Le prix Sakharov 2026 attribué à la Cour pénale internationale,"
        " un pied de nez à Donald Trump"
    )
    assert jaccard(key, known[0][1]) >= 0.8
    assert find_duplicate(key, known) == ("R12_doublon_approche", "of-1")


def test_same_topic_different_title_is_not_a_duplicate():
    known = [
        ("of-1", title_key("Découverte d’un fœtus sans vie à Angers : une femme en garde à vue"))
    ]
    key = title_key("Un fœtus découvert à Angers : une femme placée en garde à vue, une enquête")
    assert find_duplicate(key, known) is None


def test_every_rule_has_a_unique_id():
    assert len(RULE_IDS) == len(set(RULE_IDS)) == 12
