"""Run one background improvement phase and persist its progress."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from workers.optimization.control import ROOT, read_job, update_job

EXPERIMENT_PATH = re.compile(r"experiments/[a-z0-9-]+/[a-z0-9-]+")


def _log(message: str) -> None:
    print(datetime.now(timezone.utc).isoformat(timespec="seconds"), message, flush=True)


def _protected_digest(root: Path, strategy_id: str) -> str:
    """Detect accidental edits to the running strategy or its setup files."""
    files = [root / "strategies/catalog.json"]
    files += list((root / "strategies" / strategy_id).rglob("*"))
    files += list((root / "papertrading/setups/fleet").glob("*.json"))
    digest = hashlib.sha256()
    for path in sorted(path for path in files if path.is_file() and not path.name.endswith(".pyc")):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _codex(root: Path, job_id: str, stage: str, prompt: str,
           *, read_only: bool, timeout: int) -> str:
    executable = shutil.which("codex") or str(Path.home() / ".local/bin/codex")
    answer = root / "workers/optimization/runtime/jobs" / job_id / f"{stage}-answer.txt"
    command = [executable, "exec", "--ephemeral", "-C", str(root),
               "-s", "read-only" if read_only else "workspace-write",
               "-o", str(answer), "-"]
    _log(f"Агент: {stage} · запуск")
    result = subprocess.run(command, input=prompt, text=True, cwd=root,
                            stdout=sys.stdout, stderr=subprocess.STDOUT, timeout=timeout,
                            check=False)
    if result.returncode:
        raise RuntimeError(f"agent exited with code {result.returncode}; see worker log")
    if not answer.is_file():
        raise RuntimeError("agent did not write a final answer")
    return answer.read_text(encoding="utf-8").strip()


def _plan(root: Path, job_id: str) -> None:
    state = read_job(job_id, root)
    prompt = f"""Read skills/improve-paper-strategy/SKILL.md and spec/improve_paper_strategy.md.
Analyze active paper strategy {state['strategy_id']} ({state['strategy_label']}).
Parent experiment: {state['parent_experiment']}.
Read its fixed Python rule, experiment reports and paper outcomes. Do not edit files.
Return ONLY a JSON object with nonempty string keys diagnosis, hypothesis,
change, lost_winners_risk, comparison, data_limitations. Propose exactly one
testable change to reduce false entries or improve return, without claiming
it is profitable before running the experiment. The UI will show this plan
and let the user amend it before any test starts.
"""
    answer = _codex(root, job_id, "plan", prompt, read_only=True, timeout=900)
    try:
        clean = answer.strip()
        if clean.startswith("```json") and clean.endswith("```"):
            clean = clean[7:-3].strip()
        plan = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise RuntimeError("agent plan is not valid JSON") from exc
    fields = ("diagnosis", "hypothesis", "change", "lost_winners_risk",
              "comparison", "data_limitations")
    if not isinstance(plan, dict) or not all(isinstance(plan.get(key), str) and
                                             plan[key].strip() for key in fields):
        raise RuntimeError("agent plan is incomplete")
    update_job(job_id, {"stage": "WAITING_REVIEW", "plan": plan}, root)
    _log("План готов. Ожидает правки или запуска из UI.")


def _build_and_calculate(root: Path, job_id: str) -> None:
    state = read_job(job_id, root)
    if not isinstance(state.get("plan"), dict):
        raise RuntimeError("run requires a reviewed plan")
    update_job(job_id, {"stage": "BUILDING"}, root)
    existing = {path.resolve() for path in (root / "experiments").rglob("protocol.json")}
    protected_before = _protected_digest(root, state["strategy_id"])
    prompt = f"""Use skills/improve-paper-strategy/SKILL.md, skills/new-experiment/SKILL.md
and spec/improve_paper_strategy.md. Build ONE NEW reproducible experiment
for the active paper strategy {state['strategy_id']} with original experiment
{state['parent_experiment']}. Do not change that strategy, its setups, live
accounts or journals. Do not register paper accounts. This is the reviewed plan:
{json.dumps(state['plan'], ensure_ascii=False, indent=2)}
User correction or priority: {state.get('guidance') or 'none'}
Keep the fixed current rule as baseline on the same symbols, timeframes,
costs and data. Declare the full reasonable grid before running it. Record
the parent IDs and all variants in protocol.json. Implement causal Python
signals, review.pine and focused tests. Do a small smoke test only; DO NOT
run the full pipeline or create a fixed strategy. End with ONLY the new path
experiments/<family>/<run-id>, or BLOCKED: <reason> if the experiment cannot
be implemented reproducibly. Do not edit unrelated dirty files.
"""
    answer = _codex(root, job_id, "build", prompt, read_only=False, timeout=3600)
    if _protected_digest(root, state["strategy_id"]) != protected_before:
        raise RuntimeError("agent changed the running strategy or paper setups; inspect changes before continuing")
    if read_job(job_id, root)["stage"] == "CANCELLED":
        return
    if answer.startswith("BLOCKED:"):
        raise RuntimeError(answer[:1000])
    found = EXPERIMENT_PATH.findall(answer)
    if not found:
        raise RuntimeError("agent did not return a new experiment path")
    relative = found[-1]
    experiment = (root / relative).resolve()
    if not experiment.is_relative_to((root / "experiments").resolve()):
        raise RuntimeError("experiment escaped experiments/")
    if (experiment / "protocol.json").resolve() in existing:
        raise RuntimeError("agent reused an existing experiment instead of creating a new one")
    if not all((experiment / name).is_file() for name in ("protocol.json", "run.py", "review.pine")):
        raise RuntimeError("experiment missing protocol.json, run.py or review.pine")
    protocol = json.loads((experiment / "protocol.json").read_text(encoding="utf-8"))
    if protocol.get("parent_strategy") != state["strategy_id"]:
        raise RuntimeError("experiment does not identify its parent strategy")
    if not protocol.get("parent_experiment"):
        raise RuntimeError("experiment does not identify its parent experiment")
    update_job(job_id, {"stage": "CALCULATING", "experiment": relative}, root)
    if read_job(job_id, root)["stage"] == "CANCELLED":
        return
    _log(f"Запускаю полный пайплайн: {relative}")
    result = subprocess.run([sys.executable, "-m", "pipeline.run", relative], cwd=root,
                            stdout=sys.stdout, stderr=subprocess.STDOUT, timeout=7200,
                            check=False)
    if result.returncode:
        raise RuntimeError(f"pipeline exited with code {result.returncode}")
    pipeline = json.loads((experiment / "results/PIPELINE.json").read_text(encoding="utf-8"))
    if pipeline.get("stage") in ("PIPELINE_ERROR", "PAPER_REGISTERED"):
        raise RuntimeError(f"unexpected pipeline stage: {pipeline.get('stage')}")
    update_job(job_id, {"stage": "DONE", "pipeline_stage": pipeline.get("stage")}, root)
    _log(f"Готово: {relative}, {pipeline.get('stage')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("phase", choices=("plan", "run"))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.phase == "plan":
            _plan(root, args.job_id)
        else:
            _build_and_calculate(root, args.job_id)
    except Exception as exc:
        _log(f"Ошибка: {exc}")
        update_job(args.job_id, {"stage": "FAILED", "error": str(exc)}, root)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
