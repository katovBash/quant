"""Reproducible MOEX TQBR EMA crossover research; no live orders."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from itertools import combinations
from pathlib import Path

BASE = "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR"
PERIODS = (6, 12, 33, 66, 111, 222, 333, 444, 555, 666)
PAIRS = tuple(combinations(PERIODS, 2))
MODES = ("long", "short", "long_short")
FIELDS = ("symbol", "timeframe", "mode", "fast", "slow", "bars", "first_bar", "last_bar",
          "closed_trades", "winning_trades", "win_rate_pct", "net_return_pct", "buy_hold_return_pct",
          "excess_return_pp", "profit_factor", "max_drawdown_pct", "oos_trades",
          "oos_winning_trades", "oos_win_rate_pct", "oos_return_pct", "oos_buy_hold_pct", "oos_excess_pp",
          "status")


def request_json(url: str) -> dict:
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
        except Exception as exc:
            last = exc
            time.sleep(0.5 * 2**attempt)
    raise RuntimeError(f"MOEX request failed: {url}: {last}")


def universe() -> list[dict]:
    url = BASE + "/securities.json?iss.meta=off&iss.only=securities,marketdata"
    payload = request_json(url)
    sec = payload["securities"]
    market = payload["marketdata"]
    turnover = {r[0]: dict(zip(market["columns"], r)).get("VALTODAY_RUR") or 0
                for r in market["data"]}
    return sorted((dict(zip(sec["columns"], row)) | {"turnover_rub": turnover.get(row[0], 0)}
                   for row in sec["data"] if row[0] and row[6] == "A"),
                  key=lambda x: x["turnover_rub"], reverse=True)


def candles(symbol: str, interval: int, start: str, end: str, cache: Path) -> list[dict]:
    path = cache / f"{symbol}_{interval}_{start}_{end}.json"
    if path.exists():
        return json.loads(path.read_text())
    rows = []
    offset = 0
    while True:
        params = urllib.parse.urlencode({"interval": interval, "from": start, "till": end,
                                         "start": offset, "iss.meta": "off"})
        url = f"{BASE}/securities/{urllib.parse.quote(symbol)}/candles.json?{params}"
        block = request_json(url)["candles"]
        part = [dict(zip(block["columns"], row)) for row in block["data"]]
        rows.extend(part)
        if len(part) < 500:
            break
        offset += len(part)
    clean = []
    for row in rows:
        try:
            bar = {"ts": row["begin"], "open": float(row["open"]),
                   "high": float(row["high"]), "low": float(row["low"]),
                   "close": float(row["close"]), "volume": float(row["volume"])}
            if bar["open"] > 0 and bar["close"] > 0:
                clean.append(bar)
        except (TypeError, ValueError):
            continue
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False))
    return clean


def aggregate(bars: list[dict], timeframe: str) -> list[dict]:
    if timeframe in ("1D", "1H"):
        return bars
    result = []
    last_key = None
    for bar in bars:
        d = date.fromisoformat(bar["ts"][:10])
        if timeframe == "1W":
            key = d.isocalendar()[:2]
        elif timeframe == "1M":
            key = (d.year, d.month)
        else:
            raise ValueError(timeframe)
        if key != last_key:
            result.append(dict(bar))
            last_key = key
        else:
            dst = result[-1]
            dst["high"] = max(dst["high"], bar["high"])
            dst["low"] = min(dst["low"], bar["low"])
            dst["close"] = bar["close"]
            dst["volume"] += bar["volume"]
    return result


def four_hour(bars: list[dict]) -> list[dict]:
    result = []
    day = None
    within = 0
    for bar in bars:
        new_day = bar["ts"][:10] != day
        if new_day:
            day = bar["ts"][:10]
            within = 0
        if new_day or within % 4 == 0:
            result.append(dict(bar))
        else:
            dst = result[-1]
            dst["high"] = max(dst["high"], bar["high"])
            dst["low"] = min(dst["low"], bar["low"])
            dst["close"] = bar["close"]
            dst["volume"] += bar["volume"]
        within += 1
    return result


def ema(values: list[float], period: int) -> list[float]:
    out = []
    alpha = 2 / (period + 1)
    for x in values:
        out.append(x if not out else out[-1] + alpha * (x - out[-1]))
    return out


def backtest(bars: list[dict], fast: int, slow: int, start: str,
             fee_bps: float, slip_bps: float, tick: float = 0.0,
             mode: str = "long") -> dict:
    """Integer shares at signal close; execute at next open plus one tick."""
    if mode not in MODES:
        raise ValueError(mode)
    if len(bars) < slow + 3:
        return {"trades": 0, "wins": 0, "net": 0.0, "hold": 0.0,
                "pf": 0.0, "dd": 0.0}
    ef = ema([b["close"] for b in bars], fast)
    es = ema([b["close"] for b in bars], slow)
    fee = fee_bps / 10000
    slip = slip_bps / 10000
    capital = 1_000_000.0
    cash = capital
    position = 0
    entry_cash_flow = 0.0
    returns = []
    peak = capital
    drawdown = 0.0
    first_open = None
    last_close = None
    for i in range(slow, len(bars)):
        bar = bars[i]
        if bar["ts"][:10] < start:
            continue
        if first_open is None:
            first_open = bar["open"]
        last_close = bar["close"]
        up = ef[i - 2] <= es[i - 2] and ef[i - 1] > es[i - 1]
        down = ef[i - 2] >= es[i - 2] and ef[i - 1] < es[i - 1]
        signal_equity = cash + position * bars[i - 1]["close"]
        signal_qty = math.floor(signal_equity * 0.25 / bars[i - 1]["close"])
        if position > 0 and down:
            proceeds = position * max(bar["open"] * (1 - slip) - tick, 0) * (1 - fee)
            returns.append(proceeds - entry_cash_flow)
            cash += proceeds
            position = 0
        elif position < 0 and up:
            cover = -position * (bar["open"] * (1 + slip) + tick) * (1 + fee)
            returns.append(entry_cash_flow - cover)
            cash -= cover
            position = 0
        if position == 0 and ((up and mode in ("long", "long_short")) or
                              (down and mode in ("short", "long_short"))):
            qty = signal_qty
            if qty > 0:
                if up:
                    entry_cash_flow = qty * (bar["open"] * (1 + slip) + tick) * (1 + fee)
                    if entry_cash_flow <= cash:
                        cash -= entry_cash_flow
                        position = qty
                else:
                    entry_cash_flow = qty * max(bar["open"] * (1 - slip) - tick, 0) * (1 - fee)
                    cash += entry_cash_flow
                    position = -qty
        equity = cash + position * bar["close"]
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    final = cash + position * (last_close or bars[-1]["close"])
    wins = sum(x > 0 for x in returns)
    gross_profit = sum(x for x in returns if x > 0)
    gross_loss = -sum(x for x in returns if x < 0)
    # Buy-and-hold holds the same 25% capital weight, with entry/exit costs.
    if first_open is None:
        hold = 0.0
    else:
        # Baseline uses the same integer-share sizing at 1m RUB capital.
        hold_qty = math.floor(capital * 0.25 / first_open)
        hold_cost = hold_qty * (first_open * (1 + slip) + tick) * (1 + fee)
        hold_value = hold_qty * max(last_close * (1 - slip) - tick, 0) * (1 - fee)
        hold = (hold_value - hold_cost) / capital
    return {"trades": len(returns), "wins": wins, "net": (final / capital - 1) * 100,
            "hold": hold * 100, "pf": gross_profit / gross_loss if gross_loss else
            (math.inf if gross_profit else 0.0), "dd": drawdown * 100}


def scan_one(symbol: str, timeframe: str, bars: list[dict], pairs: tuple,
             train_start: str, oos_start: str, fee: float, slip: float,
             tick: float = 0.0) -> list[dict]:
    rows = []
    for mode in MODES:
        for fast, slow in pairs:
            whole = backtest(bars, fast, slow, train_start, fee, slip, tick, mode)
            oos = backtest(bars, fast, slow, oos_start, fee, slip, tick, mode)
            n = whole["trades"]
            m = oos["trades"]
            rows.append({"symbol": symbol, "timeframe": timeframe, "mode": mode,
                         "fast": fast, "slow": slow, "bars": len(bars),
                         "first_bar": bars[0]["ts"] if bars else "",
                         "last_bar": bars[-1]["ts"] if bars else "",
                         "closed_trades": n,
                         "winning_trades": whole["wins"],
                         "win_rate_pct": round(100 * whole["wins"] / n, 2) if n else "",
                         "net_return_pct": round(whole["net"], 2),
                         "buy_hold_return_pct": round(whole["hold"], 2),
                         "excess_return_pp": round(whole["net"] - whole["hold"], 2),
                         "profit_factor": round(whole["pf"], 3) if math.isfinite(whole["pf"]) else "inf",
                         "max_drawdown_pct": round(whole["dd"], 2),
                         "oos_trades": m,
                         "oos_winning_trades": oos["wins"],
                         "oos_win_rate_pct": round(100 * oos["wins"] / m, 2) if m else "",
                         "oos_return_pct": round(oos["net"], 2),
                         "oos_buy_hold_pct": round(oos["hold"], 2),
                         "oos_excess_pp": round(oos["net"] - oos["hold"], 2),
                         "status": "insufficient_history" if len(bars) < slow + 3 else
                         "candidate" if n >= 10 and m >= 3 and whole["net"] > 0
                         and oos["net"] > 0 and whole["pf"] > 1 and whole["dd"] >= -30
                         else "insufficient_trades_or_failed"})
    return rows


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-date", default="2018-01-01")
    p.add_argument("--to-date", default=str(date.today()))
    p.add_argument("--oos-date", default="2025-01-01")
    p.add_argument("--timeframes", nargs="+", choices=("1H", "4H", "1D", "1W", "1M"),
                   default=("1D", "1W", "1M"))
    p.add_argument("--limit", type=int, default=0, help="top turnover symbols; 0 = all TQBR")
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--fee-bps", type=float, default=5)
    p.add_argument("--slip-bps", type=float, default=0,
                   help="extra slippage beyond the one-tick Pine setting")
    p.add_argument("--cache", type=Path, default=Path("data/candles/moex_scan"))
    p.add_argument("--out", type=Path, default=Path("experiments/.history/legacy-ema/12-33-cross/execute/research/daily_weekly_monthly"))
    args = p.parse_args()
    all_securities = universe()
    securities = all_securities
    if args.limit:
        securities = securities[:args.limit]
        for symbol in ("VTBR", "LKOH", "GAZP"):
            if not any(x["SECID"] == symbol for x in securities):
                securities.extend(x for x in all_securities if x["SECID"] == symbol)
    symbols = [x["SECID"] for x in securities]
    ticks = {x["SECID"]: float(x.get("MINSTEP") or 0) for x in securities}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "universe.json").write_text(json.dumps(securities, ensure_ascii=False, indent=2))
    jobs = [(s, i) for s in symbols for i in ({"1D": 24, "1W": 24, "1M": 24,
                                               "1H": 60, "4H": 60}[tf] for tf in args.timeframes)]
    jobs = sorted(set(jobs))
    data = {}
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(candles, s, i, args.from_date, args.to_date, args.cache): (s, i)
                   for s, i in jobs}
        for count, future in enumerate(as_completed(futures), 1):
            s, i = futures[future]
            try:
                data[s, i] = future.result()
            except Exception as exc:
                errors.append({"symbol": s, "interval": i, "error": str(exc)})
            if count % 25 == 0 or count == len(jobs):
                print(f"Downloaded {count}/{len(jobs)} series; errors={len(errors)}", flush=True)
    rows = []
    for symbol in symbols:
        for tf in args.timeframes:
            raw = data.get((symbol, 24 if tf in ("1D", "1W", "1M") else 60))
            if raw is None:
                continue
            bars = four_hour(raw) if tf == "4H" else aggregate(raw, tf)
            rows.extend(scan_one(symbol, tf, bars, PAIRS, args.from_date,
                                 args.oos_date, args.fee_bps, args.slip_bps,
                                 ticks[symbol]))
    write_csv(args.out / "all_results.csv", rows)
    selected = [r for r in rows if r["mode"] == "long" and r["fast"] == 12 and r["slow"] == 33
                and r["status"] == "candidate"]
    selected.sort(key=lambda r: (r["oos_return_pct"], r["net_return_pct"]), reverse=True)
    write_csv(args.out / "ema_12_33_candidates.csv", selected)
    (args.out / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2))
    print(f"symbols={len(symbols)} results={len(rows)} EMA12/33 candidates={len(selected)} errors={len(errors)}")
    for row in selected[:15]:
        print(row["symbol"], row["timeframe"], row["closed_trades"], row["win_rate_pct"],
              row["net_return_pct"], row["oos_return_pct"])


if __name__ == "__main__":
    main()
