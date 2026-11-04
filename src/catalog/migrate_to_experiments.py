"""One-time move of historical EMA reviews out of the promoted strategy catalog."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ROOT / "strategies"
REVIEWS = ROOT / "experiments/.history/rule-reviews"
ACTIVE = "ema-cross-12-33-long-short"
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")


def destination(path: Path) -> Path:
    try:
        parts = path.relative_to(STRATEGIES).parts
    except ValueError:
        return path
    if not parts:
        return path
    if parts[0] == "template":
        return ROOT / "experiments/template/.archive/legacy_strategy_layout" / Path(*parts[1:])
    if not parts[0].startswith("ema-"):
        return path
    if parts[0] == ACTIVE and len(parts) > 1 and parts[1] in ("strategy.pine", "strategy.py"):
        return path
    if parts[0] == ACTIVE and len(parts) == 1:
        return path
    return REVIEWS / Path(*parts)


def rewrite(content: str, old_source: Path) -> str:
    new_source = destination(old_source)

    def replace(match: re.Match[str]) -> str:
        raw = match.group(2)
        if raw.startswith(("http://", "https://", "mailto:", "#", "/", "data:")):
            return match.group(0)
        target_text, sep, anchor = raw.partition("#")
        old_target = (old_source.parent / target_text).resolve()
        if not old_target.exists():
            return match.group(0)
        new_target = destination(old_target)
        new_rel = os.path.relpath(new_target, new_source.parent)
        if target_text.endswith("/") and old_target.is_dir():
            new_rel += "/"
        return match.group(1) + new_rel + (sep + anchor if sep else "") + match.group(3)

    return LINK.sub(replace, content)


def migrate() -> None:
    folders = sorted(p for p in STRATEGIES.glob("ema-*") if p.is_dir())
    if len(folders) != 21 or ACTIVE not in {p.name for p in folders}:
        raise RuntimeError("expected 21 original EMA directories, including the active strategy")
    if REVIEWS.exists():
        raise RuntimeError("review destination exists; this migration runs only once")
    for folder in folders:
        for filename in ("README.md", "strategy.pine", "results.csv"):
            if not (folder / filename).is_file():
                raise RuntimeError(f"missing {filename}: {folder}")
    markdown = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and "data" not in p.parts]
    rewritten = [(destination(p), rewrite(p.read_text(encoding="utf-8"), p)) for p in markdown]
    REVIEWS.mkdir(parents=True)
    for folder in folders:
        if folder.name == ACTIVE:
            target = REVIEWS / ACTIVE
            target.mkdir()
            for item in folder.iterdir():
                if item.name not in ("strategy.pine", "strategy.py"):
                    shutil.move(str(item), str(target / item.name))
        else:
            shutil.move(str(folder), str(REVIEWS / folder.name))
    shutil.move(str(STRATEGIES / "template"),
                str(ROOT / "experiments/template/.archive/legacy_strategy_layout"))
    for path, content in rewritten:
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"moved {len(folders) - 1} prototypes and 1 active review; rewrote {len(rewritten)} Markdown files")


if __name__ == "__main__":
    migrate()
