"""Allocate a run inside one stable indicator folder, never duplicate the family."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "experiments"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def create(indicator_id: str, run_id: str, root: Path = DEFAULT_ROOT) -> Path:
    if not SLUG.fullmatch(indicator_id) or not SLUG.fullmatch(run_id):
        raise ValueError("indicator and run IDs must use lowercase letters, digits and hyphens")
    existing = []
    for marker in root.rglob("indicator.json"):
        if ".history" in marker.parts:
            continue
        value = json.loads(marker.read_text(encoding="utf-8"))
        if value.get("indicator_id") == indicator_id:
            existing.append(marker.parent)
    if len(existing) > 1:
        raise ValueError("indicator_id is already duplicated: " + indicator_id)
    family = existing[0] if existing else root / indicator_id
    if family.exists() and not existing and any(family.iterdir()):
        raise ValueError("target folder exists without indicator.json: " + str(family))
    target = family / run_id
    if target.exists():
        raise ValueError("run already exists: " + str(target))
    target.mkdir(parents=True)
    marker = family / "indicator.json"
    index = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {
        "indicator_id": indicator_id, "runs": []}
    index["runs"] = sorted(set(index.get("runs", [])) | {run_id})
    marker.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target / "protocol.json").write_text(json.dumps({
        "indicator_id": indicator_id, "run_id": run_id, "status": "DRAFT",
        "hypothesis": None, "frozen_on": None, "source_snapshot": None,
        "eligible_universe": None, "corporate_actions": None,
        "signal_timeframes": None, "parameter_grid": None,
        "expected_variants": None, "split": None, "baseline": None,
        "signal_rule": None, "cost_status": None, "selection": None,
        "run_command": None}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target / "results").mkdir()
    summary_template = root / "template/SUMMARY.template.md"
    if summary_template.is_file():
        (target / "SUMMARY.md").write_text(
            f"# {run_id}\n\n" + summary_template.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("indicator_id")
    parser.add_argument("run_id")
    parser.add_argument("--experiments-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(create(args.indicator_id, args.run_id, args.experiments_root))


if __name__ == "__main__":
    main()
