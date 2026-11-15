"""Build fixed Python/Pine candidates, measure adapter parity and resume pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from preregister_classic_indicator_grid import SPECS

ROOT = Path(__file__).resolve().parents[1]


def pine(family: str, variant: str, timeframe: str) -> str:
    _, length_text, mode = variant.split("_")
    length = int(length_text)
    title = f"{family.upper()} · {variant} · {timeframe} · review"
    head = f'''//@version=6
// Fixed research hypothesis. TradingView/Python fill parity is not verified.
// Closed bars decide; market orders fill at the next available bar open.
strategy("{title}", overlay=true, pyramiding=0, initial_capital=1000000,
     currency=currency.RUB, default_qty_type=strategy.percent_of_equity,
     default_qty_value=25, commission_type=strategy.commission.percent,
     commission_value=0.15, process_orders_on_close=false)
length = {length}
chartOk = timeframe.period == "{ {'1H': '60', '4H': '240', '1D': 'D', '1W': 'W'}[timeframe] }"
bool longSignal = false
bool shortSignal = false
'''
    bodies = {
        "aroon": f'''upAgo = ta.highestbars(high, length + 1)
downAgo = ta.lowestbars(low, length + 1)
up = 100.0 * (length - upAgo) / length
down = 100.0 * (length - downAgo) / length
side = up > down ? 1 : down > up ? -1 : 0
var int previousSide = 0
if bar_index >= length and barstate.isconfirmed
    strong = side == 1 ? up >= 70 and down <= 30 : down >= 70 and up <= 30
    longSignal := side == 1 and side != previousSide and ({str(mode == 'cross').lower()} or strong)
    shortSignal := side == -1 and side != previousSide and ({str(mode == 'cross').lower()} or strong)
    previousSide := side
''',
        "williams": f'''highestPrice = ta.highest(high, length)
lowestPrice = ta.lowest(low, length)
value = highestPrice == lowestPrice ? -50.0 : -100.0 * (highestPrice - close) / (highestPrice - lowestPrice)
if bar_index >= length and barstate.isconfirmed
    longSignal := ta.crossover(value, {(-80 if mode == 'rebound' else -20)})
    shortSignal := ta.crossunder(value, {(-20 if mode == 'rebound' else -80)})
''',
        "stoch": f'''rawK = ta.stoch(close, high, low, length)
k = ta.sma(rawK, 3)
d = ta.sma(k, 3)
if bar_index >= length + 4 and barstate.isconfirmed
    longSignal := ta.crossover(k, d) and ({str(mode == 'cross').lower()} or k < 30)
    shortSignal := ta.crossunder(k, d) and ({str(mode == 'cross').lower()} or k > 70)
''',
        "keltner": f'''middle = ta.ema(close, length)
atrValue = ta.atr(length)
upper = middle + {(1.5 if mode == 'narrow' else 2.0)} * atrValue
lower = middle - {(1.5 if mode == 'narrow' else 2.0)} * atrValue
if bar_index >= length and barstate.isconfirmed
    longSignal := close > upper and close[1] <= upper[1]
    shortSignal := close < lower and close[1] >= lower[1]
plot(upper, "Upper", color=color.new(color.red, 65))
plot(lower, "Lower", color=color.new(color.aqua, 65))
''',
        "ichimoku": f'''conversionLength = {(9 if length == 26 else 7)}
spanLength = {(52 if length == 26 else 44)}
conversion = (ta.highest(high, conversionLength) + ta.lowest(low, conversionLength)) / 2
base = (ta.highest(high, length) + ta.lowest(low, length)) / 2
spanA = (conversion + base) / 2
spanB = (ta.highest(high, spanLength) + ta.lowest(low, spanLength)) / 2
visibleUpper = math.max(spanA[length], spanB[length])
visibleLower = math.min(spanA[length], spanB[length])
if bar_index >= spanLength + length and barstate.isconfirmed
    longSignal := close > visibleUpper and close[1] <= visibleUpper[1] and ({str(mode == 'break').lower()} or spanA[length] > spanB[length])
    shortSignal := close < visibleLower and close[1] >= visibleLower[1] and ({str(mode == 'break').lower()} or spanA[length] < spanB[length])
plot(visibleUpper, "Visible cloud upper", color=color.new(color.green, 65))
plot(visibleLower, "Visible cloud lower", color=color.new(color.red, 65))
''',
        "mfi": f'''typical = hlc3
positiveFlow = typical > typical[1] ? typical * volume : 0.0
negativeFlow = typical < typical[1] ? typical * volume : 0.0
positiveSum = ta.sma(positiveFlow, length) * length
negativeSum = ta.sma(negativeFlow, length) * length
value = positiveSum + negativeSum == 0 ? 50.0 : 100.0 * positiveSum / (positiveSum + negativeSum)
if bar_index >= length and barstate.isconfirmed
    longSignal := ta.crossover(value, {(20 if mode == 'rebound' else 80)})
    shortSignal := ta.crossunder(value, {(80 if mode == 'rebound' else 20)})
''',
        "cmf": f'''moneyFlow = high == low ? 0.0 : (2 * close - high - low) / (high - low) * volume
flowSum = ta.sma(moneyFlow, length) * length
volumeSum = ta.sma(volume, length) * length
value = volumeSum == 0 ? 0.0 : flowSum / volumeSum
if bar_index >= length and barstate.isconfirmed
    longSignal := ta.crossover(value, {(0.0 if mode == 'zero' else 0.05)})
    shortSignal := ta.crossunder(value, {(-0.0 if mode == 'zero' else -0.05)})
''',
        "dmi": f'''[plusDI, minusDI, adxValue] = ta.dmi(length, length)
if bar_index >= 2 * length and barstate.isconfirmed and adxValue >= {(20 if mode == 'adx20' else 25)}
    longSignal := plusDI > minusDI and plusDI[1] <= minusDI[1]
    shortSignal := minusDI > plusDI and minusDI[1] <= plusDI[1]
''',
        "cci": f'''value = ta.cci(hlc3, length)
if bar_index >= length and barstate.isconfirmed
    longSignal := ta.crossover(value, {(-100 if mode == 'rebound' else 100)})
    shortSignal := ta.crossunder(value, {(100 if mode == 'rebound' else -100)})
''',
    }
    tail = '''longSignal := longSignal and chartOk
shortSignal := shortSignal and chartOk
if longSignal and strategy.position_size <= 0
    strategy.entry("Long", strategy.long)
else if shortSignal and strategy.position_size >= 0
    strategy.entry("Short", strategy.short)
plotshape(longSignal, title="Long signal", style=shape.triangleup,
     location=location.belowbar, color=color.lime, size=size.tiny)
plotshape(shortSignal, title="Short signal", style=shape.triangledown,
     location=location.abovebar, color=color.red, size=size.tiny)
'''
    return head + bodies[family] + tail


def finalize(family: str) -> None:
    run_id = SPECS[family][0]
    experiment = ROOT / "experiments" / family / run_id
    state = json.loads((experiment / "results/PIPELINE.json").read_text())
    review = json.loads((experiment / "results/paper_review.json").read_text())
    rule = review.get("rule")
    default = rule or {"variant": json.loads((experiment / "protocol.json").read_text())["expected_variants"][1], "timeframe": "1D"}
    (experiment / "review.pine").write_text(pine(family, default["variant"], default["timeframe"]), encoding="utf-8")
    if state["stage"] != "NEEDS_FIXED_STRATEGY":
        print(f"{family}: {state['stage']}, no account registration")
        return
    variant, timeframe = rule["variant"], rule["timeframe"]
    identifier = variant.replace("_", "-") + "-" + timeframe.lower()
    destination = ROOT / "strategies" / identifier
    destination.mkdir(exist_ok=True)
    symbols = [item["symbol"] for item in review["stocks"]]
    strategy = f'''"""Fixed {family} experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = {identifier!r}
TIMEFRAME = {timeframe!r}
VARIANT = {variant!r}
PAPER_SYMBOLS = {symbols!r}
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method({family!r}, VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
'''
    (destination / "strategy.py").write_text(strategy, encoding="utf-8")
    (destination / "strategy.pine").write_text(pine(family, variant, timeframe), encoding="utf-8")
    check = '''"""Measured paper adapter parity on frozen source prefixes."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.timeframes import load_research_bars
from src.research.classic_indicator_grid import signals_for_method
from strategy import STRATEGY_ID, TIMEFRAME, VARIANT, PAPER_SYMBOLS, signal
def check():
    checked = events = mismatches = 0
    by_symbol = {}
    family = VARIANT.split("_", 1)[0]
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        entries, _ = signals_for_method(family, VARIANT, bars)
        event_indices = [i for i, value in enumerate(entries) if value]
        step = max(1, len(event_indices) // 40)
        indices = set(event_indices[::step])
        indices.update(range(max(0, len(bars) - 40), len(bars)))
        stride = max(1, len(bars) // 80)
        indices.update(range(0, len(bars), stride))
        symbol_mismatch = 0
        for index in sorted(indices):
            expected = "long" if entries[index] > 0 else "short" if entries[index] < 0 else None
            symbol_mismatch += signal(bars[:index + 1]) != expected
            checked += 1
            events += bool(entries[index])
        mismatches += symbol_mismatch
        by_symbol[symbol] = {"bars_checked": len(indices), "mismatches": symbol_mismatch}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT, "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "paper adapter on historical prefixes versus frozen experiment entry series",
              "independent_signal_implementation": False,
              "pine_verified_against_python": False,
              "bars_checked": checked, "signal_events_checked": events,
              "mismatches": mismatches, "symbols": by_symbol}
    Path(__file__).with_name("parity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n")
    return result
if __name__ == "__main__":
    result = check()
    print(json.dumps({key: result[key] for key in ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if result["mismatches"] else 0)
'''
    (destination / "check_parity.py").write_text(check, encoding="utf-8")
    result = subprocess.run([sys.executable, str(destination / "check_parity.py")], cwd=ROOT, text=True, capture_output=True)
    print(f"{family}: parity {result.stdout.strip()}")
    if result.returncode:
        raise RuntimeError(result.stderr)
    result = subprocess.run([sys.executable, "-m", "pipeline.run", str(experiment.relative_to(ROOT)),
                             "--existing-results", "--strategy-dir", str(destination.relative_to(ROOT))],
                            cwd=ROOT, text=True, capture_output=True)
    print(f"{family}: {result.stdout[-700:]}")
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)


if __name__ == "__main__":
    for name in sys.argv[1:] or SPECS:
        finalize(name)
