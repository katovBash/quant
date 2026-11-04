"""Check that promoted code and historical EMA reports stay separate."""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ROOT / "strategies"
REVIEWS = ROOT / "experiments/.history/rule-reviews"


def main() -> int:
    problems = []
    selected = sorted(p for p in STRATEGIES.iterdir() if p.is_dir())
    if not selected:
        problems.append("no selected strategies")
    for folder in selected:
        for name in ("README.md", "strategy.pine"):
            if not (folder / name).is_file():
                problems.append(f"{folder.name}: missing {name}")
        for name in ("results.csv", ".archive", "tickers", "success"):
            if (folder / name).exists():
                problems.append(f"{folder.name}: historical {name} belongs in experiments")
    reviews = sorted(p for p in REVIEWS.glob("ema-*") if p.is_dir())
    for folder in reviews:
        table = folder / "results.csv"
        if not (folder / "README.md").is_file() or not table.is_file():
            problems.append(f"{folder.name}: missing README or results.csv")
            continue
        with table.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if len({r["ticker"] for r in rows}) != 258 or any(
            not r["status"] or not r["outcome"] for r in rows
        ):
            problems.append(f"{folder.name}: incomplete 258-ticker table")
    if problems:
        print("Layout issues:\n" + "\n".join(problems))
        return 1
    print(f"OK: {len(selected)} selected strategies, {len(reviews)} historical EMA reviews.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
