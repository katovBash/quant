"""One-time migration to a small visible strategy directory.

Move verbose old ticker pages/charts to a hidden archive and rewrite existing
local Markdown links so archived evidence remains reachable. Results are built
separately by build_strategy_tables.py before this migration.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ROOT / "strategies"
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")


def folders() -> list[Path]:
    return [p for p in sorted(STRATEGIES.glob("ema-*")) if p.is_dir()]


def map_target(path: Path) -> Path:
    try:
        rest = path.relative_to(STRATEGIES)
    except ValueError:
        return path
    if not rest.parts or rest.parts[0] not in {p.name for p in folders()}:
        return path
    strategy = STRATEGIES / rest.parts[0]
    if len(rest.parts) >= 3 and rest.parts[1:3] == ("code", "strategy.pine"):
        return strategy / "strategy.pine"
    if len(rest.parts) >= 2 and rest.parts[1] in ("code", "tickers", "success"):
        return strategy / ".archive" / Path(*rest.parts[1:])
    return path


def map_source(path: Path) -> Path:
    if path.parent in folders() and path.name == "README.md":
        return path.parent / ".archive/legacy_README.md"
    return map_target(path)


def rewrite_links(content: str, old_source: Path, new_source: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        raw = match.group(2)
        if raw.startswith(("http://", "https://", "mailto:", "#", "/")):
            return match.group(0)
        path_text, anchor = (raw.split("#", 1) + [""])[:2] if "#" in raw else (raw, "")
        old_target = (old_source.parent / path_text).resolve()
        if not old_target.exists():
            return match.group(0)
        new_target = map_target(old_target)
        new_path = os.path.relpath(new_target, new_source.parent)
        if raw.endswith("/") and new_target.is_dir():
            new_path += "/"
        return match.group(1) + new_path + ("#" + anchor if anchor else "") + match.group(3)

    return LINK.sub(replace, content)


def migrate() -> None:
    targets = folders()
    if any((p / ".archive").exists() for p in targets):
        raise RuntimeError("strategy archive already exists; migration is one-time")
    markdown = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and "data" not in p.parts]
    rewritten = [(map_source(p), rewrite_links(p.read_text(encoding="utf-8"), p, map_source(p)))
                 for p in markdown]
    for strategy in targets:
        if not (strategy / "results.csv").exists() or not (strategy / "code/strategy.pine").exists():
            raise RuntimeError(f"missing table or Pine: {strategy}")
    for strategy in targets:
        archive = strategy / ".archive"
        archive.mkdir()
        shutil.move(str(strategy / "README.md"), str(archive / "legacy_README.md"))
        shutil.move(str(strategy / "code/strategy.pine"), str(strategy / "strategy.pine"))
        for name in ("code", "tickers", "success"):
            shutil.move(str(strategy / name), str(archive / name))
        ds_store = strategy / ".DS_Store"
        if ds_store.exists():
            shutil.move(str(ds_store), str(archive / ".DS_Store"))
    for target, content in rewritten:
        target.write_text(content, encoding="utf-8")
    print(f"migrated {len(targets)} strategies; rewrote {len(rewritten)} Markdown files")


if __name__ == "__main__":
    migrate()
