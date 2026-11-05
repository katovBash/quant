"""Run a frozen experiment, review it, then register a parity-checked paper candidate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(*parts: str) -> str:
    completed = subprocess.run([sys.executable, *parts], cwd=ROOT, text=True,
                               capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout)[-3000:])
    return completed.stdout.strip()


def run(experiment_dir: Path, *, existing_results: bool = False,
        strategy_dir: Path | None = None) -> dict:
    experiment_dir = experiment_dir.resolve()
    results = experiment_dir / "results"
    protocol = experiment_dir / "protocol.json"
    if not protocol.exists() or not (experiment_dir / "run.py").exists():
        raise ValueError("experiment needs protocol.json and run.py")
    results.mkdir(exist_ok=True)
    state = {"experiment": str(experiment_dir.relative_to(ROOT)), "stage": "STARTED",
             "run_mode": "existing_results_revalidated" if existing_results else "full_run"}
    target = results / "PIPELINE.json"
    try:
        from scripts.fetch_moex_dividends import inspect as inspect_dividends

        cached_dividends = ROOT / "data/dividends/moex_coverage.json"
        cookie = os.environ.get("MOEX_ISS_COOKIE")
        cached_check = (json.loads(cached_dividends.read_text(encoding="utf-8"))
                        if cached_dividends.is_file() else None)
        dividend_check = (cached_check if cached_check and
                          (existing_results or (not cookie and cached_check.get("status") == "SUBSCRIPTION_REQUIRED"))
                          else inspect_dividends(cookie=cookie))
        state["dividend_source"] = dividend_check["status"]
        review_path = results / "paper_review.json"
        if existing_results:
            command(str(ROOT / "skills/new-experiment/scripts/validate_run.py"),
                    "--protocol", str(protocol), "--results", str(results))
        else:
            command(str(experiment_dir / "run.py"))
        state["stage"] = "EXPERIMENT_CALCULATED"
        existing_review = (json.loads(review_path.read_text(encoding="utf-8"))
                           if review_path.is_file() else {})
        if (not existing_results or not existing_review.get("activation")
                or strategy_dir is not None):
            command(str(ROOT / "skills/experiment-paper-review/scripts/prepare.py"),
                    "--protocol", str(protocol), "--results", str(results))
        command(str(ROOT / "scripts/build_experiment_packages.py"),
                "--experiment", str(experiment_dir))
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["validation"] = json.loads((results / "validation.json").read_text(encoding="utf-8"))
        from guardrails.lifecycle import experiment_gate, publish

        gate, warnings = experiment_gate(review)
        state.update({"experiment_gate": gate, "warnings": warnings,
                      "review": str(review_path.relative_to(ROOT)),
                      "rule": review.get("rule"),
                      "stocks": [item["symbol"] for item in review.get("stocks", [])]})
        if existing_results and review.get("activation") and strategy_dir is None:
            state["stage"] = ("PAPER_REGISTERED_EXISTING" if gate == "PAPER_CANDIDATE"
                              else "PAPER_REGISTERED_REVIEW_REQUIRED")
            state["accounts"] = len(review["activation"].get("accounts", []))
        elif gate == "EXPERIMENT_CLOSED":
            state["stage"] = "CLOSED_RESEARCH"
        elif gate != "PAPER_CANDIDATE":
            state["stage"] = "REVIEW_REQUIRED"
        elif strategy_dir is None:
            state["stage"] = "NEEDS_FIXED_STRATEGY"
            state["next_action"] = "Create strategy.py, strategy.pine and measured parity.json; rerun with --strategy-dir"
        else:
            strategy_dir = strategy_dir.resolve()
            parity_script = strategy_dir / "check_parity.py"
            if not parity_script.exists():
                raise ValueError("strategy needs check_parity.py using the experiment's frozen candles")
            command(str(parity_script))
            command(str(ROOT / "skills/experiment-paper-review/scripts/activate.py"),
                    "--review", str(review_path), "--strategy-dir", str(strategy_dir))
            publish(ROOT / "papertrading/live", ROOT / "papertrading/setups/fleet", ROOT / "strategies")
            state["stage"] = "PAPER_REGISTERED"
            state["strategy_id"] = strategy_dir.name
            state["accounts"] = 10
    except Exception as exc:
        state["stage"] = "PIPELINE_ERROR"
        state["error"] = str(exc)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment_dir", type=Path)
    parser.add_argument("--existing-results", action="store_true")
    parser.add_argument("--strategy-dir", type=Path)
    args = parser.parse_args()
    result = run(args.experiment_dir, existing_results=args.existing_results,
                 strategy_dir=args.strategy_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["stage"] == "PIPELINE_ERROR" else 0)


if __name__ == "__main__":
    main()
