import json
from datetime import UTC, datetime, timedelta

import httpx

from gazette.clean import MemoryCleanStore, clean_pass, process
from gazette.quality import alert_on_new_failures, run_checks

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


def write_raw(directory, id_, source, titre, hours_ago=2):
    folder = directory / source.lower().replace(" ", "-")
    folder.mkdir(parents=True, exist_ok=True)
    raw = {
        "id": id_,
        "source": source,
        "lien": f"https://example.fr/{id_}",
        "titre": titre,
        "resume": "Un extrait.",
        "rubrique": None,
        "publie_le": (NOW - timedelta(hours=hours_ago)).isoformat(),
        "recupere_le": NOW.isoformat(),
        "payload": {},
    }
    (folder / f"{id_}.json").write_text(json.dumps(raw), encoding="utf-8")


def bruts(tmp_path):
    d = tmp_path / "articles_bruts"
    write_raw(d, "a1", "Libération", "Le virus Shamonda détecté chez un humain en France", 3)
    write_raw(d, "a2", "Le Monde", "Le virus Shamonda détecté chez un humain en France", 1)
    write_raw(d, "a3", "Midi Libre", "Appel à témoignages : vous êtes à découvert ?")
    write_raw(d, "a4", "Le Monde", "Tempête Austen : dix départements en vigilance orange")
    return d


def test_clean_pass_keeps_rejects_and_traces(tmp_path):
    store = MemoryCleanStore()
    summary = clean_pass(bruts(tmp_path), store, NOW)
    assert (summary["gardes"], summary["rejetes"]) == (2, 2)
    assert store.rejets["a2"]["regle"] == "R11_doublon_exact"
    assert store.rejets["a2"]["doublon_de"] == "a1"  # le plus ancien est gardé
    assert store.rejets["a3"]["regle"] == "R10_non_editorial"
    assert store.propres["a4"]["brut"] == "articles_bruts/le-monde/a4.json"


def test_second_pass_processes_nothing_again(tmp_path):
    store, raw = MemoryCleanStore(), bruts(tmp_path)
    clean_pass(raw, store, NOW)
    assert clean_pass(raw, store, NOW)["entres"] == 0


def test_report_counts_by_rule_and_source(tmp_path):
    result = process(MemoryCleanStore(), bruts(tmp_path), tmp_path / "rapports", [], NOW)
    report = (tmp_path / "rapports" / "qualite-2026-10-22.md").read_text(encoding="utf-8")
    assert result["rapport_markdown"] == report
    assert "Items entrés : **4**" in report and "`R11_doublon_exact` | 1" in report
    assert "| Le Monde | 2 | 1 | 1 | 50 % |" in report


def test_checks_detect_silent_source_and_alert_once(tmp_path):
    store = MemoryCleanStore()
    clean_pass(bruts(tmp_path), store, NOW)
    checks = run_checks(store, ["Le Monde", "Ouest-France"], NOW)
    failing = {c.id: c for c in checks if not c.ok}
    assert list(failing) == ["C04_aucune_source_muette"]
    sent = []
    transport = httpx.MockTransport(
        lambda r: sent.append(json.loads(r.content)) or httpx.Response(204)
    )
    alerted = alert_on_new_failures(store, checks, "https://hooks.example/x", transport)
    assert alerted == {"C04_aucune_source_muette"}
    store.record_checks(checks, NOW, alerted)
    alerted = alert_on_new_failures(store, checks, "https://hooks.example/x", transport)
    store.record_checks(checks, NOW, alerted)
    assert len(sent) == 1 and "Ouest-France" in sent[0]["content"]  # pas de répétition


def test_failed_alert_is_retried_next_pass(tmp_path):
    store = MemoryCleanStore()
    clean_pass(bruts(tmp_path), store, NOW)
    checks = run_checks(store, ["Ouest-France"], NOW)
    # 1er passage : pas de .env ; 2e : Discord en panne ; 3e : l'alerte part enfin.
    store.record_checks(checks, NOW, alert_on_new_failures(store, checks, None))
    down = httpx.MockTransport(lambda r: httpx.Response(503))
    store.record_checks(checks, NOW, alert_on_new_failures(store, checks, "https://h/x", down))
    sent = []
    ok = httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(204))
    alerted = alert_on_new_failures(store, checks, "https://h/x", ok)
    assert alerted == {"C04_aucune_source_muette"} and len(sent) == 1


def test_too_greedy_rule_is_detected(tmp_path):
    d = tmp_path / "articles_bruts"
    for n in range(10):
        write_raw(d, f"h{n}", "Le Figaro", f"Horoscope du jour numéro {n} pour tous")
    store = MemoryCleanStore()
    clean_pass(d, store, NOW)
    rate = next(c for c in run_checks(store, [], NOW) if c.id == "C03_taux_rejet_par_source")
    assert not rate.ok and "Le Figaro" in rate.detail
