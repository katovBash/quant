"""Give every experiment one inspectable review package without inventing evidence.

Existing measured validation and paper reviews are preserved. For old runs
without the new data, the generated files explicitly block paper activation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from guardrails.lifecycle import experiment_gate
from scripts.add_monthly_report_sections import update as add_monthly_section
from src.research.experiment_report import _side_analysis
from scripts.standardize_summaries import standardize

EXPERIMENTS = ROOT / "experiments"
REQUIRED_RESULTS = ("all_variants.csv", "monthly_returns.csv", "summary.json",
                    "skipped.csv")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def catalog_pine(folder: Path) -> list[Path]:
    catalog = load(ROOT / "strategies/catalog.json")
    found = []
    for rule in catalog.get("rules", []):
        if rule.get("experiment") not in (folder.name, folder.relative_to(EXPERIMENTS).as_posix()):
            continue
        path = ROOT / "strategies" / rule["id"] / "strategy.pine"
        if path.is_file():
            found.append(path)
    return found


def package(folder: Path) -> dict:
    results = folder / "results"
    results.mkdir(exist_ok=True)
    protocol_path = folder / "protocol.json"
    protocol = load(protocol_path)
    manifest_path = results / "manifest.json"
    if not manifest_path.is_file():
        write(manifest_path, {
            "record_type": "reconstructed_inventory_not_original_run_manifest",
            "source_snapshot": protocol.get("source_snapshot"),
            "timeframes": protocol.get("signal_timeframes"),
            "variants": protocol.get("expected_variants"),
            "note": "The historical run did not save a manifest; this file records available metadata only."})

    missing = [name for name in REQUIRED_RESULTS if not (results / name).is_file()]
    if not protocol_path.is_file():
        missing.insert(0, "protocol.json")
    if not (folder / "run.py").is_file():
        missing.append("run.py")
    if not protocol.get("parameter_grid"):
        missing.append("protocol.parameter_grid")
    validation_path = results / "validation.json"
    validation_error = None
    old_validation = load(validation_path)
    if (not old_validation or old_validation.get("record_type") == "legacy_package_check_not_full_validator") and not missing:
        completed = subprocess.run([
            sys.executable, str(ROOT / "skills/new-experiment/scripts/validate_run.py"),
            "--protocol", str(protocol_path), "--results", str(results)],
            cwd=ROOT, capture_output=True, text=True, check=False)
        if completed.returncode and not validation_path.is_file():
            validation_error = (completed.stderr or completed.stdout)[-1200:]
    if not validation_path.is_file():
        corporate = protocol.get("corporate_actions")
        write(validation_path, {
            "status": "REVIEW_ONLY", "structural_ok": False,
            "record_type": "legacy_package_check_not_full_validator",
            "missing_required_evidence": missing,
            "validation_error": validation_error,
            "corporate_actions": {"status": corporate.get("status", "unchecked")
                                  if isinstance(corporate, dict) else "unchecked"},
            "note": "Re-run the frozen experiment and the full validator before selecting paper accounts."})
    validation = load(validation_path)
    add_monthly_section(folder)
    report_path = results / "REPORT.md"
    if report_path.is_file() and "## Long и short по отдельности" not in report_path.read_text(encoding="utf-8"):
        body = report_path.read_text(encoding="utf-8").rstrip()
        side_text = _side_analysis(results)
        report_path.write_text(body + "\n\n## Long и short по отдельности\n\n" +
                               side_text + "\n", encoding="utf-8")

    paper_path = results / "paper_review.json"
    paper_md = results / "PAPER_REVIEW.md"
    existing_paper = load(paper_path)
    if (not existing_paper or existing_paper.get("record_type") == "generated_blocker") and validation.get("structural_ok"):
        completed = subprocess.run([
            sys.executable, str(ROOT / "skills/experiment-paper-review/scripts/prepare.py"),
            "--protocol", str(protocol_path), "--results", str(results)],
            cwd=ROOT, capture_output=True, text=True, check=False)
        if completed.returncode and not paper_path.is_file():
            validation_error = (completed.stderr or completed.stdout)[-1200:]
    if not paper_path.is_file():
        blockers = ["Новый проверочный флоу не завершён"]
        blockers.extend("Отсутствует " + name for name in missing)
        if validation_error:
            blockers.append("Ошибка валидатора: " + validation_error)
        if not validation.get("structural_ok") and not missing:
            blockers.append("Полная проверка структуры не пройдена; см. validation.json")
        write(paper_path, {"status": "REVIEW_ONLY", "record_type": "generated_blocker",
                           "protocol": protocol,
                           "validation": validation, "rule": None,
                           "stocks": [], "blockers": blockers})
    paper = load(paper_path)
    gate, gate_warnings = experiment_gate(paper)

    local_pine = [p for p in folder.glob("*.pine") if p.is_file()]
    linked_pine = catalog_pine(folder)
    pine_paths = sorted({*local_pine, *linked_pine})
    pine_status = {
        "status": "AVAILABLE_FOR_REVIEW" if pine_paths else "MISSING_FIXED_PINE",
        "files": [rel(path) for path in pine_paths],
        "verified_against_experiment": False,
        "note": "A Pine file alone does not prove parity with Python signals or activate paper trading."
    }
    write(results / "PINE_STATUS.json", pine_status)

    if not paper_md.is_file():
        links = ["[протокол](../protocol.json)", "[манифест](manifest.json)",
                 "[валидация](validation.json)", "[общий отчёт](REPORT.md)",
                 "[машинный обзор](paper_review.json)", "[Pine статус](PINE_STATUS.json)"]
        if (results / "monthly_returns.csv").is_file():
            links.append("[каждый месяц](monthly_returns.csv)")
        pine_text = ", ".join(f"[{path.name}]({Path(os.path.relpath(path, results)).as_posix()})"
                              for path in pine_paths) if pine_paths else "Фиксированного Pine пока нет."
        blockers = paper.get("blockers", [])
        paper_md.write_text(
            "# Кандидат и виртуальная проверка\n\n"
            f"Статус: **{paper.get('status', 'REVIEW_ONLY')}**. "
            "Это обзор исторического расчёта, не разрешение на реальные сделки.\n\n"
            + " · ".join(links) + "\n\n"
            "## Что известно\n\n"
            f"Структура: {'пройдена' if validation.get('structural_ok') else 'не пройдена'}; "
            f"статус данных: `{validation.get('status', 'REVIEW_ONLY')}`; "
            f"корпоративные события: `{validation.get('corporate_actions', {}).get('status', 'unchecked')}`.\n\n"
            "## Pine для ручной проверки\n\n" + pine_text + "\n\n"
            "## До виртуального запуска\n\n"
            + "\n".join("- " + str(item) for item in blockers)
            + "\n- Выбрать одну общую настройку и все акции, прошедшие годовой порог.\n"
            "- Создать фиксированные Python/Pine и проверить совпадение сигналов.\n"
            "- Проверить лоты и расходы; только затем зарегистрировать виртуальные счета.\n",
            encoding="utf-8")

    state = {
        "experiment": rel(folder),
        "monthly_coverage": (
            "FULL_GRID" if (results / "monthly_returns.csv").is_file() else
            "FIXED_CANDIDATE_ONLY" if (results / "candidate_monthly_returns.csv").is_file() else
            "MISSING"),
        "status": "PAPER_STOPPED" if paper.get("deactivation") else
                  "CLOSED" if paper.get("decision", {}).get("status") == "CLOSED" else
                  "PAPER_REGISTERED_REVIEW" if paper.get("activation") and gate != "PAPER_CANDIDATE" else
                  "PAPER_REGISTERED" if paper.get("activation") else
                  "READY_FOR_FIXED_STRATEGY" if gate == "PAPER_CANDIDATE" else
                  "REVIEW_ONLY",
        "paper_gate": gate,
        "paper_gate_warnings": gate_warnings,
        "missing_required_evidence": missing,
        "validation_status": validation.get("status"),
        "paper_review_status": paper.get("status"),
        "pine": pine_status["status"],
        "files": {name: rel(results / name) for name in
                  ("manifest.json", "validation.json", "REPORT.md", "PAPER_REVIEW.md",
                   "PINE_STATUS.json", "candidate_monthly_returns.csv", "CANDIDATE_MONTHLY.md",
                   "trade_side_summary.csv")
                  if (results / name).is_file()},
    }
    write(results / "PACKAGE_STATUS.json", state)
    summary_path = folder / "SUMMARY.md"
    if not summary_path.is_file():
        summary_path.write_text(
            f"# {folder.name}\n\n"
            f"Статус проверки: `{state['status']}`. "
            "Результаты и решение лежат в одном комплекте файлов.\n\n"
            "[Протокол](protocol.json) · [Манифест](results/manifest.json) · "
            "[Проверка данных](results/validation.json) · "
            "[Помесячный отчёт](results/REPORT.md) · "
            "[Решение о paper](results/PAPER_REVIEW.md) · "
            "[Pine статус](results/PINE_STATUS.json).\n",
            encoding="utf-8")
    else:
        summary = summary_path.read_text(encoding="utf-8")
        if "results/REPORT.md" not in summary:
            summary_path.write_text(
                summary.rstrip() + "\n\n## Проверяемые результаты\n\n"
                "[Помесячный отчёт](results/REPORT.md) · "
                "[Проверка данных](results/validation.json) · "
                "[Решение для paper](results/PAPER_REVIEW.md) · "
                "[Статус Pine](results/PINE_STATUS.json).\n",
                encoding="utf-8")
    standardize(folder)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, help="one experiment; default: all active experiments")
    args = parser.parse_args()
    folders = [args.experiment.resolve()] if args.experiment else sorted(
        p.parent for p in EXPERIMENTS.rglob("protocol.json") if ".history" not in p.parts)
    states = [package(folder) for folder in folders]
    if args.experiment is not None:
        states = [load(p.parent / "results/PACKAGE_STATUS.json")
                  for p in sorted(EXPERIMENTS.rglob("protocol.json"))
                  if ".history" not in p.parts and
                  (p.parent / "results/PACKAGE_STATUS.json").is_file()]
    write(EXPERIMENTS / "PACKAGE_STATUS.json", {"experiments": states})
    print(json.dumps({"experiments": len(states),
                      "paper_registered": sum(s["status"] == "PAPER_REGISTERED" for s in states),
                      "ready_for_fixed_strategy": sum(s["status"] == "READY_FOR_FIXED_STRATEGY" for s in states),
                      "review_only": sum(s["status"] == "REVIEW_ONLY" for s in states)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
