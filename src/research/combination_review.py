"""Audit component controls and tested variants in combined experiments."""

import statistics
from collections import defaultdict

from src.research.annual_returns import calendar_years


def audit(protocol: dict, rows: list[dict]) -> dict:
    design = protocol.get("combination_design")
    if not design:
        return {"applicable": False, "ok": True}
    components = design.get("components", [])
    controls = {name for component in components for name in component.get("controls", [])}
    combined = set(design.get("combined_variants", []))
    scope = design.get("scope")
    parameters_ok = all(component.get("parameters") and all(
        (isinstance(values, list) and bool(values)) or
        (isinstance(values, dict) and "start" in values and "stop" in values)
        for values in component["parameters"].values()) for component in components)
    factorial_axes = set(design.get("factorial_axes", []))
    grid = protocol.get("parameter_grid", {})
    grid_axes = set(grid.get("axes", {})) | {name for group in grid.get("groups", [])
                                            for name in group.get("axes", {})}
    factorial_ok = scope != "full_factorial" or (bool(factorial_axes) and factorial_axes <= grid_axes)
    declared = controls | combined | {"baseline"}
    observed = {(row["symbol"], row["timeframe"], row["variant"]) for row in rows}
    pairs = {(symbol, frame) for symbol, frame, _ in observed}
    missing = sorted((symbol, frame, variant) for symbol, frame in pairs
                     for variant in declared if (symbol, frame, variant) not in observed)
    expected = set(protocol.get("expected_variants", []))
    return {"applicable": True, "scope": scope,
            "components": len(components), "controls": sorted(controls),
            "combined_variants": sorted(combined), "observed_pairs": len(pairs),
            "missing_variant_pairs": len(missing), "missing_examples": missing[:10],
            "undeclared_variants": sorted(expected - declared),
            "parameters_declared": parameters_ok,
            "factorial_axes_missing": sorted(factorial_axes - grid_axes),
            "ok": len(components) >= 2 and bool(controls) and bool(combined)
                  and scope in ("fixed_parameter_transfer", "full_factorial")
                  and parameters_ok and factorial_ok and not missing
                  and not (expected - declared) and not (controls & combined)}


def report_section(protocol: dict, rows: list[dict], by_pair: dict) -> str:
    design = protocol.get("combination_design")
    if not design:
        return ""
    checked = audit(protocol, rows)
    lines = ["## Комбинация: отдельно и вместе", "",
             f"Объём: `{design.get('scope', 'не указан')}`. "
             "Это описание фактически проверенной сетки, а не всех возможных настроек. "
             f"Контролей: {len(checked['controls'])}; сочетаний: "
             f"{len(checked['combined_variants'])}; пар акция × интервал: "
             f"{checked['observed_pairs']}; недостающих строк варианта: "
             f"{checked['missing_variant_pairs']}.", "",
             "| Компонент | Проверенные параметры | Самостоятельный контроль |",
             "|---|---|---|"]
    for component in design["components"]:
        parameters = ", ".join(f"{key}={values}" for key, values in component["parameters"].items())
        controls = ", ".join(f"`{value}`" for value in component["controls"])
        lines.append(f"| {component['name']} | {parameters} | {controls} |")
    lines += ["", "Комбинации: " + ", ".join(f"`{name}`" for name in checked["combined_variants"]) + ".",
              "", "### Сопоставление на одинаковых акциях и интервалах", "",
              "Медиана годовой доходности по акциям. Для неполного года сравниваются "
              "только акции с одинаковым числом месяцев от января; число акций указано в ячейке.", ""]
    groups = defaultdict(list)
    for row in rows:
        variant = row["variant"]
        if variant not in checked["controls"] and variant not in checked["combined_variants"]:
            continue
        months = by_pair.get((row["symbol"], row["timeframe"], variant), [])
        if not months:
            continue
        years = {item["year"]: item for item in calendar_years(months)}
        groups[(row["timeframe"], variant)].append((months, years))
    if not groups:
        return "\n".join(lines + ["Контроли и комбинации отсутствуют в месячном расчёте.", ""])
    all_years = sorted({year for cases in groups.values() for _, years in cases for year in years})[-3:]
    final_year = all_years[-1]
    final_month = max((item[final_year]["last_month"] for cases in groups.values()
                       for _, item in cases if final_year in item), default=12)
    year_labels = [year + (f" 01–{final_month:02d} YTD" if year == final_year and final_month < 12 else "")
                   for year in all_years]
    lines += ["| Интервал | Вариант | " + " | ".join(year_labels) + " | Медиана прибыльных месяцев |",
              "|---|---|" + "---:|" * len(all_years) + "---:|"]
    for (frame, variant), cases in sorted(groups.items()):
        cells = []
        for year in all_years:
            values = [item[year]["return_pct"] for _, item in cases if year in item
                      and item[year]["return_pct"] is not None
                      and (item[year]["complete"] or
                           (year == final_year and item[year]["first_month"] == 1
                            and item[year]["last_month"] == final_month
                            and item[year]["months"] == final_month))]
            cells.append(f"{statistics.median(values):+.2f}% ({len(values)})" if values else "—")
        shares = [100 * sum(float(m["pnl_rub"]) > 0 for m in months) / len(months)
                  for months, _ in cases]
        lines.append(f"| {frame} | `{variant}` | {' | '.join(cells)} | "
                     f"{statistics.median(shares):.1f}% |")
    untested = design.get("untested_dependencies", [])
    lines += ["", "**Не проверенные зависимости:** " + ("; ".join(untested) if untested else "не перечислены") + ".",
              "Положительный результат одного сочетания не доказывает, что соседние параметры устойчивы.", ""]
    return "\n".join(lines)
