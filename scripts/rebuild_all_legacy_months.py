"""Resume monthly replay for old grids, then validate and refresh each package."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rebuild_legacy_months import SUPPORTED


def run(command: list[str], log: Path) -> int:
    with log.open("w", encoding="utf-8") as stream:
        return subprocess.run(command, cwd=ROOT, stdout=stream,
                              stderr=subprocess.STDOUT, check=False).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip", nargs="*", default=[])
    args = parser.parse_args()
    log_dir = ROOT / "experiments/.rebuild_logs"
    log_dir.mkdir(exist_ok=True)
    state_file = log_dir / "status.json"
    status = json.loads(state_file.read_text()) if state_file.is_file() else {}
    for name in SUPPORTED:
        if name in args.skip:
            continue
        folder = ROOT / "experiments" / name
        status[name] = {"state": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat()}
        state_file.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
        print(name, "replaying", flush=True)
        replay = run([sys.executable, str(ROOT / "scripts/rebuild_legacy_months.py"),
                      "--experiment", str(folder)], log_dir / f"{name}.replay.log")
        validate = None
        package = None
        if replay == 0:
            validate = run([sys.executable, str(ROOT / "skills/new-experiment/scripts/validate_run.py"),
                            "--protocol", str(folder / "protocol.json"),
                            "--results", str(folder / "results")],
                           log_dir / f"{name}.validation.log")
            package = run([sys.executable, str(ROOT / "scripts/build_experiment_packages.py"),
                           "--experiment", str(folder)],
                          log_dir / f"{name}.package.log")
        state = ("DONE" if replay == 0 and validate == 0 and package == 0 else
                 "REVIEW_ONLY" if replay == 0 and validate == 1 and package == 0 else
                 "ERROR")
        status[name] = {"state": state,
                        "replay_exit": replay, "validation_exit": validate,
                        "package_exit": package,
                        "finished_at": datetime.now(timezone.utc).isoformat()}
        state_file.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
        print(name, status[name]["state"], flush=True)


if __name__ == "__main__":
    main()
