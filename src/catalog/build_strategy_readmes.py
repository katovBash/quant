"""Write the comparable historical report for every researched EMA rule."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / "experiments/.history/rule-reviews"

RULES = {
    "ema-cross-12-33-long": ("EMA12/33 · только long", "Пересечение EMA12 выше EMA33 открывает long; обратное пересечение закрывает позицию. Вход по следующему бару."),
    "ema-cross-12-33-long-short": ("EMA12/33 · long и short", "EMA12 пересекает EMA33 вверх — long; вниз — short. Встречный сигнал разворачивает позицию на следующем баре."),
    "ema-cross-12-33-adx-filter": ("EMA12/33 + ADX14", "Сигнал пересечения EMA12/33 открывает long или short, только если ADX14 не ниже выбранного порога; по умолчанию порог 20. Встречное пересечение закрывает позицию."),
    "ema-cross-12-33-rsi-filter": ("EMA12/33 + RSI14", "Вход long по пересечению вверх при RSI14 > 50; вход short по пересечению вниз при RSI14 < 50. Встречный кросс закрывает позицию."),
    "ema-cross-12-33-channel-zone": ("EMA12/33 + зоны канала", "Пересечение EMA12/33 служит базовым сигналом; автоматические зоны по подтверждённым локальным максимумам и минимумам фильтруют вход."),
    "ema-cross-12-33-regression-channel": ("EMA12/33 + регрессионный канал", "Пересечение EMA12/33 фильтруется длинным каналом линейной регрессии, рассчитанным по предшествующим барам."),
    "ema-cross-12-33-trendline-filter": ("EMA12/33 + трендовые линии", "Пересечение EMA12/33 фильтруется линиями, построенными из подтверждённых ценовых экстремумов."),
    "ema-cross-12-33-heikin-ashi-signal": ("EMA12/33 на Heikin Ashi", "Пересечение EMA12/33 считается по Heikin Ashi; исполнение моделируется по обычным ценам OHLC."),
    "ema-cross-12-33-range-expansion": ("EMA12/33 + расширение диапазона", "Пересечение EMA12/33 используется вместе с недавней свечой с расширенным истинным диапазоном."),
    "ema-cross-12-33-volume-filter": ("EMA12/33 + объём", "Пересечение EMA12/33 используется вместе с недавним всплеском объёма относительно предыдущих свечей."),
    "ema-cross-12-33-66-filter": ("EMA12/33 + EMA66 · long", "Long после пересечения EMA12/33 вверх, если EMA33 выше EMA66; выход по утрате условий либо стопу ATR. Pine ограничен 1D."),
    "ema-cross-12-33-66-weekly-filter": ("EMA12/33 + EMA66 + неделя", "Дневной long по EMA12/33 и EMA66 с дополнительным недельным фильтром и стопом ATR."),
    "ema-cross-33-66-long": ("EMA33/66 + EMA12 · long", "Long после пересечения EMA33/66 вверх при EMA12 выше EMA33; выход по тренду либо стопу ATR. Это не чистый кросс 33/66."),
    "ema-cross-33-66-weekly-filter": ("EMA33/66 + недельный фильтр", "Дневной long по EMA33/66 с подтверждением EMA12, недельным фильтром и стопом ATR."),
    "ema-support-33": ("Поддержка EMA33", "Дневной long при отскоке цены от EMA33 с фильтром тренда и стопом ATR."),
    "ema-support-33-weekly-filter": ("Поддержка EMA33 + неделя", "Отскок от EMA33 на 1D с недельным фильтром тренда и стопом ATR."),
    "ema-support-66": ("Поддержка EMA66", "Дневной long при отскоке цены от EMA66 с фильтром тренда и стопом ATR."),
    "ema-support-66-weekly-filter": ("Поддержка EMA66 + неделя", "Отскок от EMA66 на 1D с недельным фильтром тренда и стопом ATR."),
    "ema-hybrid-6-12-long-12-33-short": ("EMA6/12 long + EMA12/33 short", "Long управляется пересечением EMA6/12, short — пересечением EMA12/33."),
    "ema-hybrid-6-12-long-12-33-short-trend": ("EMA6/12 long с трендом + EMA12/33 short", "Long по EMA6/12 разрешён при EMA12 выше EMA33; short управляется EMA12/33."),
    "ema-cross-12-33-manual-channel": ("EMA12/33 + ручной канал", "Четыре опорные точки канала выбираются вручную на графике TradingView; массового воспроизводимого теста нет."),
}


def build() -> None:
    if set(RULES) != {p.name for p in REVIEWS.glob("ema-*") if p.is_dir()}:
        raise ValueError("research review catalog and README rule map differ")
    for slug, (title, rule) in RULES.items():
        folder = REVIEWS / slug
        pine = folder / "strategy.pine"
        pine_link = "strategy.pine"
        if slug == "ema-cross-12-33-long-short":
            pine = ROOT / "strategies" / slug / "strategy.pine"
            pine_link = f"../../../strategies/{slug}/strategy.pine"
        if not pine.exists():
            raise ValueError(f"missing Pine: {slug}")
        with (folder / "results.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        tested = [r for r in rows if r["status"] == "historical_test"]
        tickers = {r["ticker"] for r in tested}
        missing = len(rows) - len(tested)
        frames = ", ".join(dict.fromkeys(r["timeframe"] for r in rows))
        source = ", ".join(sorted({r["source"] for r in tested})) or "массового сопоставимого расчёта нет"
        positive = sum(r["outcome"] == "🟢 прибыль" for r in tested)
        negative = sum(r["outcome"] == "🔴 убыток" for r in tested)
        top_sections = []
        for frame in ("1H", "4H", "1D", "1W"):
            if frame not in {r["timeframe"] for r in rows}:
                continue
            candidates = [r for r in tested if r["timeframe"] == frame
                          and float(r["return_pct"]) > 0 and int(r["closed_trades"]) > 0]
            candidates.sort(key=lambda r: float(r["return_pct"]), reverse=True)
            top_sections += [f"### {frame}: топ‑5 по исторической доходности", ""]
            if not candidates:
                top_sections += ["Подходящих исторических результатов нет.", ""]
                continue
            top_sections += ["| Акция | Доходность | Закрытых | Прибыльных | Win rate | PF | Просадка |",
                             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
            for r in candidates[:5]:
                thin = " ⚠️" if int(r["closed_trades"]) < 10 else ""
                top_sections.append(f"| {r['ticker']}{thin} | +{r['return_pct']}% | "
                                    f"{r['closed_trades']} | {r['winning_trades']} | "
                                    f"{r['win_rate_pct']}% | {r['profit_factor']} | "
                                    f"{r['max_drawdown_pct']}% |")
            top_sections.append("")
        text = [
            f"# {title}", "", "## Правило", "", rule, "",
            "Точный расчёт индикаторов, дополнительные условия, размер позиции и ордера "
            f"зафиксированы в [Pine-скрипте]({pine_link}). Для ручной проверки откройте "
            "акцию Московской биржи в TradingView, выберите указанный интервал, "
            "вставьте скрипт в Pine Editor и сравните сделки в Strategy Tester.", "",
            "## Результаты по акциям", "",
            f"[Открыть единую таблицу всех акций](results.csv) — {len(rows)} строк "
            f"по 258 акциям TQBR и интервалам {frames}. Исторически рассчитано "
            f"{len(tested)} строк по {len(tickers)} акциям: 🟢 прибыль с закрытыми "
            f"сделками {positive}, 🔴 убыток {negative}; ⚪ нет сопоставимого теста "
            f"для {missing} строк. Строки без закрытых сделок также помечены ⚪. "
            "Пустые числовые поля означают отсутствие теста, а не нулевую доходность.", "",
            "В таблице: тикер, название компании, таймфрейм, доходность, число закрытых "
            "и прибыльных сделок, win rate, profit factor, просадка, даты и источник. "
            "Все результаты — локальные исторические расчёты по MOEX ISS; сделки Pine "
            "с ними поштучно ещё не сверены. `historical_test` не означает допуск "
            "к paper trading или доказанное преимущество.", "",
            "Топы ниже упорядочены **только по исторической доходности после базовых издержек**. "
            "Это быстрый обзор, не рейтинг надёжности и не рекомендация к торговле. "
            "⚠️ означает менее 10 закрытых сделок; особенно внимательно смотрите на это "
            "для недельных графиков.", "",
            *top_sections,
            "## Проверка и архив", "",
            f"Источник расчёта: {source}. Для short в историческом результате не подтверждены "
            "стоимость займа, дивидендные обязательства и доступность бумаги. "
            "Исполнение в TradingView может отличаться от локального расчёта. "
            "[Критерии допуска](../../../criteria/README.md) применяются отдельно; "
            "параметры, выбранные после просмотра истории, требуют новых данных.", "",
            "[Старые тикерные заметки, SVG и прежний список `success`](.archive/legacy_README.md) "
            "сохранены как архив. SVG — график локальных свечей MOEX, не скриншот "
            "TradingView. Архивные списки могли объединять разные направления или параметры; "
            "актуальный статус строк смотрите в `results.csv`.", "",
        ]
        if slug == "ema-cross-12-33-long-short":
            text += ["## Автоматическая бумажная проверка", "",
                     "Только для этой стратегии сейчас есть отдельная [Python-реализация сигнала](../../../strategies/ema-cross-12-33-long-short-1h/strategy.py) "
                     "на PLZL 1H. [Бумажный сервис](../../../service/paper_runner.py) загружает этот файл, "
                     "считает EMA12/33 по свечам MOEX и ведёт виртуальные позиции; Pine-файл он не читает. "
                     "Исполнение бумажного счёта позже, чем в Strategy Tester. "
                     "[Состояние и условия прогона](../../../papertrading/README.md). "
                     "Остальные Pine-стратегии автоматически не торгуются.", ""]
        (folder / "README.md").write_text("\n".join(text), encoding="utf-8")


if __name__ == "__main__":
    build()
