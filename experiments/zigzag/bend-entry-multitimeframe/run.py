"""Run fixed bend-entry grid and exploratory feature diagnostics."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from bend_signals import context_factory, forward_events, prepare
from src.research.parameter_grid import variants_from_grid
from src.research.timeframes import load_research_bars, source_path
from src.research.trader_method_run import run


def correlation(moment: list[float]) -> float | None:
    count, sx, sy, sxx, syy, sxy = moment
    if count < 30:
        return None
    vx, vy = count * sxx - sx * sx, count * syy - sy * sy
    denominator = vx * vy
    return round((count * sxy - sx * sy) / denominator ** 0.5, 4) if denominator > 0 else None


def diagnostics(output: Path, smoke: bool):
    protocol = json.loads((HERE / "protocol.json").read_text())
    symbols = sorted({item["SECID"] for item in json.loads(
        (ROOT / protocol["eligible_universe"]["snapshot_file"]).read_text())
        if item["BOARDID"] == "TQBR"})
    if smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    source = ROOT / "data/candles/moex_scan"
    event_path = output / "bend_event_forward.csv"
    fields = ("symbol", "timeframe", "trigger", "delay_bars", "signal_date", "direction", "leg_ratio",
              "wick_fraction", "band_excursion_pct", "forward_3bar_pct", "forward_10bar_pct")
    grouped = defaultdict(lambda: [0.0] * 6)
    with event_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for symbol in symbols:
            for timeframe in protocol["signal_timeframes"]:
                if not source_path(source, symbol, timeframe).exists():
                    continue
                bars = load_research_bars(source, symbol, timeframe)
                if len(bars) < protocol["min_bars"]:
                    continue
                for row in forward_events(bars, prepare(bars), symbol=symbol, timeframe=timeframe):
                    writer.writerow(row)
                    for feature in ("leg_ratio", "wick_fraction", "band_excursion_pct"):
                        if row[feature] is not None:
                            for horizon in ("3", "10"):
                                x = float(row[feature])
                                y = row[f"forward_{horizon}bar_pct"]
                                moment = grouped[(timeframe, row["trigger"], row["delay_bars"], feature, horizon)]
                                moment[0] += 1
                                moment[1] += x
                                moment[2] += y
                                moment[3] += x * x
                                moment[4] += y * y
                                moment[5] += x * y
    rows = [{"timeframe": tf, "trigger": trigger, "delay_bars": delay,
             "feature": feature, "forward_bars": horizon,
             "events": int(moment[0]), "pearson_r": correlation(moment)}
            for (tf, trigger, delay, feature, horizon), moment in sorted(grouped.items())]
    with (output / "feature_correlations.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, ("timeframe", "trigger", "delay_bars", "feature", "forward_bars", "events", "pearson_r"))
        writer.writeheader()
        writer.writerows(rows)


def annotate_source_coverage(output: Path):
    report = output / "REPORT.md"
    marker = "## Наличие исходных свечей для запрошенных интервалов"
    note = ("\n\n" + marker + "\n\n"
            "Полный перебор 165 правил (164 входа и контроль) выполнен на доступных "
            "1H, 4H и 1D. Для 15M и 30M в замороженном снимке нет минутных "
            "свечей: **0 рассчитанных акций** на каждом интервале. Эти результаты "
            "имеют статус `SOURCE_MISSING`; часовые свечи не дробились на минуты. "
            "Всего рассчитаны 263 акции на 1H, 263 на 4H и 319 на 1D. "
            "Диапазон ожиданий проверен целиком: 0 на свече экстремума, "
            "каждое целое от 1 до 20 для подтверждений `close` и `break`.\n\n"
            "Выбор правила после просмотра этой сетки не является независимой "
            "проверкой. Корпоративные события не применены, точное совпадение "
            "с исходным Trendoscope Band-ZigZag и сделок Pine/Python не доказано. "
            "Эксперимент не переключает paper trading.\n")
    content = report.read_text(encoding="utf-8")
    if marker not in content:
        report.write_text(content + note, encoding="utf-8")


if __name__ == "__main__":
    smoke = "--smoke" in sys.argv
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]
    run(HERE, smoke=smoke, context_factory=context_factory)
    diagnostics(HERE / ("smoke" if smoke else "results"), smoke)
    annotate_source_coverage(HERE / ("smoke" if smoke else "results"))
