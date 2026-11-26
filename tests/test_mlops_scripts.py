"""Déploiement : compensation réelle du script et absence de corpus dans les logs publics."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("fail", [False, True])
def test_deploy_compensates_failed_restart_without_leaking_articles(tmp_path, fail):
    docker = tmp_path / "docker"
    docker.write_text("""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['COMMAND_LOG'], 'a') as out:
    out.write(json.dumps(args)+'\\n')
if args[0] == 'inspect':
    print('old-image')
elif '-Atc' in args:
    print('old-version')
elif 'evaluate' in args:
    print(json.dumps({'run_id': 8, 'nb_articles': 100, 'metriques': {'silhouette': .2},
                      'evaluation': {'version': 'new-version'},
                      'themes': ['PRIVATE_ARTICLE_TEXT']}))
    print('"new-version"')
elif ('up' in args and args[-1] == 'collecteur' and '--no-build' not in args
      and os.environ.get('FAIL_RESTART') == 'yes'):
    sys.exit(1)
""")
    docker.chmod(0o755)
    log = tmp_path / "commands.jsonl"
    result = subprocess.run(
        ["sh", str(ROOT / "bin/deploy-model")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "PATH": str(tmp_path) + ":" + os.environ["PATH"],
            "COMMAND_LOG": str(log),
            "GITHUB_ACTOR": "test-ci",
            "FAIL_RESTART": "yes" if fail else "no",
        },
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert "PRIVATE_ARTICLE_TEXT" not in result.stdout + result.stderr
    assert result.returncode == (1 if fail else 0)
    if fail:
        restore = next(c for c in calls if "promote" in c)
        assert restore[restore.index("--version") + 1] == "old-version"
        assert ["tag", "old-image", "projetm2ops-collecteur:latest"] in calls
        assert any("--no-build" in c for c in calls)
    else:
        assert not any("promote" in c for c in calls)
        assert any("run_daily_themes" in " ".join(c) for c in calls)
