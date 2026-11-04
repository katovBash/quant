"""Cost stress for fixed EMA paper-trading candidates, no live orders."""

from __future__ import annotations

import json
from pathlib import Path

from src.ema.core.adx_ema import SCAN, load_bars
from src.ema.core.research_ema_combinations import crosses, gates, simulate
from src.ema.core.research_ema_heikin_ashi import heikin_ashi

OUTPUT = Path("experiments/.history/papertrading-notes/STRESS.md")
CASES = (("RTKM", "1D", "range_expansion"), ("AFKS", "4H", "volume"),
         ("ROSN", "1D", "volume"), ("VKCO", "1D", "ha_signal"))


def main() -> None:
    universe = json.loads((SCAN / "daily_weekly_monthly/universe.json").read_text())
    ticks = {row["SECID"]: float(row.get("MINSTEP") or 0) for row in universe}
    lines = ["# Стресс по комиссии и проскальзыванию", "",
             "Поздний период 01.01.2025–30.10.2026. Стандарт: комиссия 0,05% за сторону, 1 тик проскальзывания. Стресс: **0,15% за сторону, 3 тика**. Сигналы не меняются; заявки на следующем обычном открытии. Это простой стресс стоимости исполнения, без платы за заём и дивидендов по short.", "",
             "| Тикер | Интервал | Вариант | Стандарт: доходность / PF / просадка | Стресс: доходность / PF / просадка | Закрытых / прибыльных при стрессе |",
             "| --- | --- | --- | ---: | ---: | ---: |"]
    for symbol, timeframe, kind in CASES:
        bars = load_bars(symbol, timeframe)
        if kind == "ha_signal":
            signals = crosses(heikin_ashi(bars))
            allowed = [True] * len(bars)
            up = down = allowed
        else:
            signals = crosses(bars)
            up, down = gates(bars)[kind]
        for label, use_signals, use_up, use_down in (
            ("Чистая EMA12/33", crosses(bars), [True] * len(bars), [True] * len(bars)),
            (kind, signals, up, down),
        ):
            normal = simulate(bars, use_signals, use_up, use_down, ticks[symbol], "2025-01-01")
            stress = simulate(bars, use_signals, use_up, use_down, ticks[symbol] * 3, "2025-01-01", fee_bps=15)
            lines.append(f"| {symbol} | {timeframe} | `{label}` | {normal['return_pct']:+.2f}% / {normal['profit_factor']} / {normal['max_drawdown_pct']:.2f}% | {stress['return_pct']:+.2f}% / {stress['profit_factor']} / {stress['max_drawdown_pct']:.2f}% | {stress['closed_trades']} / {stress['winning_trades']} |")
    lines += ["", "Если преимущество исчезает при небольшом ухудшении исполнения, вариант не готов к paper trading. В 4H локальная агрегация свечей может отличаться от TradingView; сверка сделок остаётся отдельным шагом."]
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
