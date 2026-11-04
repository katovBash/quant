"""Report actual experiment coverage and traceable strategy folders."""

from __future__ import annotations

import ast
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ("15M", "30M", "1H", "4H", "1D")
OUT = ROOT / "experiments/STRATEGY_COVERAGE.md"


def report() -> str:
    strategies = sorted((ROOT / "strategies").glob("*/README.md"))
    report_lines = [
        "# Покрытие экспериментов и перенос в стратегии",
        "",
        "Снимок строится из `results/progress.csv` и ссылок в README стратегий командой "
        "`python3 scripts/audit_experiment_strategy_coverage.py`. "
        "`complete_previous` считается завершённым; повторы одного тикера и интервала учитываются один раз.",
        "",
        "Число строк перебора не равно числу стратегий. Стратегия — одно выбранное и зафиксированное правило. "
        "Отсутствие стратегии может означать, что вариант не отобран или ручная проверка ещё не завершена.",
        "",
        "| Эксперимент | 15M | 30M | 1H | 4H | 1D | Стратегии с прямой ссылкой |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for experiment in sorted((ROOT / "experiments").glob("*-grid-search")):
        progress = experiment / "results/progress.csv"
        if not progress.exists():
            continue
        manifest_path = experiment / "results/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        completed: dict[str, set[str]] = defaultdict(set)
        seen: dict[str, set[str]] = defaultdict(set)
        with progress.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                frame, symbol = row.get("timeframe"), row.get("symbol")
                if frame not in FRAMES or not symbol:
                    continue
                seen[frame].add(symbol)
                if row.get("status") in ("complete", "complete_previous"):
                    completed[frame].add(symbol)
        planned = len(manifest.get("symbols", [])) or 258
        frame_cells = []
        for frame in FRAMES:
            frame_cells.append(f"{len(completed[frame])}/{planned}" if frame in manifest.get("timeframes", []) else "—")
        links = []
        needle = f"experiments/{experiment.name}/"
        for readme in strategies:
            if needle in readme.read_text(encoding="utf-8"):
                slug = readme.parent.name
                links.append(f"[{slug}](../strategies/{slug}/README.md)")
        report_lines.append(f"| [{experiment.name}]({experiment.name}/README.md) | " +
                            " | ".join(frame_cells) + " | " +
                            (", ".join(links) if links else "нет") + " |")
    report_lines += [
        "",
        "Числитель — реально завершённые тикеры; знаменатель — заявленная вселенная. "
        "Пропуски из-за недостатка свечей остаются пропусками. Знак «—» означает, что интервал не был включён в manifest.",
        "",
        "Исследование [двух индикаторов](double-indicator/sma-cross-sideways-filters-smlt-1h/README.md) "
        "проводилось отдельно на SMLT 1H; прежняя стратегия удалена после проверки месячного риска. "
        "Исследование режимов рынка описывает прогноз события, а не торговые сделки, поэтому прямой перенос в стратегию не требуется.",
        "",
        "Для оценки достаточности одного кандидата нужно отдельно проверять число его сделок, "
        "соседние параметры, результаты на других бумагах без перенастройки, издержки и новые данные. "
        "Покрытие вселенной само по себе не подтверждает преимущество.",
        "",
    ]
    setups = defaultdict(list)
    for path in sorted((ROOT / "papertrading/setups/fleet").glob("*.json")):
        setup = json.loads(path.read_text(encoding="utf-8"))
        setups[setup["strategy"]].append(setup["account_id"])
    report_lines += [
        "## Проверка комплектности стратегий",
        "",
        "| Стратегия | Python | Pine | Настроенных виртуальных счетов |",
        "| --- | --- | --- | ---: |",
    ]
    for readme in strategies:
        if readme.parent.name == "template":
            continue
        slug = readme.parent.name
        python_path = readme.parent / "strategy.py"
        python = "да" if python_path.exists() else "**нет**"
        pine = "да" if (readme.parent / "strategy.pine").exists() else "**нет**"
        strategy_id = slug
        if python_path.exists():
            for node in ast.parse(python_path.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "STRATEGY_ID" for target in node.targets):
                    strategy_id = ast.literal_eval(node.value)
                    break
        report_lines.append(f"| [{slug}](../strategies/{slug}/README.md) | {python} | {pine} | {len(setups[strategy_id])} |")
    report_lines += [
        "",
        "Здесь проверено наличие файлов и setup. Равенство сигналов Python и Pine, фактическое "
        "исполнение и корректность short-расходов требуют отдельной проверки. "
        "Живое состояние берётся из `papertrading/live/fleet_status.json`, а не из этого снимка.",
        "",
    ]
    return "\n".join(report_lines)


if __name__ == "__main__":
    OUT.write_text(report(), encoding="utf-8")
    print(OUT)
