"""Freeze nine distinct indicator hypotheses before their first full run."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from create_indicator_run import create


ROOT = Path(__file__).resolve().parents[1]
SPECS = {
    "aroon": ("trend-cross", "Tushar Chande", "https://www.tradingview.com/support/solutions/43000501801-aroon-indicator/", [14, 25], ["cross", "strong"], "Aroon recency cross, with or without a 70/30 strength requirement, may detect trend starts."),
    "williams": ("percent-r-reentry", "Larry Williams", "https://www.tradingview.com/support/solutions/43000501985-williams-r-r/", [14, 28], ["rebound", "trend"], "Leaving Williams %R extremes may favor either mean reversion or trend continuation."),
    "stoch": ("stochastic-cross", "George Lane", "https://www.tradingview.com/support/solutions/43000502332-stochastic-stoch/", [14, 28], ["cross", "extreme"], "Stochastic K/D cross may be more useful near extremes than at all levels."),
    "keltner": ("atr-envelope-break", "Chester Keltner / Linda Bradford Raschke", "https://www.tradingview.com/support/solutions/43000502266-keltner-channels-kc/", [20, 30], ["narrow", "wide"], "Close outside an EMA/ATR envelope may identify trends; width may affect false breaks."),
    "ichimoku": ("visible-cloud-break", "Goichi Hosoda", "https://www.tradingview.com/support/solutions/43000589152-ichimoku-cloud/", [26, 22], ["break", "aligned"], "Break above/below the cloud visible at decision time may identify durable trends; cloud direction may filter failures."),
    "mfi": ("money-flow-reentry", "Gene Quong / Avrum Soudack", "https://www.tradingview.com/support/solutions/43000502348-money-flow-mfi/", [14, 28], ["rebound", "trend"], "Volume-weighted money flow may resolve whether extremes favor reversal or continuation."),
    "cmf": ("money-flow-cross", "Marc Chaikin", "https://www.tradingview.com/support/solutions/43000501974-chaikin-money-flow-cmf/", [20, 40], ["zero", "buffer"], "CMF zero crosses may improve if a five-percent pressure buffer filters noise."),
    "dmi": ("directional-cross", "J. Welles Wilder", "https://www.tradingview.com/support/solutions/43000502250-directional-movement-dmi/", [14, 28], ["adx20", "adx25"], "Directional cross during ADX-confirmed trend may reduce sideways reversals; strength threshold may matter."),
    "cci": ("deviation-extremes", "Donald Lambert", "https://www.tradingview.com/support/solutions/43000502001-commodity-channel-index-cci/", [20, 30], ["rebound", "trend"], "CCI crossings of +/-100 may work as either reversal or momentum continuation signals."),
}


def main() -> None:
    for family, (run_id, author, url, lengths, modes, hypothesis) in SPECS.items():
        target = create(family, run_id)
        variant_names = [f"{family}_{length}_{mode}" for length in lengths for mode in modes]
        protocol = {
            "indicator_id": family, "run_id": run_id, "method_id": family,
            "status": "PREREGISTERED", "frozen_on": str(date.today()),
            "hypothesis": hypothesis,
            "research_provenance": {
                "type": "mechanical_interpretation", "author": author,
                "primary_source": url, "source_checked_on": str(date.today()),
                "actual_trades_verified": False, "personal_return_status": "not_available",
                "source_status": "Official TradingView indicator description and formula consulted; no personal trade journal claimed.",
                "adaptations": "Entry at completed-bar crossing; opposite directional entry reverses at next open. Parameters and confirmation modes are research hypotheses, not the named author's personal trading rules.",
                "research_family": {"sources_reviewed": 1, "hypotheses_selected": 1, "existing_comparators": []}},
            "source_snapshot": "MOEX ISS local snapshot 2026-10-30",
            "eligible_universe": {"snapshot_file": "data/candles/moex_scan/universe_2026-10-30.json", "cache_dir": "data/candles/moex_scan", "board": "TQBR", "requires_source_timeframes": ["1D"]},
            "required_data": ["completed OHLCV bars" if family in ("mfi", "cmf") else "completed OHLC bars"],
            "availability_lag": "All signal inputs become known after bar close; order fills at next available bar open. Ichimoku uses only the cloud values already plotted at that close.",
            "corporate_actions": {"status": "unchecked", "applied_in_main_results": False, "splits_status": "unchecked", "dividend_source_status_file": "data/dividends/moex_coverage.json"},
            "signal_timeframes": ["1H", "4H", "1D", "1W"],
            "entry_design": {"mechanisms": modes, "confirmation": "one completed signal bar with causal indicator values", "decision_time": "bar close", "delay_bars": 1, "not_applicable": ["sub-hour history is not consistently available for the full frozen universe"]},
            "exit_design": {"mechanisms": ["reverse at next opposite qualified signal"], "parameter_ranges": {}, "decision_time": "bar close, next-open fill", "not_applicable": []},
            "parameter_grid": {"axes": {"length": {"values": lengths}, "mode": {"values": modes}}, "variant_template": f"{family}_{{length}}_{{mode}}", "include_baseline": True, "max_combinations": 5},
            "expected_variants": ["baseline", *variant_names],
            "parameter_rationale": "Two conventional neighboring horizons and two mechanically distinct signal interpretations form a complete 2x2 grid. This bounded grid was frozen before inspecting PnL; it is not a claim to have tested every possible numerical setting.",
            "min_bars": 100,
            "baseline": "One 25% long buy-and-hold position on the same stock and timeframe, filled next open",
            "signal_rule": hypothesis + " Exact causal implementation: src/research/classic_indicator_grid.py; opposite signal reverses at next open.",
            "signal_semantics": "Independent directional order for each symbol and timeframe; not a common-capital portfolio.",
            "evaluation_unit": "Independent 1m RUB virtual account per stock and timeframe.",
            "initial_capital_rub": 1000000, "position_weight_pct": 25,
            "simulator_cost_bps_per_side": 15,
            "cost_status": "after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots",
            "start": "2024-01-01", "split": "2026-01-01", "late_sample_status": "seen_history", "primary_evaluation": "monthly",
            "selection": "Train-month ranking, then latest complete 12m after-cost return >10% for every liquid stock. Late history is seen, not independent holdout.",
            "run_command": f"python3 -m pipeline.run experiments/{family}/{run_id}",
            "limitations": ["Historical parameter search; late history used for acceptance gate", "Corporate actions and short borrowing not in primary PnL", "Pine/Python trade parity unverified until fixed strategy stage"],
        }
        (target / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (target / "run.py").write_text(
            '"""Full-universe preregistered classic-indicator experiment."""\n'
            'from pathlib import Path\nimport sys\n'
            'sys.path.insert(0, str(Path(__file__).resolve().parents[3]))\n'
            'from src.research.trader_method_run import run\n'
            'from src.research.classic_indicator_grid import signals_for_method\n'
            f'METHOD = "{family}"\n'
            'if __name__ == "__main__":\n'
            '    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,\n'
            '        signal_factory=lambda variant, bars: signals_for_method(METHOD, variant, bars))\n', encoding="utf-8")
        (target / "SUMMARY.md").write_text(
            f"# {author}: {run_id}\n\nHypothesis: {hypothesis}\n\n"
            f"Source: {url}\n\nStatus: preregistered, calculation pending.\n"
            "The source defines the indicator; entries, exits and parameter grid are explicit research adaptations.\n", encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main()
