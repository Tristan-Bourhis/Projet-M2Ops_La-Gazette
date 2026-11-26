"""Commandes : python -m gazette.mlops --help."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from gazette.db import PostgresThemeStore, connect, migrate
from gazette.evaluation import load_policy
from gazette.registry import Registry
from gazette.themes import load_config, load_encoder, run_themes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["evaluate", "promote", "rollback", "status", "review", "review-export"]
    )
    parser.add_argument(
        "--window",
        choices=["yesterday", "latest"],
        default="yesterday",
        help="latest : amorçage local sur les dernières 24 h",
    )
    parser.add_argument("--config", type=Path, default=Path("config/clustering.yaml"))
    parser.add_argument("--actor", default=os.environ.get("GITHUB_ACTOR", ""))
    parser.add_argument("--version")
    parser.add_argument("--run", type=int)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--promote", action="store_true", help="CI après merge uniquement")
    args = parser.parse_args()
    with connect(os.environ["DATABASE_URL"]) as conn:
        migrate(conn)
        registry = Registry(conn)
        if args.action == "status":
            result = registry.production()
        elif args.action == "rollback":
            result = registry.activate(None, args.actor, "rollback")
        elif args.action == "promote":
            result = registry.activate(args.version, args.actor)
        elif args.action == "review-export":
            from gazette.review import export_review

            if not args.run or not args.file:
                parser.error("review-export exige --run et --file (dossier de sortie)")
            run = conn.execute("SELECT * FROM runs WHERE id = %s", (args.run,)).fetchone()
            if not run:
                raise ValueError("Run inconnu.")
            result = export_review(run, args.file)
        elif args.action == "review":
            registry.review(args.run, args.actor, json.loads(args.file.read_text()))
            result = {"relecture": args.run}
        else:
            config, policy = load_config(args.config), load_policy()
            encoder = load_encoder(config["modele"]["nom"], config["modele"]["revision"])
            # Journée UTC d'hier, borne supérieure exclusive obtenue par 1 microseconde.
            from datetime import timedelta

            end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            end -= timedelta(microseconds=1)
            if args.window == "latest":
                end = datetime.now(UTC)
            result = run_themes(
                PostgresThemeStore(conn), encoder, config, end, policy=policy, publish=False
            )
            print(json.dumps(result, default=str, ensure_ascii=False))
            if result["evaluation"]["verdict"] != "candidat":
                return 1
            result = registry.candidate(result["run_id"], config, policy)
            if args.promote:
                registry.activate(result, args.actor)
        print(json.dumps(result, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
