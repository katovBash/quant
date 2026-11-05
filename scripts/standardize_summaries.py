"""Keep active experiment summaries aligned with the shared template."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "experiments/template/SUMMARY.template.md").read_text(encoding="utf-8")
START = "<!-- experiment-summary:start -->"
END = "<!-- experiment-summary:end -->"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def standardize(folder: Path) -> None:
    results = folder / "results"
    protocol = read(folder / "protocol.json")
    validation = read(results / "validation.json")
    paper = read(results / "paper_review.json")
    pine = read(results / "PINE_STATUS.json")
    summary = read(results / "summary.json")
    report = (results / "REPORT.md").read_text(encoding="utf-8") if (results / "REPORT.md").is_file() else ""
    coverage = re.search(r"^Покрытие: (.+)$", report, re.MULTILINE)
    side_file = results / "trade_side_summary.csv"
    if side_file.is_file():
        with side_file.open(newline="", encoding="utf-8-sig") as stream:
            side_rows = list(csv.DictReader(stream))
        cases = len({(r["symbol"], r["timeframe"], r["variant"]) for r in side_rows})
        side_status = f"{cases} выбранных примеров; вся сетка не пересчитана" if cases else "нет данных"
    else:
        side_status = "не выполнен"
    hypothesis = protocol.get("hypothesis")
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        hypothesis = "Гипотеза описана в исходном протоколе."
    hypothesis = hypothesis.strip().replace("\n", " ")
    if len(hypothesis) > 350:
        hypothesis = hypothesis[:347].rstrip() + "…"
    values = {
        "DATA_STATUS": str(validation.get("status", "не проверено")),
        "COVERAGE": coverage.group(1) if coverage else "см. отчёт",
        "PAPER_STATUS": ("закрыт после оценки" if paper.get("decision", {}).get("status") == "CLOSED"
                         else "зарегистрированы виртуальные счета" if paper.get("activation")
                         else "кандидат не зарегистрирован"),
        "HYPOTHESIS": hypothesis,
        "SNAPSHOT": str(protocol.get("source_snapshot", "не указан")),
        "COST_STATUS": str(protocol.get("cost_status") or summary.get("cost_model") or "не указан"),
        "CORPORATE_STATUS": str(validation.get("corporate_actions", {}).get("status", "unchecked")),
        "GAP_PAIRS": str(validation.get("monthly_validation", {}).get("gap_pairs", "не проверено")),
        "SIDE_STATUS": side_status,
        "PINE_STATUS": str(pine.get("status", "не проверен")),
    }
    block = TEMPLATE
    for key, value in values.items():
        block = block.replace("{{" + key + "}}", value)
    path = folder / "SUMMARY.md"
    body = path.read_text(encoding="utf-8") if path.is_file() else f"# {folder.name}\n"
    if START in body and END in body:
        body = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n*", "", body,
                      count=1, flags=re.DOTALL)
    body = re.sub(r"\n## Краткая сводка\n.*?(?=\n## |\Z)", "\n", body,
                  count=1, flags=re.DOTALL)
    title, _, rest = body.partition("\n")
    if not title.startswith("# "):
        raise ValueError(f"SUMMARY needs a title: {path}")
    path.write_text(title + "\n\n" + block.rstrip() + "\n\n" + rest.lstrip("\n"),
                    encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path)
    args = parser.parse_args()
    folders = [args.experiment] if args.experiment else sorted(
        p.parent for p in (ROOT / "experiments").rglob("protocol.json")
        if ".history" not in p.parts and "template" not in p.parts)
    for folder in folders:
        standardize(folder.resolve())
        print(folder)


if __name__ == "__main__":
    main()
