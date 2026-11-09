"""Sweep exact default source-pivot pauses on the frozen MOEX candle snapshot."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from source_signals import context_factory, pivots_by_bar, signals_for_variant
from src.research.parameter_grid import variants_from_grid
from src.research.timeframes import load_research_bars, source_path
from src.research.trader_method_run import run


def write_entry_trace(output: Path, smoke: bool) -> None:
    """Small auditable event sample; not a substitute for the full results CSVs."""
    source = ROOT / "data/candles/moex_scan"
    symbols = ("SBER", "GAZP") if smoke else ("SFIN", "WUSH", "SBER")
    fields = ("symbol", "timeframe", "delay_bars", "extreme_date", "extreme_price",
              "signal_date", "side", "first_fill_date", "first_fill_open")
    with (output / "entry_trace.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for symbol in symbols:
            for timeframe in ("1H", "4H", "1D", "1W"):
                if not source_path(source, symbol, timeframe).exists():
                    continue
                bars = load_research_bars(source, symbol, timeframe)
                records = pivots_by_bar(bars)
                for delay in (5, 10, 30):
                    entries, _ = signals_for_variant(f"pivot__d{delay}", bars, records)
                    for index, side in enumerate(entries[:-1]):
                        if side and bars[index]["ts"] >= "2024-01-01":
                            extreme = records[index]["pivot_bar"]
                            writer.writerow({"symbol": symbol, "timeframe": timeframe,
                                             "delay_bars": delay,
                                             "extreme_date": bars[extreme]["ts"],
                                             "extreme_price": records[index]["pivot_price"],
                                             "signal_date": bars[index]["ts"],
                                             "side": "LONG" if side > 0 else "SHORT",
                                             "first_fill_date": bars[index + 1]["ts"],
                                             "first_fill_open": bars[index + 1]["open"]})


def annotate_source_coverage(output: Path) -> None:
    report = output / "REPORT.md"
    marker = "## Исходный ZigZag и момент входа"
    content = report.read_text(encoding="utf-8")
    if marker in content:
        return
    note = ("\n\n" + marker + "\n\n"
            "Использованы исходные `add_pivots` и `draw_zigzag` из присланного "
            "Pine, а также правила `ta/1` для sticky Bollinger Bands; Python "
            "переносит их **настройки по умолчанию**. Указанный на графике "
            "конец плеча предварительный и может передвинуться. Вход происходит "
            "ровно через выбранные 0–30 закрытых свечей после последнего "
            "экстремума: низ → long, верх → short. Новый экстремум сбрасывает "
            "счётчик; сигнал исполняется на открытии следующей свечи. Выход — "
            "только при противоположном таком сигнале.\n\n"
            "[Проверочные события для задержек 5/10/30](entry_trace.csv) "
            "показывают дату экстремума, дату сигнала и первую возможную цену "
            "исполнения. 15M/30M в этом снимке имеют `SOURCE_MISSING`, потому "
            "что минутных свечей нет. Pine ещё не сверен по сделкам с Python "
            "на данных TradingView; результаты не разрешают paper trading.\n")
    report.write_text(content + note, encoding="utf-8")


if __name__ == "__main__":
    smoke = "--smoke" in sys.argv
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]
    run(HERE, smoke=smoke, context_factory=context_factory)
    output = HERE / ("smoke" if smoke else "results")
    write_entry_trace(output, smoke)
    annotate_source_coverage(output)
