"""Orchestration Prefect : la collecte toutes les 30 minutes, décrite en code."""

import logging
from pathlib import Path

from prefect import flow, get_run_logger

from gazette.collect import run_collection

INTERVAL_SECONDS = 30 * 60
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("gazette").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)


@flow(name="collecte", retries=1, retry_delay_seconds=300)
def collecte(sources: str = "sources.csv", output: str = "/data/articles_bruts") -> dict:
    summary = run_collection(Path(sources), Path(output))
    get_run_logger().info("Bilan de la collecte : %s", summary)
    if summary["sources"] and not summary["ok"]:
        raise RuntimeError("Aucune source n'a répondu : run marqué en échec.")
    if summary["en_sommeil"]:
        # Run en rouge tant qu'une source dort : l'alerte reste visible dans Prefect
        # jusqu'à la réparation (corriger l'URL dans sources.csv).
        raise RuntimeError(
            f"Source(s) en sommeil après 3 échecs : {', '.join(summary['en_sommeil'])}."
            " Vérifier l'URL dans sources.csv."
        )
    return summary


if __name__ == "__main__":
    collecte.serve(name="collecte-toutes-les-30-min", interval=INTERVAL_SECONDS)
