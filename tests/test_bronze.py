from gazette.bronze import item_id, slugify, write_raw_item


def item(link="https://example.org/a"):
    return {"id": item_id("Ouest-France", link), "source": "Ouest-France", "lien": link}


def test_same_article_gives_same_id():
    assert item_id("Ouest-France", "https://Example.org/a?utm_source=rss#top") == item_id(
        "Ouest-France", "https://example.org/a"
    )


def test_same_link_in_two_sources_gives_two_items():
    assert item_id("Le Monde", "https://example.org/a") != item_id(
        "Ouest-France", "https://example.org/a"
    )


def test_two_passes_zero_duplicate(tmp_path):
    assert write_raw_item(tmp_path, item()) is True
    assert write_raw_item(tmp_path, item()) is False
    assert len(list(tmp_path.rglob("*.json"))) == 1
    assert not list(tmp_path.rglob("*.tmp"))


def test_source_folder_name():
    assert slugify("Dernières Nouvelles d’Alsace") == "dernieres-nouvelles-d-alsace"
