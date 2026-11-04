"""Build one honest, comparable ticker table per researched EMA rule.

Historical source files are preserved in experiments/.history/legacy-ema. Missing rows
remain explicit; this script never converts a different strategy's result into
a result for the current Pine file.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / "experiments/.history/rule-reviews"
LEGACY = ROOT / "experiments/.history/legacy-ema"
SCAN = LEGACY / "12-33-cross/execute/research"
VARIANTS = LEGACY / "12-33-cross/execute/variants/long-short/execute/variants"
UNIVERSE = SCAN / "daily_weekly_monthly/universe.json"
FIELDS = (
    "ticker", "company", "timeframe", "status", "outcome", "return_pct", "closed_trades",
    "winning_trades", "win_rate_pct", "profit_factor", "max_drawdown_pct",
    "first_bar", "last_bar", "source", "notes",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def spec_for(slug: str) -> tuple[list[dict[str, str]], str]:
    """Return rows from the matching implementation only, plus provenance."""
    base = SCAN / "daily_weekly_monthly/all_results.csv"
    intraday = SCAN / "intraday/all_results.csv"
    if slug in ("ema-cross-12-33-long", "ema-cross-12-33-long-short"):
        fast, slow, mode = {
            "ema-cross-12-33-long": (12, 33, "long"),
            "ema-cross-12-33-long-short": (12, 33, "long_short"),
        }[slug]
        rows = [r for p in (base, intraday) for r in read_csv(p)
                if (r["fast"], r["slow"], r["mode"]) == (str(fast), str(slow), mode)]
        return [dict(r, _return=r["net_return_pct"], _trades=r["closed_trades"],
                     _wins=r["winning_trades"], _pf=r["profit_factor"],
                     _dd=r["max_drawdown_pct"], _source="MOEX ISS · scan_ema.py") for r in rows], \
            f"EMA {fast}/{slow}, {mode}; MOEX ISS scan_ema.py"

    if slug == "ema-cross-12-33-adx-filter":
        rows = [r for r in read_csv(VARIANTS / "adx-filter/execute/all_results.csv")
                if r["adx_threshold"] == "20"]
        return [dict(r, _return=r["return_pct"], _trades=r["closed_trades"],
                     _wins=r["winning_trades"], _pf=r["profit_factor"],
                     _dd=r["max_drawdown_pct"], _source="MOEX ISS · ADX20") for r in rows], \
            "ADX14, порог 20 (значение Pine по умолчанию)"

    filters = {
        "ema-cross-12-33-rsi-filter": "rsi-filter",
        "ema-cross-12-33-channel-zone": "channel-zone-filter",
        "ema-cross-12-33-regression-channel": "regression-channel",
        "ema-cross-12-33-trendline-filter": "trendline-filter",
    }
    if slug in filters:
        name = filters[slug]
        rows = read_csv(VARIANTS / name / "execute/all_results.csv")
        return [dict(r, _return=r["filter_return_pct"],
                     _trades=r["filter_closed_trades"], _wins=r["filter_winning_trades"],
                     _pf=r["filter_profit_factor"], _dd=r["filter_max_drawdown_pct"],
                     _source=f"MOEX ISS · {name}") for r in rows], name

    if slug == "ema-cross-12-33-heikin-ashi-signal":
        rows = read_csv(VARIANTS / "heikin-ashi-signal/execute/all_results.csv")
        return [dict(r, _return=r["full_ha_real_return_pct"],
                     _trades=r["full_ha_real_closed_trades"],
                     _wins=r["full_ha_real_winning_trades"],
                     _pf=r["full_ha_real_profit_factor"],
                     _dd=r["full_ha_real_max_drawdown_pct"],
                     _source="MOEX ISS · HA signals / real OHLC fills") for r in rows], \
            "EMA на Heikin Ashi, исполнение по обычным ценам"

    if slug in ("ema-cross-12-33-range-expansion", "ema-cross-12-33-volume-filter"):
        variant = "range_expansion" if slug.endswith("range-expansion") else "volume"
        rows = [r for r in read_csv(VARIANTS / "pattern-lab/execute/all_results.csv")
                if r["variant"] == variant]
        return [dict(r, _return=r["full_return_pct"],
                     _trades=r["full_closed_trades"], _wins=r["full_winning_trades"],
                     _pf=r["full_profit_factor"], _dd=r["full_max_drawdown_pct"],
                     _source=f"MOEX ISS · pattern-lab:{variant}") for r in rows], variant

    hybrid = {
        "ema-hybrid-6-12-long-12-33-short": LEGACY / "6-12-long-12-33-short/execute/results.csv",
        "ema-hybrid-6-12-long-12-33-short-trend": LEGACY / "6-12-long-12-33-short/execute/variants/trend-long/execute/results.csv",
    }
    if slug in hybrid:
        rows = read_csv(hybrid[slug])
        if slug.endswith("-trend"):
            cols = ("return_pct", "closed_trades", "winning_trades", "profit_factor", "max_drawdown_pct")
        else:
            cols = ("hybrid_return_pct", "hybrid_trades", "hybrid_wins",
                    "hybrid_profit_factor", "hybrid_max_drawdown_pct")
        return [dict(r, _return=r[cols[0]], _trades=r[cols[1]], _wins=r[cols[2]],
                     _pf=r[cols[3]], _dd=r[cols[4]], _source="MOEX ISS · hybrid")
                for r in rows], "EMA hybrid"

    return [], "Нет сопоставимого массового расчёта для этого Pine-файла"


def build() -> dict[str, int]:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    stocks = {r["SECID"]: r["SECNAME"] for r in universe
              if str(r.get("SECTYPE")) in ("1", "2")}
    if len(stocks) != 258:
        raise ValueError(f"unexpected equity universe size: {len(stocks)}")
    counts = {}
    for folder in sorted(REVIEWS.glob("ema-*")):
        if not folder.is_dir():
            continue
        source_rows, note = spec_for(folder.name)
        matched = {}
        for row in source_rows:
            ticker, tf = row["symbol"], row["timeframe"]
            if ticker not in stocks or tf not in ("1D", "1H", "4H", "1W"):
                continue
            key = (ticker, tf)
            if key in matched:
                raise ValueError(f"duplicate result for {folder.name}: {key}")
            matched[key] = row
        frames = ("1D",) if any(x in folder.name for x in
                 ("weekly", "support", "66-filter", "manual-channel", "33-66-long")) \
                 else ("1H", "4H", "1D", "1W")
        rows = []
        for ticker, company in sorted(stocks.items()):
            for tf in frames:
                src = matched.get((ticker, tf))
                if src:
                    trades = int(src["_trades"])
                    wins = int(src["_wins"])
                    net = float(src["_return"])
                    outcome = ("⚪ нет закрытых сделок" if trades == 0 else
                               "🟢 прибыль" if net > 0 else
                               "🔴 убыток" if net < 0 else "⚪ без изменения")
                    rows.append(dict(zip(FIELDS, (
                        ticker, company, tf, "historical_test", outcome, src["_return"], trades,
                        wins, round(100 * wins / trades, 2) if trades else "",
                        src["_pf"], src["_dd"], src.get("first_bar", ""),
                        src.get("last_bar", ""), src["_source"], note,
                    ))))
                else:
                    rows.append(dict(zip(FIELDS, (
                        ticker, company, tf, "not_tested", "⚪ не проверено", "", "", "", "", "", "",
                        "", "", "", note,
                    ))))
        with (folder / "results.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        counts[folder.name] = sum(r["status"] == "historical_test" for r in rows)
    return counts


if __name__ == "__main__":
    for slug, count in build().items():
        print(f"{slug}: {count} historical rows")
