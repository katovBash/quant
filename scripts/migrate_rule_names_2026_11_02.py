"""One-time, non-destructive rename of strategy rules to ticker-free IDs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ROOT / "strategies"
BACKUP = ROOT / "papertrading/migrations/2026-11-02-rule-names"
SLUGS = {
    "adx-di-14-20-long-short-plzl-1h": "adx-di-14-20-long-short-1h",
    "bollinger-breakout-10-2-long-short-smlt-4h": "bollinger-breakout-10-2-long-short-4h",
    "breakout-20-long-short-plzl-1h": "breakout-20-long-short-1h",
    "cci-reversal-10-100-long-short-jnos-4h": "cci-reversal-10-100-long-short-4h",
    "donchian-breakout-20-long-short-wush-1h": "donchian-breakout-20-long-short-1h",
    "ema-cross-12-33-long-short-plzl-1h": "ema-cross-12-33-long-short-1h",
    "ema-cross-13-48-long-short-plzl-vtbr-gazp-1h": "ema-cross-13-48-long-short-1h",
    "ema-level-25-atr05-long-short-universal-1d": "ema-level-25-atr05-long-short-1d",
    "ema-level-45-atr025-long-short-smlt-1h": "ema-level-45-atr025-long-short-1h",
    "ema-level-79-atr025-long-short-wush-1h": "ema-level-79-atr025-long-short-1h",
    "ema-level-94-atr05-long-short-sfin-1h": "ema-level-94-atr05-long-short-1h",
    "four-point-levels-5-1p5-long-short-kogk-1h": "four-point-levels-5-1p5-long-short-1h",
    "rsi-21-60-40-long-short-sfin-1h": "rsi-21-60-40-long-short-1h",
    "sma-cross-10-59-atr025-long-short-smlt-1h": "sma-cross-10-59-atr025-long-short-1h",
    "sma-cross-12-60-long-short-smlt-1h": "sma-cross-12-60-long-short-1h",
}
IDS = {**SLUGS, "ema-cross-12-33-long-short": "ema-cross-12-33-long-short-1h",
       "ema-level-45-atr025-long-short-universal-1d": "ema-level-25-atr05-long-short-1d"}


def main() -> None:
    if BACKUP.exists():
        raise RuntimeError(f"migration backup already exists: {BACKUP}")
    missing = [old for old in SLUGS if not (STRATEGIES / old).is_dir()]
    occupied = [new for new in SLUGS.values() if (STRATEGIES / new).exists()]
    if missing or occupied:
        raise RuntimeError(f"source missing: {missing}; destination occupied: {occupied}")

    BACKUP.mkdir(parents=True)
    for folder in (ROOT / "papertrading/setups").rglob("*.json"):
        dest = BACKUP / "before" / folder.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(folder, dest)
    for folder in (ROOT / "papertrading/live").glob("*/state.json"):
        dest = BACKUP / "before" / folder.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(folder, dest)
    (BACKUP / "mapping.json").write_text(json.dumps({"folders": SLUGS, "ids": IDS},
                                                   ensure_ascii=False, indent=2) + "\n")

    for old, new in SLUGS.items():
        (STRATEGIES / old).rename(STRATEGIES / new)

    changed = []
    extensions = {".md", ".py", ".pine", ".json", ".command"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in extensions:
            continue
        rel = path.relative_to(ROOT)
        if (rel.parts[0] == "data" or rel.parts[:2] == ("papertrading", "live") or
                rel.parts[:2] == ("papertrading", "migrations") or
                path == Path(__file__).resolve() or "results" in rel.parts or ".history" in rel.parts):
            continue
        try:
            before = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        after = before
        for old, new in SLUGS.items():
            after = after.replace(old, new)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append(str(rel))

    for path in (ROOT / "papertrading/setups").rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("strategy") in IDS:
            data["strategy"] = IDS[data["strategy"]]
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in (ROOT / "papertrading/live").glob("*/state.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("strategy") in IDS:
            data["strategy"] = IDS[data["strategy"]]
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for folder in STRATEGIES.iterdir():
        path = folder / "strategy.py"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for old, new in IDS.items():
            text = text.replace(f'STRATEGY_ID = "{old}"', f'STRATEGY_ID = "{new}"')
        path.write_text(text, encoding="utf-8")
    # The universal 1D file was copied from EMA 45 and had an incorrect ID.
    daily = STRATEGIES / "ema-level-25-atr05-long-short-1d/strategy.py"
    text = daily.read_text(encoding="utf-8")
    text = text.replace('STRATEGY_ID = "ema-level-45-atr025-long-short-1d"',
                        'STRATEGY_ID = "ema-level-25-atr05-long-short-1d"')
    daily.write_text(text, encoding="utf-8")
    (BACKUP / "README.md").write_text(
        "# Переименование правил 02.11.2026\n\n"
        "До запуска скрипта fleet остановлен. Старые setup и state.json сохранены в `before/`; "
        "исходные сделки и журналы не переписывались. `mapping.json` фиксирует соответствие старых и новых ID. "
        "Имена виртуальных счетов сохранены, чтобы не смешивать наблюдения разных бумаг.\n\n"
        "Проверить все setup, состояния и тесты до повторного запуска fleet.\n",
        encoding="utf-8")
    print(json.dumps({"renamed": len(SLUGS), "edited_text_files": len(changed),
                      "backup": str(BACKUP)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
