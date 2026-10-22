"""Contrôles de données : des faits vérifiés sur les vraies données après chaque passage.

Ils ne testent pas le code (c'est le rôle de la CI) : ils disent si les données du jour sont
saines, publient leurs chiffres et alertent l'équipe quand un fait devient faux.
Assertions maison plutôt qu'un outil dédié : quatre faits simples, sans dépendance de plus.
"""

import logging
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

import httpx

from gazette.clean import CleanStore, log_event
from gazette.rules import FUTURE_TOLERANCE

MAX_REJECT_RATE = 0.8
MIN_ITEMS_FOR_RATE = 10  # en début de journée, 3 rejets sur 3 ne veulent rien dire
SILENCE = timedelta(hours=12)
CHECK_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class Check:
    id: str
    ok: bool
    valeur: float
    seuil: float
    detail: str

    def as_dict(self) -> dict:
        return asdict(self)


def run_checks(store: CleanStore, sources: list[str], now: datetime) -> list[Check]:
    recent = store.clean_since(now - CHECK_WINDOW)
    future = [r for r in recent if r["publie_le"] and r["publie_le"] > now + FUTURE_TOLERANCE]
    empty = [r for r in recent if not r["titre"].strip()]
    day = store.day_rows(now.astimezone(UTC).date())
    entered, rejected = Counter(r["source"] for r in day), Counter()
    rejected.update(r["source"] for r in day if r["regle"])
    rates = {
        source: rejected[source] / count
        for source, count in entered.items()
        if count >= MIN_ITEMS_FOR_RATE
    }
    too_greedy = {s: r for s, r in rates.items() if r > MAX_REJECT_RATE}
    recent_sources = {r["source"] for r in store.clean_since(now - SILENCE)}
    silent = [source for source in sources if source not in recent_sources]
    return [
        Check(
            "C01_aucune_date_future",
            not future,
            len(future),
            0,
            ", ".join(r["id"][:12] for r in future[:5]) or "aucune",
        ),
        Check(
            "C02_aucun_titre_vide",
            not empty,
            len(empty),
            0,
            ", ".join(r["id"][:12] for r in empty[:5]) or "aucun",
        ),
        Check(
            "C03_taux_rejet_par_source",
            not too_greedy,
            round(max(rates.values(), default=0), 3),
            MAX_REJECT_RATE,
            ", ".join(f"{s} {r:.0%}" for s, r in too_greedy.items()) or "toutes ≤ 80 %",
        ),
        Check(
            "C04_aucune_source_muette",
            not silent,
            len(silent),
            0,
            ", ".join(silent) + " : aucun article propre depuis 12 h" if silent else "aucune",
        ),
    ]


def metrics(store: CleanStore, checks: list[Check], now: datetime) -> dict:
    """Chiffres publiés à chaque passage (artefact Prefect ; le TD 8 les collectera)."""
    day = store.day_rows(now.astimezone(UTC).date())
    rejected = sum(1 for row in day if row["regle"])
    values = {
        "articles_entres_jour": len(day),
        "articles_gardes_jour": len(day) - rejected,
        "articles_rejetes_jour": rejected,
        "taux_rejet_jour": round(rejected / len(day), 3) if day else 0.0,
        "controles_en_echec": sum(not check.ok for check in checks),
    }
    log_event(logging.INFO, "metriques_qualite", **values)
    for check in checks:
        level = logging.INFO if check.ok else logging.ERROR
        log_event(level, "controle_qualite", **check.as_dict())
    return values


def send_alert(message: str, webhook_url: str | None, transport=None) -> bool:
    """Webhook Discord ou Slack : « content » pour Discord, « text » pour Slack."""
    if not webhook_url:
        log_event(logging.ERROR, "alerte_non_envoyee", raison="ALERT_WEBHOOK_URL absent")
        return False
    try:
        with httpx.Client(timeout=10, transport=transport) as client:
            response = client.post(webhook_url, json={"content": message, "text": message})
            response.raise_for_status()
    except httpx.HTTPError as error:
        log_event(logging.ERROR, "alerte_non_envoyee", raison=str(error))
        return False
    log_event(logging.WARNING, "alerte_envoyee", message=message)
    return True


def alert_on_new_failures(
    store: CleanStore, checks: list[Check], webhook_url: str | None, transport=None
) -> set[str]:
    """Alerte quand un contrôle passe au rouge, pas à chaque passage tant qu'il le reste.

    Renvoie les contrôles rouges dont l'équipe a bien été prévenue. Si l'envoi échoue
    (pas de .env, Discord injoignable), ils n'en font pas partie : on réessaie au passage
    suivant, au lieu de perdre l'alerte.
    """
    already = store.alerted_checks()
    failing = {check.id for check in checks if not check.ok}
    new = [check for check in checks if not check.ok and check.id not in already]
    if not new:
        return failing & already
    lines = [f"🚨 La gazette : {len(new)} contrôle(s) qualité en échec"]
    lines += [f"• {check.id} : {check.detail}" for check in new]
    sent = send_alert("\n".join(lines), webhook_url, transport)
    return failing & already | ({check.id for check in new} if sent else set())
