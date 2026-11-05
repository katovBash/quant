"""Recalculate SFIN 1H RSI variants with one verified ex-dividend cash flow.

This is a sensitivity check, not a fully adjusted backtest: other dividends,
short-borrow costs, lot rules and corporate events remain unmodeled.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.ema.core.compare_ema_filters import rsi
from src.ema.core.research_ema_combinations import simulate
from src.research.standalone_grid import crossing, load_bars

EXPERIMENT = Path(__file__).resolve().parent
EX_DATE = "2025-12-25"
DIVIDEND_RUB = 902.0
SOURCE = "https://mkb-broker.ru/lists/depository-news/dividendy_v_denezhnoy_forme_o_korporativnom_deystvii_vyplata_dividendov_v_vide_denezhnykh_sredstv_s_tsennymi_bumagami_emitenta_pao_esefay_inn_6164077483_aktsiya_1_02_56453_p_isin_ru000a0jvw89_20251217141405607/"


def main() -> None:
    bars = load_bars("SFIN", "1H")
    universe = json.loads((ROOT / "data/candles/moex_scan/universe_2026-10-30.json").read_text())
    entry = next(item for item in universe if item["SECID"] == "SFIN")
    tick = float(entry.get("MINSTEP") or 0)
    original = {(row["variant"], row["mode"]): row for row in csv.DictReader(
        (EXPERIMENT / "results/1H/SFIN.csv").open(encoding="utf-8"))}
    always = [True] * len(bars)
    rows = []
    for length in (7, 14, 21):
        values = rsi(bars, length)
        for above, below in ((50, 50), (55, 45), (60, 40)):
            variant = f"rsi_{length}_{above}_{below}"
            signals = crossing(values, above, below)
            baseline = simulate(bars, signals, always, always, tick, "2024-01-01")
            expected = float(original[(variant, "long_short")]["net_return_pct"])
            if baseline["return_pct"] != expected:
                raise ValueError(f"baseline changed for {variant}: {baseline['return_pct']} != {expected}")
            adjusted = simulate(bars, signals, always, always, tick, "2024-01-01",
                                dividends_per_share={EX_DATE: DIVIDEND_RUB})
            adjusted_late = simulate(bars, signals, always, always, tick, "2025-01-01",
                                     dividends_per_share={EX_DATE: DIVIDEND_RUB})
            rows.append({"variant": variant, "raw_return_pct": expected,
                         "one_dividend_return_pct": adjusted["return_pct"],
                         "difference_pp": round(adjusted["return_pct"] - expected, 2),
                         "late_return_pct": adjusted_late["return_pct"],
                         "closed_trades": adjusted["closed_trades"],
                         "profit_factor": adjusted["profit_factor"]})
    csv_path = EXPERIMENT / "SFIN_DIVIDEND_CHECK.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# SFIN 1H · чувствительность RSI к дивиденду", "",
             f"Источник выплаты: [сообщение о корпоративном действии]({SOURCE}). "
             f"Дата фиксации: {EX_DATE}; выплата: {DIVIDEND_RUB:g} ₽ на акцию.", "",
             "В этом прогоне на первой свече даты фиксации длинная позиция получает выплату, "
             "короткая оплачивает её. Исходные строки CSV сверены перед пересчётом. "
             "Это **чувствительность только к одной выплате**, не окончательная доходность: "
             "остальные выплаты, стоимость займа, доступность short, биржевые лоты и "
             "корпоративные события остаются непроверенными.", "",
             "| Настройка | Исходная доходность | С одной выплатой | Изменение | Поздняя часть | Сделки | PF |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['variant']} | {row['raw_return_pct']:+.2f}% | "
                     f"{row['one_dividend_return_pct']:+.2f}% | {row['difference_pp']:+.2f} п.п. | "
                     f"{row['late_return_pct']:+.2f}% | {row['closed_trades']} | "
                     f"{row['profit_factor']:.3f} |")
    lines += ["", "Выбор лучшей строки произведён на уже просмотренной истории. "
              "[Полные исходные варианты](results/1H/SFIN.csv) и "
              "[стратегия для ручной сверки](../../strategies/rsi-21-60-40-long-short-1h/README.md).", ""]
    (EXPERIMENT / "SFIN_DIVIDEND_CHECK.md").write_text("\n".join(lines), encoding="utf-8")
    print(EXPERIMENT / "SFIN_DIVIDEND_CHECK.md")


if __name__ == "__main__":
    main()
