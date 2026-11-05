"""Publish operational paper-account categories from recorded daily equity."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, datetime
from pathlib import Path

from eval.evaluate import classify_paper


def review_account(folder: Path) -> dict:
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    review_path = folder / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    started = datetime.fromisoformat(state["started_at"]).date()
    dates: list[date] = []
    equity: list[float] = []
    path = folder / "equity.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not {"date", "strategy_equity"}.issubset(reader.fieldnames or []):
                raise ValueError(f"invalid equity file: {path}")
            for row in reader:
                day = date.fromisoformat(row["date"])
                value = float(row["strategy_equity"])
                if (dates and day <= dates[-1]) or not math.isfinite(value) or value <= 0:
                    raise ValueError(f"invalid equity observation: {path}")
                dates.append(day)
                equity.append(value)
    category = classify_paper(
        dates, equity, started=started, initial_capital=float(state["initial_capital"]),
        costs_verified=review.get("costs_verified") is True,
        has_short=state.get("mode") in ("short", "long_short"),
        short_costs_verified=review.get("short_costs_verified") is True,
    )
    return {"account_id": folder.name, "symbol": state["symbol"], "strategy": state["strategy"],
            "started_on": started.isoformat(), "last_equity_date": dates[-1].isoformat() if dates else None,
            "costs_verified": review.get("costs_verified") is True,
            "short_costs_verified": review.get("short_costs_verified") is True,
            **category}


def publish(live_root: Path) -> list[dict]:
    rows = []
    for folder in sorted(live_root.iterdir()):
        if not folder.is_dir() or not (folder / "state.json").exists():
            continue
        result = review_account(folder)
        target = folder / "paper_status.json"
        temp = target.with_suffix(".json.tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(target)
        rows.append(result)
    lines = ["# Статусы виртуальных счетов", "",
             "`APPROVED_30D_PAPER` означает только положительный результат виртуального счёта "
             "после 30 календарных дней с подтверждёнными расходами. Это не разрешение торговать "
             "реальными деньгами и не доказательство устойчивого преимущества.", "",
             "| Счёт | Правило | Категория | Дней | Доходность | Дата последней оценки |",
             "| --- | --- | --- | ---: | ---: | --- |"]
    for row in rows:
        ret = "—" if row["paper_return_pct"] is None else f"{row['paper_return_pct']:+.2f}%"
        lines.append(f"| [{row['account_id']}]({row['account_id']}/paper_status.json) | `{row['strategy']}` | "
                     f"`{row['paper_status']}` | {row['paper_calendar_days']} | {ret} | "
                     f"{row['last_equity_date'] or '—'} |")
    if not rows:
        lines.append("| Нет счетов | — | — | — | — | — |")
    lines += ["", "Категории: `NO_DATA` — нет ряда капитала; `OBSERVING` — меньше 30 дней; "
              "`COSTS_UNVERIFIED` — месяц прошёл, но расходы не подтверждены; "
              "`NOT_APPROVED_30D` — доходность за месяц неположительна. "
              "При изменении торгового правила создаётся новый счёт и новый отсчёт 30 дней.", ""]
    target = live_root / "STATUS.md"
    temp = target.with_suffix(".md.tmp")
    temp.write_text("\n".join(lines), encoding="utf-8")
    temp.replace(target)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, default=Path("papertrading/live"))
    args = parser.parse_args()
    print(json.dumps(publish(args.live_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
