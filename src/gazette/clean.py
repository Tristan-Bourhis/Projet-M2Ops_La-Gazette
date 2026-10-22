"""Nettoyage : articles bruts -> articles_propres ou rejets, et rapport de qualité du jour."""

import argparse
import csv
import json
import logging
import os
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from gazette.bronze import slugify
from gazette.normalize import normalize_item
from gazette.rules import RULES, find_duplicate, first_rule

logger = logging.getLogger("gazette.clean")
DEDUP_WINDOW = timedelta(hours=48)
RULE_LABELS = {rule.id: rule.ecarte for rule in RULES} | {
    "R11_doublon_exact": "même titre qu'un article déjà gardé (dépêche reprise)",
    "R12_doublon_approche": "titre à deux mots près d'un article déjà gardé",
}


def log_event(level: int, event: str, **fields) -> None:
    payload = {"ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "evenement": event}
    logger.log(level, json.dumps(payload | fields, ensure_ascii=False, default=str))


class CleanStore(Protocol):
    def known_ids(self) -> set[str]: ...
    def recent_keys(self, since: datetime) -> list[tuple[str, str]]: ...
    def save(self, kept: list[dict], rejected: list[dict], at: datetime) -> None: ...
    def day_rows(self, day: date) -> list[dict]: ...
    def clean_since(self, since: datetime) -> list[dict]: ...
    def record_checks(self, checks: list, at: datetime) -> None: ...
    def failing_checks(self) -> set[str]: ...


class MemoryCleanStore:
    """Pour les tests et un lancement sans base : même interface que PostgresCleanStore."""

    def __init__(self):
        self.propres: dict[str, dict] = {}
        self.rejets: dict[str, dict] = {}
        self.checks: list[tuple[datetime, str, bool]] = []

    def known_ids(self):
        return set(self.propres) | set(self.rejets)

    def recent_keys(self, since):
        return [
            (row["id"], row["cle_titre"])
            for row in self.propres.values()
            if row["publie_le"] and row["publie_le"] >= since
        ]

    def save(self, kept, rejected, at):
        for row in kept:
            self.propres.setdefault(row["id"], row | {"traite_le": at})
        for row in rejected:
            self.rejets.setdefault(row["id"], row | {"traite_le": at})

    def day_rows(self, day):
        rows = [r | {"regle": None} for r in self.propres.values()] + list(self.rejets.values())
        return [r for r in rows if r["traite_le"].astimezone(UTC).date() == day]

    def clean_since(self, since):
        return [r for r in self.propres.values() if r["traite_le"] >= since]

    def record_checks(self, checks, at):
        self.checks += [(at, check.id, check.ok) for check in checks]

    def failing_checks(self):
        last: dict[str, bool] = {}
        for _, check_id, ok in sorted(self.checks):
            last[check_id] = ok
        return {check_id for check_id, ok in last.items() if not ok}


def raw_path(item: dict) -> str:
    """Traçabilité : d'un article propre ou rejeté, on retrouve son fichier brut."""
    return f"articles_bruts/{slugify(item['source'])}/{item['id']}.json"


def new_raw_items(raw_dir: Path, known: set[str]) -> Iterator[dict]:
    """Items bruts pas encore traités. Le nom du fichier est l'id : rien à relire sinon."""
    for path in sorted(raw_dir.glob("*/*.json")):
        if path.stem in known:
            continue
        try:
            yield json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_event(logging.ERROR, "brut_illisible", fichier=str(path), erreur=str(error))


def clean_pass(raw_dir: Path, store: CleanStore, now: datetime) -> dict:
    """Un passage : normalise, applique les règles, dédoublonne, enregistre."""
    items = [normalize_item(raw) for raw in new_raw_items(raw_dir, store.known_ids())]
    # Le plus ancien d'abord : en cas de doublon, on garde l'article d'origine.
    items.sort(key=lambda item: (item["publie_le"] or now, item["source"]))
    known_keys = store.recent_keys(now - DEDUP_WINDOW)
    kept, rejected = [], []
    for item in items:
        item["brut"] = raw_path(item)
        rule, original = first_rule(item, now), None
        if rule is None:
            duplicate = find_duplicate(item["cle_titre"], known_keys)
            if duplicate:
                rule, original = duplicate
        if rule:
            rejected.append(item | {"regle": rule, "doublon_de": original})
        else:
            kept.append(item)
            known_keys.append((item["id"], item["cle_titre"]))
    store.save(kept, rejected, now)
    summary = {
        "entres": len(items),
        "gardes": len(kept),
        "rejetes": len(rejected),
        "par_regle": dict(Counter(row["regle"] for row in rejected).most_common()),
    }
    log_event(logging.INFO, "nettoyage_termine", **summary)
    return summary


def build_report(rows: list[dict], day: date, last_pass: dict | None = None) -> str:
    """Rapport du jour : entrés, gardés, rejetés par règle et par source, top 5 des rejets."""
    rejected = [row for row in rows if row["regle"]]
    by_rule = Counter(row["regle"] for row in rejected)
    by_source: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_source[row["source"]]["entres"] += 1
        by_source[row["source"]]["rejetes" if row["regle"] else "gardes"] += 1
    total = len(rows)
    lines = [
        f"# Rapport de qualité du {day.isoformat()}",
        "",
        f"- Items entrés : **{total}**",
        f"- Gardés : **{total - len(rejected)}**",
        f"- Rejetés : **{len(rejected)}** ({rate(len(rejected), total)})",
    ]
    if last_pass is not None:
        lines.append(
            f"- Dernier passage : {last_pass['entres']} entrés, {last_pass['gardes']} gardés,"
            f" {last_pass['rejetes']} rejetés"
        )
    lines += ["", "## Les 5 rejets les plus fréquents", ""]
    lines += [
        f"{rank}. `{rule}` : {count} ({RULE_LABELS.get(rule, '')})"
        for rank, (rule, count) in enumerate(by_rule.most_common(5), start=1)
    ] or ["Aucun rejet."]
    lines += ["", "## Par règle", "", "| Règle | Rejets | Exemple |", "|---|---|---|"]
    for rule, count in by_rule.most_common():
        example = next(row["titre"] for row in rejected if row["regle"] == rule)
        lines.append(f"| `{rule}` | {count} | {cell(example)} |")
    lines += ["", "## Par source", "", "| Source | Entrés | Gardés | Rejetés | Taux |"]
    lines.append("|---|---|---|---|---|")
    for source, counts in sorted(by_source.items()):
        lines.append(
            f"| {source} | {counts['entres']} | {counts['gardes']} | {counts['rejetes']}"
            f" | {rate(counts['rejetes'], counts['entres'])} |"
        )
    return "\n".join(lines) + "\n"


def rate(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f} %" if whole else "-"


def cell(text: str, limit: int = 80) -> str:
    text = text.replace("|", "/")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def write_report(reports_dir: Path, day: date, markdown: str) -> Path:
    """Archive rapports/qualite-YYYY-MM-DD.md, réécrit à chaque passage avec le cumul du jour."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"qualite-{day.isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def source_names(sources_csv: Path) -> list[str]:
    with sources_csv.open(encoding="utf-8-sig", newline="") as stream:
        return sorted(row["nom"].strip() for row in csv.DictReader(stream) if row.get("nom"))


def process(
    store: CleanStore,
    raw_dir: Path,
    reports_dir: Path,
    sources: list[str],
    now: datetime,
    webhook_url: str | None = None,
) -> dict:
    """Nettoyage, rapport, contrôles et alerte : ce que fait la tâche après chaque collecte."""
    from gazette.quality import alert_on_new_failures, metrics, run_checks

    summary = clean_pass(raw_dir, store, now)
    day = now.astimezone(UTC).date()
    report = build_report(store.day_rows(day), day, summary)
    path = write_report(reports_dir, day, report)
    checks = run_checks(store, sources, now)
    alert_on_new_failures(store, checks, webhook_url)
    store.record_checks(checks, now)
    return summary | {
        "rapport": str(path),
        "rapport_markdown": report,
        "controles": [check.as_dict() for check in checks],
        "metriques": metrics(store, checks, now),
    }


def run_cleaning(raw_dir: Path, reports_dir: Path, sources_csv: Path) -> dict:
    """Avec DATABASE_URL : tables articles_propres et rejets. Sinon : en mémoire."""
    now = datetime.now(UTC)
    sources = source_names(sources_csv)
    webhook = os.environ.get("ALERT_WEBHOOK_URL") or None
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return process(MemoryCleanStore(), raw_dir, reports_dir, sources, now, webhook)
    from gazette.db import PostgresCleanStore, connect, migrate

    with connect(database_url) as conn:
        migrate(conn)
        return process(PostgresCleanStore(conn), raw_dir, reports_dir, sources, now, webhook)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nettoyer les articles bruts.")
    parser.add_argument("--bruts", type=Path, default=Path("/data/articles_bruts"))
    parser.add_argument("--rapports", type=Path, default=Path("/data/rapports"))
    parser.add_argument("--sources", type=Path, default=Path("sources.csv"))
    parser.add_argument(
        "--alerte-test", action="store_true", help="envoyer une alerte de test au webhook"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.alerte_test:
        from gazette.quality import send_alert

        sent = send_alert(
            "🧪 La gazette : alerte de test, le canal fonctionne.",
            os.environ.get("ALERT_WEBHOOK_URL"),
        )
        return 0 if sent else 1
    summary = run_cleaning(args.bruts, args.rapports, args.sources)
    return 0 if all(check["ok"] for check in summary["controles"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
