"""Compare daily EMA strategies for GAZP and VTBR; optional completed-week filter."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path


SYMBOLS = ("GAZP", "VTBR")
EMA_PERIODS = (12, 33, 66)
MODES = ("cross12_33_pure", "cross12_33", "cross33_66", "support")


@dataclass(frozen=True)
class Bar:
    day: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_csv(path: Path) -> list[Bar]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        bars = [Bar(row["date"], *(float(row[k]) for k in ("open", "high", "low", "close", "volume"))) for row in reader]
    if len(bars) < 67:
        raise ValueError(f"{path}: need at least 67 daily bars for EMA66 warmup and a next bar")
    if len({b.day for b in bars}) != len(bars) or bars != sorted(bars, key=lambda b: b.day):
        raise ValueError(f"{path}: dates must be unique and ascending")
    for b in bars:
        if not (b.open > 0 and b.low > 0 and b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high and b.volume >= 0):
            raise ValueError(f"{path}: invalid OHLCV on {b.day}")
    return bars


def fetch_moex(symbol: str, start: str, end: str, path: Path) -> int:
    if symbol not in SYMBOLS:
        raise ValueError("only GAZP and VTBR are supported")
    base = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{symbol}/candles.json"
    rows: dict[str, Bar] = {}
    offset = 0
    while True:
        url = base + "?" + urllib.parse.urlencode({"interval": 24, "from": start, "till": end, "start": offset, "iss.meta": "off"})
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = json.load(response)["candles"]
        records = [dict(zip(payload["columns"], row)) for row in payload["data"]]
        for row in records:
            bar = Bar(str(row["begin"])[:10], *(float(row[k]) for k in ("open", "high", "low", "close", "volume")))
            rows[bar.day] = bar
        if not records:
            break
        offset += len(records)
    if not rows:
        raise ValueError(f"MOEX returned no TQBR daily candles for {symbol}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("date", "open", "high", "low", "close", "volume"))
        for b in sorted(rows.values(), key=lambda x: x.day):
            writer.writerow((b.day, b.open, b.high, b.low, b.close, b.volume))
    return len(rows)


def indicators(bars: list[Bar], mode: str = "cross12_33_pure", support_line: int = 33,
               use_weekly: bool = False) -> list[dict]:
    if mode not in MODES or support_line not in (33, 66):
        raise ValueError("invalid entry mode or support line")
    result = []
    emas: dict[int, float] = {}
    week_emas: dict[int, float] = {}
    week_count = 0
    week_key = None
    last_week_close = None
    confirmed_week_close = None
    atr = None
    for i, b in enumerate(bars):
        current_week = date.fromisoformat(b.day).isocalendar()[:2]
        if week_key is not None and current_week != week_key:
            week_count += 1
            for period in (33, 66):
                if period not in week_emas:
                    week_emas[period] = last_week_close
                else:
                    week_emas[period] += 2 / (period + 1) * (last_week_close - week_emas[period])
            confirmed_week_close = last_week_close
        week_key = current_week
        last_week_close = b.close
        for period in EMA_PERIODS:
            if period not in emas:
                emas[period] = b.close
            else:
                emas[period] += (2 / (period + 1)) * (b.close - emas[period])
        tr = b.high - b.low if i == 0 else max(b.high - b.low, abs(b.high - bars[i - 1].close), abs(b.low - bars[i - 1].close))
        atr = tr if atr is None else (13 * atr + tr) / 14
        week_up = week_count >= 66 and week_emas[33] > week_emas[66] and confirmed_week_close > week_emas[33]
        weekly_ok = not use_weekly or week_up
        ready = (i >= 32 if mode == "cross12_33_pure" else i >= 65 and atr > 0 and (not use_weekly or week_count >= 66))
        prior = result[-1] if result else None
        pure_cross = prior is not None and prior["ema"][12] <= prior["ema"][33] and emas[12] > emas[33]
        pure_exit = prior is not None and prior["ema"][12] >= prior["ema"][33] and emas[12] < emas[33]
        fast_cross = prior is not None and prior["ema"][12] <= prior["ema"][33] and emas[12] > emas[33] and emas[33] > emas[66] and b.close > emas[33]
        slow_cross = prior is not None and prior["ema"][33] <= prior["ema"][66] and emas[33] > emas[66] and emas[12] > emas[33] and b.close > emas[33]
        base = emas[support_line]
        support = b.low <= base + 0.25 * atr and b.close > base and b.close > b.open and b.close > emas[12] and emas[33] > emas[66] and (support_line == 66 or emas[12] > emas[33])
        selected = {"cross12_33_pure": pure_cross, "cross12_33": fast_cross,
                    "cross33_66": slow_cross, "support": support}[mode]
        trend_failed = emas[33] < emas[66] if mode == "cross33_66" else emas[12] < emas[33]
        result.append({"ema": dict(emas), "weekly_ema": dict(week_emas), "weekly_close": confirmed_week_close,
                       "close": b.close, "atr": atr, "ready": ready,
                       "enter": bool(ready and (mode == "cross12_33_pure" or weekly_ok) and selected),
                       "exit": bool(ready and pure_exit if mode == "cross12_33_pure" else i >= 65 and (trend_failed or b.close < emas[66] or (use_weekly and not week_up)))})
    return result


def run(data: dict[str, list[Bar]], capital: float = 1_000_000, fee_bps: float = 5,
        slippage_bps: float = 10, risk_pct: float = 0.005,
        max_weight: float = 0.25, lot_sizes: dict[str, int] | None = None,
        start: str | None = None, mode: str = "cross12_33_pure", support_line: int = 33,
        use_weekly: bool = False, fixed_weight: bool = False) -> dict:
    if capital <= 0 or min(fee_bps, slippage_bps, risk_pct, max_weight) < 0 or max_weight > 1 or risk_pct > 1:
        raise ValueError("invalid risk or cost parameters")
    if mode == "cross12_33_pure" and use_weekly:
        raise ValueError("pure EMA12/33 mode has no weekly filter")
    symbols = tuple(s for s in SYMBOLS if s in data)
    if not symbols or set(data) - set(SYMBOLS):
        raise ValueError("data must contain GAZP and/or VTBR")
    lots = lot_sizes or {s: 1 for s in symbols}
    if any(lots.get(s, 0) < 1 for s in symbols):
        raise ValueError("lot sizes must be positive")
    by_day = {s: {b.day: (b, ind) for b, ind in zip(data[s], indicators(data[s], mode, support_line, use_weekly))} for s in symbols}
    days = sorted(set.intersection(*(set(by_day[s]) for s in symbols)))
    if not days:
        raise ValueError("no common trading dates")
    cash = capital
    positions: dict[str, dict] = {}
    trades: list[dict] = []
    curve: list[dict] = []
    prev = None
    fee = fee_bps / 10_000
    slip = slippage_bps / 10_000
    for day in days:
        current = {s: by_day[s][day] for s in symbols}
        warmed_up = all(current[s][1]["ready"] for s in symbols)
        if prev is not None and warmed_up and (start is None or day >= start):
            # Yesterday's close sets orders for today's open. Sell before buying.
            for s in symbols:
                if s not in positions:
                    continue
                bar, _ = current[s]
                p = positions[s]
                if p["stop"] is not None and bar.open <= p["stop"]:
                    reason = "gap_stop"
                elif prev[s][1]["exit"]:
                    reason = "trend"
                elif p["stop"] is not None and bar.low <= p["stop"]:
                    reason = "stop"
                else:
                    reason = None
                if reason:
                    raw = min(bar.open, p["stop"]) if reason in ("gap_stop", "stop") else bar.open
                    price = raw * (1 - slip)
                    proceeds = p["qty"] * price * (1 - fee)
                    cash += proceeds
                    trades.append({"date": day, "symbol": s, "side": "SELL", "qty": p["qty"], "price": round(price, 4), "fee": round(p["qty"] * price * fee, 2), "reason": reason})
                    del positions[s]
            equity_open = cash + sum(positions[s]["qty"] * current[s][0].open for s in positions)
            for s in symbols:
                if s in positions or not prev[s][1]["enter"] or (mode != "cross12_33_pure" and not prev[s][1]["atr"]):
                    continue
                bar, _ = current[s]
                price = bar.open * (1 + slip)
                atr = prev[s][1]["atr"]
                stop = None if mode == "cross12_33_pure" else bar.open - 3 * atr
                if stop is not None and stop <= 0:
                    continue
                cap_shares = min(max_weight * equity_open / (price * (1 + fee)),
                                 cash / (price * (1 + fee)))
                max_shares = cap_shares if stop is None or fixed_weight else min(
                    risk_pct * equity_open / max(price - stop, price * 0.01), cap_shares)
                qty = int(max_shares // lots[s]) * lots[s]
                if qty <= 0:
                    continue
                cash -= qty * price * (1 + fee)
                positions[s] = {"qty": qty, "stop": stop}
                trades.append({"date": day, "symbol": s, "side": "BUY", "qty": qty, "price": round(price, 4), "fee": round(qty * price * fee, 2), "reason": mode if mode != "support" else f"ema{support_line}_support"})
            # An intraday stop on a fresh position also applies on entry day.
            for s in SYMBOLS:
                if s not in positions or positions[s]["stop"] is None or current[s][0].low > positions[s]["stop"]:
                    continue
                p = positions.pop(s)
                price = p["stop"] * (1 - slip)
                cash += p["qty"] * price * (1 - fee)
                trades.append({"date": day, "symbol": s, "side": "SELL", "qty": p["qty"], "price": round(price, 4), "fee": round(p["qty"] * price * fee, 2), "reason": "entry_day_stop"})
            for s in positions:
                bar, ind = current[s]
                if positions[s]["stop"] is not None:
                    positions[s]["stop"] = max(positions[s]["stop"], bar.close - 3 * ind["atr"])
            equity = cash + sum(positions[s]["qty"] * current[s][0].close for s in positions)
            curve.append({"date": day, "equity": round(equity, 2), "cash": round(cash, 2)})
        prev = current
    if not curve:
        raise ValueError("no backtest days after warmup/start")
    peak = capital
    max_dd = 0.0
    for point in curve:
        peak = max(peak, point["equity"])
        max_dd = min(max_dd, point["equity"] / peak - 1)
    final = curve[-1]["equity"]
    years = max((date.fromisoformat(curve[-1]["date"]) - date.fromisoformat(curve[0]["date"])).days / 365.25, 1 / 365.25)
    latest = {s: {"date": days[-1], "close": current[s][0].close,
                  "signal": "EXIT" if s in positions and current[s][1]["exit"] else "ENTRY" if s not in positions and current[s][1]["enter"] else "HOLD" if s in positions else "WAIT",
                  "shares": positions.get(s, {}).get("qty", 0), "stop": round(positions[s]["stop"], 4) if s in positions and positions[s]["stop"] is not None else None,
                  "ema": {str(k): round(v, 4) for k, v in current[s][1]["ema"].items()},
                  "weekly_ema": {str(k): round(v, 4) for k, v in current[s][1]["weekly_ema"].items()}} for s in symbols}
    return {"period": [curve[0]["date"], curve[-1]["date"]], "initial_rub": capital,
            "final_rub": final, "return_pct": round((final / capital - 1) * 100, 2),
            "cagr_pct": round(((final / capital) ** (1 / years) - 1) * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2), "trades": trades, "equity": curve,
            "next_session": latest, "assumptions": {"fee_bps_per_side": fee_bps,
            "slippage_bps_per_side": slippage_bps, "risk_per_trade_pct": None if mode == "cross12_33_pure" else risk_pct * 100,
            "max_weight_per_symbol_pct": max_weight * 100, "mode": mode,
            "support_line": support_line if mode == "support" else None,
            "use_weekly": use_weekly, "fixed_weight": fixed_weight or mode == "cross12_33_pure",
            "dividends_included": False,
            "vtbr_pre_2024_07_15_split_adjusted_required": True}}


def buy_hold_baseline(bars: list[Bar], start: str, capital: float, fee_bps: float,
                      slippage_bps: float, lot_size: int, weight: float = 0.25) -> dict:
    selected = [b for b in bars if b.day >= start]
    if not selected or lot_size < 1 or capital <= 0:
        raise ValueError("invalid buy-and-hold inputs")
    fee = fee_bps / 10_000
    price = selected[0].open * (1 + slippage_bps / 10_000)
    qty = int(min(weight * capital, capital) / (price * (1 + fee)) // lot_size) * lot_size
    cash = capital - qty * price * (1 + fee)
    peak = capital
    max_dd = 0.0
    for bar in selected:
        equity = cash + qty * bar.close
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    final = cash + qty * selected[-1].close
    years = max((date.fromisoformat(selected[-1].day) - date.fromisoformat(selected[0].day)).days / 365.25, 1 / 365.25)
    return {"entries": int(qty > 0), "exits": 0,
            "return_pct": round((final / capital - 1) * 100, 2),
            "cagr_pct": round(((final / capital) ** (1 / years) - 1) * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2), "final_rub": round(final, 2)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="download daily TQBR candles from MOEX ISS")
    fetch.add_argument("--from-date", required=True)
    fetch.add_argument("--to-date", required=True)
    fetch.add_argument("--dir", type=Path, default=Path("data"))
    fetch.add_argument("--symbol", choices=("BOTH",) + SYMBOLS, default="BOTH")
    back = sub.add_parser("backtest", help="backtest and generate next-session paper signals")
    back.add_argument("--dir", type=Path, default=Path("data"))
    back.add_argument("--from-date")
    back.add_argument("--capital", type=float, default=1_000_000)
    back.add_argument("--fee-bps", type=float, default=5)
    back.add_argument("--slippage-bps", type=float, default=10)
    back.add_argument("--lot-gazp", type=int, default=1)
    back.add_argument("--lot-vtbr", type=int, default=1)
    back.add_argument("--mode", choices=MODES, default="cross12_33_pure")
    back.add_argument("--symbol", choices=("BOTH",) + SYMBOLS, default="BOTH")
    back.add_argument("--support-line", type=int, choices=(33, 66), default=33)
    back.add_argument("--weekly", action="store_true", help="require completed 1W EMA33 > EMA66")
    back.add_argument("--out", type=Path, default=Path("result.json"))
    compare = sub.add_parser("compare", help="compare EMA variants on the same symbol with fixed 25% position sizing")
    compare.add_argument("--dir", type=Path, default=Path("data"))
    compare.add_argument("--symbol", choices=SYMBOLS, default="VTBR")
    compare.add_argument("--from-date")
    compare.add_argument("--capital", type=float, default=1_000_000)
    compare.add_argument("--fee-bps", type=float, default=5)
    compare.add_argument("--slippage-bps", type=float, default=10)
    compare.add_argument("--lot-gazp", type=int, default=10)
    compare.add_argument("--lot-vtbr", type=int, default=1)
    compare.add_argument("--out", type=Path, default=Path("comparison.csv"))
    args = parser.parse_args()
    if args.command == "fetch":
        for symbol in SYMBOLS if args.symbol == "BOTH" else (args.symbol,):
            n = fetch_moex(symbol, args.from_date, args.to_date, args.dir / f"{symbol}.csv")
            print(f"{symbol}: {n} bars")
    elif args.command == "backtest":
        result = run({s: load_csv(args.dir / f"{s}.csv") for s in SYMBOLS if args.symbol in ("BOTH", s)},
                     capital=args.capital, fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
                     lot_sizes={"GAZP": args.lot_gazp, "VTBR": args.lot_vtbr}, start=args.from_date,
                     mode=args.mode, support_line=args.support_line, use_weekly=args.weekly)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k not in ("trades", "equity")}, ensure_ascii=False, indent=2))
        print(f"Full results: {args.out}")
    else:
        data = {args.symbol: load_csv(args.dir / f"{args.symbol}.csv")}
        common_start = max(args.from_date or data[args.symbol][66].day, data[args.symbol][66].day)
        rows = []
        for mode, line in (("cross12_33_pure", 33), ("cross12_33", 33),
                           ("cross33_66", 33), ("support", 33), ("support", 66)):
            result = run(data, capital=args.capital, fee_bps=args.fee_bps,
                         slippage_bps=args.slippage_bps, start=common_start,
                         lot_sizes={"GAZP": args.lot_gazp, "VTBR": args.lot_vtbr},
                         mode=mode, support_line=line, fixed_weight=True)
            rows.append({"symbol": args.symbol, "strategy": mode if mode != "support" else f"support{line}",
                         "from": result["period"][0], "to": result["period"][1],
                         "entries": sum(t["side"] == "BUY" for t in result["trades"]),
                         "exits": sum(t["side"] == "SELL" for t in result["trades"]),
                         "return_pct": result["return_pct"], "cagr_pct": result["cagr_pct"],
                         "max_drawdown_pct": result["max_drawdown_pct"], "final_rub": result["final_rub"]})
        baseline = buy_hold_baseline(data[args.symbol], common_start, args.capital,
                                     args.fee_bps, args.slippage_bps,
                                     args.lot_gazp if args.symbol == "GAZP" else args.lot_vtbr)
        rows.append({"symbol": args.symbol, "strategy": "buy_hold_25pct",
                     "from": rows[0]["from"], "to": rows[0]["to"], **baseline})
        with args.out.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        for row in rows:
            print(row)
        print(f"Comparison: {args.out}")


if __name__ == "__main__":
    main()
