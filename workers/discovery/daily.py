"""Opt-in, idempotent daily research orchestration.

The model proposes and implements a *new* hypothesis. This module owns the
switch, duplicate guard, frozen protocol check, pipeline invocation and report.
It never bypasses pipeline.run or sends live orders.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from workers.discovery.control import ROOT, read_json, record_run, runtime, set_enabled, status, write_json
from workers.experiment.create import build as create_experiment

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def fingerprint(candidate: dict) -> str:
    """Stable identity for a rule, excluding tuned parameter values and names."""
    content = {
        "signal": _normalized(candidate["signal_rule"]),
        "entry": _normalized(candidate["entry_rule"]),
        "exit": _normalized(candidate["exit_rule"]),
        "roles": sorted(_normalized(x) for x in candidate["indicator_roles"]),
        "timeframes": sorted(candidate["timeframes"]),
    }
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_candidate(candidate: dict) -> None:
    if candidate.get("status") == "NO_IDEA":
        return
    if candidate.get("status") != "IDEA":
        raise ValueError("planner must return IDEA or NO_IDEA")
    for key in ("indicator_id", "run_id"):
        if not isinstance(candidate.get(key), str) or not SLUG.fullmatch(candidate[key]):
            raise ValueError(f"invalid {key}")
    for key in ("source_url", "source_evidence", "hypothesis", "signal_rule",
                "entry_rule", "exit_rule", "next_research"):
        if not isinstance(candidate.get(key), str) or not candidate[key].strip():
            raise ValueError(f"missing {key}")
    if not candidate["source_url"].startswith("https://"):
        raise ValueError("source_url must be HTTPS")
    for key in ("indicator_roles", "timeframes"):
        if not isinstance(candidate.get(key), list) or not candidate[key] or not all(
                isinstance(x, str) and x.strip() for x in candidate[key]):
            raise ValueError(f"missing {key}")
    if not isinstance(candidate.get("parameter_axes"), dict) or not candidate["parameter_axes"]:
        raise ValueError("parameter_axes must declare a nonempty grid")
    for name, values in candidate["parameter_axes"].items():
        if not isinstance(name, str) or not name or not isinstance(values, list) or not values:
            raise ValueError("each parameter axis needs a name and nonempty values")
        if any(isinstance(value, (dict, list)) for value in values):
            raise ValueError("parameter axis values must be scalar")
    if not isinstance(candidate.get("excluded_variants"), list):
        raise ValueError("excluded_variants must be a list")


def _known_duplicate(candidate: dict, root: Path, registry: dict,
                     prepared_path: Path | None = None) -> str | None:
    key = fingerprint(candidate)
    if key in registry:
        return f"fingerprint already registered: {registry[key].get('experiment', key)}"
    for path in (root / "experiments").rglob("protocol.json"):
        if ".history" in path.parts or "template" in path.parts:
            continue
        if prepared_path is not None and path.resolve() == (prepared_path / "protocol.json").resolve():
            continue
        protocol = read_json(path)
        if protocol.get("discovery", {}).get("fingerprint") == key:
            return f"fingerprint already in {path.relative_to(root)}"
        if (protocol.get("indicator_id") == candidate["indicator_id"] and
                protocol.get("run_id") == candidate["run_id"]):
            return f"run already exists: {path.relative_to(root)}"
    return None


def _codex(root: Path, day: str, stage: str, prompt: str,
           *, read_only: bool, timeout: int) -> str:
    folder = runtime(root)
    folder.mkdir(parents=True, exist_ok=True)
    answer = folder / f"{day}-{stage}-answer.txt"
    log = folder / f"{day}-{stage}.log"
    command = ["codex", "exec", "--ephemeral", "-C", str(root),
               "-s", "read-only" if read_only else "workspace-write",
               "-o", str(answer), "-"]
    with log.open("w", encoding="utf-8") as output:
        try:
            completed = subprocess.run(command, input=prompt, text=True, cwd=root,
                                       stdout=output, stderr=subprocess.STDOUT,
                                       timeout=timeout, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Codex {stage} unavailable: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(f"Codex {stage} failed (exit {completed.returncode}); see {log}")
    if not answer.is_file():
        raise RuntimeError(f"Codex {stage} did not write its answer; see {log}")
    return answer.read_text(encoding="utf-8").strip()


def plan(root: Path, day: str) -> dict:
    prompt = f"""Read spec/daily_discovery.md and the active experiments' protocol.json files.
Today is {day} Europe/Moscow. Find one NEW, testable trading hypothesis from a
verifiable primary research source or an author's own documented method. Use
the available web tools; if you cannot verify a source, return NO_IDEA. Compare
the signal meaning, entry, exit and timeframes with existing experiments, not
just their folder names. Enumerate meaningful indicator roles and a parameter
grid BEFORE testing. Do not write files or run an experiment in this stage.
Respond with only one JSON object. For an idea use these exact keys:
status="IDEA", indicator_id, run_id, source_url, source_evidence (where the
exact rule is described), hypothesis, signal_rule, entry_rule, exit_rule,
indicator_roles (array), timeframes (array), parameter_axes (object of arrays),
excluded_variants (array), next_research. If no verifiable nonduplicate idea,
return {{"status":"NO_IDEA","reason":"...","next_research":"..."}}.
Do not claim that a cited trader published a rule if the rule is your adaptation.
"""
    try:
        value = json.loads(_codex(root, day, "plan", prompt, read_only=True, timeout=900))
    except json.JSONDecodeError as exc:
        raise ValueError("planner did not return JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("planner response must be an object")
    return value


def build(root: Path, day: str, candidate: dict) -> None:
    create_experiment(root, day, candidate, _codex)


def build_strategy(root: Path, day: str, candidate: dict, experiment: Path) -> Path:
    prompt = f"""Use the experiment-paper-review skill for
{experiment.relative_to(root)}. The completed pipeline says NEEDS_FIXED_STRATEGY.
Create exactly one fixed Python strategy, TradingView Pine and check_parity.py
for the selected rule, using the experiment's frozen candles. Do not change
the selected setting or stock list; do not register accounts yourself. Run
the parity check and report its measured results. If parity fails, say so and
do not fabricate a pass. Do not touch unrelated dirty files. End with only
the path to strategies/<strategy-id>, or BLOCKED plus the reason.
Candidate: {json.dumps(candidate, ensure_ascii=False)}
"""
    answer = _codex(root, day, "strategy", prompt, read_only=False, timeout=3600)
    if not answer.startswith("strategies/"):
        raise RuntimeError(f"strategy builder blocked: {answer[:300]}")
    target = (root / answer).resolve()
    if target.parent != (root / "strategies").resolve():
        raise ValueError("strategy path escapes strategies/")
    for name in ("strategy.py", "strategy.pine", "check_parity.py"):
        if not (target / name).is_file():
            raise ValueError(f"fixed strategy missing {name}")
    return target


def _verify_experiment(root: Path, candidate: dict, key: str) -> Path:
    path = (root / "experiments" / candidate["indicator_id"] / candidate["run_id"]).resolve()
    if path.parent != (root / "experiments" / candidate["indicator_id"]).resolve():
        raise ValueError("experiment path escapes indicator family")
    for name in ("protocol.json", "run.py", "review.pine"):
        if not (path / name).is_file():
            raise ValueError(f"new experiment missing {name}")
    protocol = read_json(path / "protocol.json")
    if protocol.get("indicator_id") != candidate["indicator_id"] or protocol.get("run_id") != candidate["run_id"]:
        raise ValueError("protocol IDs differ from proposed hypothesis")
    if protocol.get("status") == "DRAFT" or not protocol.get("expected_variants"):
        raise ValueError("protocol is not preregistered with a full parameter grid")
    for field in ("source_url", "signal_rule", "entry_rule", "exit_rule"):
        if _normalized(str(protocol.get(field, ""))) != _normalized(candidate[field]):
            raise ValueError(f"protocol changed declared {field}")
    for field in ("eligible_universe", "corporate_actions", "cost_status", "start",
                  "split", "selection", "run_command"):
        if not protocol.get(field):
            raise ValueError(f"protocol missing {field}")
    if not protocol.get("parameter_grid") or not protocol.get("signal_timeframes"):
        raise ValueError("protocol lacks grid or signal timeframes")
    if set(protocol["signal_timeframes"]) != set(candidate["timeframes"]):
        raise ValueError("protocol changed the declared timeframes")
    axes = protocol["parameter_grid"].get("axes", {})
    for name, values in candidate["parameter_axes"].items():
        actual = axes.get(name, {}).get("values")
        if actual != values:
            raise ValueError(f"protocol changed parameter axis {name}")
    protocol["discovery"] = {"fingerprint": key,
                              "source_url": candidate["source_url"],
                              "source_evidence": candidate["source_evidence"],
                              "indicator_roles": candidate["indicator_roles"],
                              "excluded_variants": candidate["excluded_variants"]}
    write_json(path / "protocol.json", protocol)
    return path


def _report(root: Path, day: str, result: dict) -> Path:
    folder = runtime(root) / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{day}.md"
    lines = [f"# Discovery · {day}", "", f"Статус: `{result['status']}`.", "",
             "## Проверено", "", result.get("tested") or "Новый расчёт не запускался.", ""]
    if result.get("experiment"):
        lines += [f"Эксперимент: `{result['experiment']}`.", ""]
    if result.get("source_url"):
        lines += [f"Источник: {result['source_url']}", ""]
    lines += ["## Отклонено или остановлено", "", result.get("reason") or "Нет.", "",
              "## Запущено", "",
              (f"Виртуальные счета: {result['accounts']}." if result.get("accounts") else
               "Виртуальные счета зарегистрированы; число см. в PIPELINE.json.")
              if result["status"] == "PAPER_REGISTERED" else "Новых paper-счетов нет.", "",
              "## Далее", "", result.get("next_research") or "Смотреть сохранённый отчёт и этап пайплайна.", ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def run_daily(root: Path = ROOT, *, day: str | None = None,
              retry: bool = False, candidate_file: Path | None = None,
              prepared: bool = False,
              planner=plan, builder=build, strategy_builder=build_strategy,
              pipeline_runner=None) -> dict:
    day = day or datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()
    if not status(root)["enabled"]:
        return {"status": "DISABLED", "reason": "Enable discovery first; no agent was started."}
    if prepared and candidate_file is None:
        return {"status": "FAILED", "reason": "--prepared requires --candidate-file"}
    folder = runtime(root)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "runner.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "ALREADY_RUNNING"}
        previous = status(root)
        registry_file = folder / "registry.json"
        registry = read_json(registry_file)
        if previous["last_run_day"] == day:
            if not retry or previous["last_result"] not in ("FAILED", "STOPPED", "NO_IDEA", "RUNNING"):
                return {"status": "ALREADY_DONE", "last_result": previous["last_result"],
                        "last_report": previous["last_report"]}
            reserved = [row for row in registry.values() if row.get("day") == day]
            if reserved:
                experiment = reserved[0]["experiment"]
                return {"status": "RECOVERY_REQUIRED", "experiment": experiment,
                        "reason": "Hypothesis already reserved; automatic retry would duplicate a build or backtest.",
                        "next_action": f"Inspect {experiment}; after repair run python3 -m pipeline.run {experiment}."}
        record_run(day, "RUNNING", None, root)
        result: dict = {"status": "FAILED", "reason": "unknown failure"}
        key = None
        try:
            candidate = (json.loads(candidate_file.read_text(encoding="utf-8"))
                         if candidate_file is not None else planner(root, day))
            validate_candidate(candidate)
            if candidate["status"] == "NO_IDEA":
                result = {"status": "NO_IDEA", "reason": candidate.get("reason", "No verified new idea."),
                          "next_research": candidate.get("next_research")}
            else:
                key = fingerprint(candidate)
                rel = f"experiments/{candidate['indicator_id']}/{candidate['run_id']}"
                duplicate = _known_duplicate(candidate, root, registry,
                                             (root / rel) if prepared else None)
                if duplicate:
                    result = {"status": "DUPLICATE", "reason": duplicate,
                              "next_research": candidate["next_research"]}
                else:
                    registry[key] = {"experiment": rel, "status": "RESERVED", "day": day,
                                     "source_url": candidate["source_url"]}
                    write_json(registry_file, registry)
                    if not status(root)["enabled"]:
                        result = {"status": "STOPPED", "reason": "Discovery was turned off before build."}
                    else:
                        if not prepared:
                            builder(root, day, candidate)
                        experiment = _verify_experiment(root, candidate, key)
                        registry[key]["status"] = "BUILT"
                        write_json(registry_file, registry)
                        if not status(root)["enabled"]:
                            result = {"status": "STOPPED", "reason": "Discovery was turned off before pipeline."}
                        else:
                            if pipeline_runner is None:
                                from pipeline.run import run as pipeline_runner
                            state = pipeline_runner(experiment)
                            stage = state["stage"]
                            if stage == "NEEDS_FIXED_STRATEGY" and not prepared and status(root)["enabled"]:
                                strategy = strategy_builder(root, day, candidate, experiment)
                                state = (pipeline_runner(experiment, existing_results=True,
                                                         strategy_dir=strategy)
                                         if status(root)["enabled"] else
                                         {"stage": "STOPPED", "warnings": [
                                             "Discovery was turned off before paper registration."]})
                                stage = state["stage"]
                            result = {"status": stage, "pipeline_stage": stage,
                                      "reason": state.get("error") or "; ".join(state.get("warnings", [])),
                                      "experiment": rel, "source_url": candidate["source_url"],
                                      "next_research": candidate["next_research"]}
                            calculated = read_json(experiment / "results/summary.json")
                            result["tested"] = (f"{calculated.get('symbols', '—')} акций; "
                                                f"{calculated.get('rows', '—')} расчётов по вариантам. "
                                                f"Пайплайн: `{stage}`.")
                            result["accounts"] = state.get("accounts", 0)
                    registry[key]["status"] = result["status"]
                    write_json(registry_file, registry)
        except Exception as exc:
            result = {"status": "FAILED", "reason": f"{type(exc).__name__}: {exc}"}
            if key and key in registry:
                registry[key]["status"] = "FAILED"
                write_json(registry_file, registry)
        report = _report(root, day, result)
        record_run(day, result["status"], str(report.relative_to(root)), root)
        return result


def finalize(root: Path, experiment: Path) -> dict:
    """Record a later parity/paper pipeline outcome for today's discovered run."""
    target = experiment.resolve()
    try:
        rel = str(target.relative_to(root.resolve()))
    except ValueError as exc:
        raise ValueError("experiment must be inside this repository") from exc
    registry_file = runtime(root) / "registry.json"
    registry = read_json(registry_file)
    matches = [(key, row) for key, row in registry.items() if row.get("experiment") == rel]
    if len(matches) != 1:
        raise ValueError("experiment is not uniquely registered by daily discovery")
    key, entry = matches[0]
    pipeline_file = target / "results/PIPELINE.json"
    pipeline = read_json(pipeline_file)
    stage = pipeline.get("stage")
    if stage not in ("PAPER_REGISTERED", "PAPER_REGISTERED_REVIEW_REQUIRED",
                     "PAPER_REGISTERED_EXISTING", "REVIEW_REQUIRED", "CLOSED_RESEARCH",
                     "PIPELINE_ERROR", "NEEDS_FIXED_STRATEGY"):
        raise ValueError(f"pipeline has no final stage in {pipeline_file}")
    result = {"status": stage, "pipeline_stage": stage, "experiment": rel,
              "source_url": entry.get("source_url"),
              "reason": pipeline.get("error") or "; ".join(pipeline.get("warnings", []))}
    calculated = read_json(target / "results/summary.json")
    result["tested"] = (f"{calculated.get('symbols', '—')} акций; "
                        f"{calculated.get('rows', '—')} расчётов по вариантам. "
                        f"Пайплайн: `{stage}`.")
    result["accounts"] = pipeline.get("accounts", 0)
    day = entry["day"]
    report = _report(root, day, result)
    entry["status"] = stage
    write_json(registry_file, registry)
    if status(root)["last_run_day"] == day:
        record_run(day, stage, str(report.relative_to(root)), root)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("on", "off", "status", "run", "retry", "finalize"))
    parser.add_argument("--candidate-file", type=Path)
    parser.add_argument("--prepared", action="store_true")
    parser.add_argument("--experiment", type=Path)
    args = parser.parse_args()
    if args.command == "on":
        output = set_enabled(True)
    elif args.command == "off":
        output = set_enabled(False)
    elif args.command == "status":
        output = status()
    elif args.command == "finalize":
        if args.experiment is None:
            parser.error("finalize requires --experiment")
        output = finalize(ROOT, args.experiment)
    else:
        output = run_daily(retry=args.command == "retry", candidate_file=args.candidate_file,
                           prepared=args.prepared)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if output.get("status") in ("FAILED", "PIPELINE_ERROR"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
