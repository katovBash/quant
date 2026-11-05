"""Preregister ten sourced mechanical trader hypotheses before any return scan."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.create_indicator_run import create

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-04"
METHODS = (
    ("john-bollinger", "bollinger-squeeze-breakout", [20, 30], ["1D", "1H", "4H"],
     "https://www.bollingerbands.com/tradestation-methods", "mechanical_interpretation",
     "BandWidth reaches its trailing 20-bar low, then price closes outside a band; exit at middle band."),
    ("john-bollinger", "bollinger-confirmed-breakout", [20, 30], ["1D", "1H", "4H"],
     "https://www.bollingerbands.com/_files/ugd/58be43_d09c50b6e8ea4afd9af0523ef94de876.pdf", "mechanical_interpretation",
     "Two consecutive closes outside the same Bollinger Band; exit at middle band. The published Method IV also uses ADX, omitted here as a deliberate isolated test."),
    ("brian-shannon", "shannon-avwap-reclaim", [20, 40], ["1D", "1H", "4H"],
     "https://alphatrends.net/anchored-vwap/", "mechanical_interpretation",
     "Anchor VWAP at the lowest low in the preceding lookback; enter long on reclaim above AVWAP, exit below it."),
    ("brian-shannon", "shannon-avwap-bounce", [20, 40], ["1D", "1H", "4H"],
     "https://alphatrends.net/archives/interview-stockbsessed-03112023/", "mechanical_interpretation",
     "Anchor VWAP at the lowest low in the preceding lookback; enter long on a touch and close above rising AVWAP, exit below it."),
    ("alexander-gerchik", "gerchik-false-breakout", [20, 40], ["1D", "4H"],
     "https://gerchik.com/videouroki/urovni-dlya-lozhnih-proboev-model-zahoda-v-sdelku", "mechanical_interpretation",
     "Prior range high/low is the level; wick breaks it but close returns inside. Trade toward range center."),
    ("alexander-gerchik", "gerchik-level-retest", [20, 40], ["1D", "4H"],
     "https://gerchik.com/journal/instrukczii/zahod-v-pozu-posle-lozhnogo-proboya/", "mechanical_interpretation",
     "Close breaks prior range level, next bar touches and closes beyond the former level; exit through range center."),
    ("alexander-elder", "elder-force-index", [2, 13], ["1D", "4H"],
     "https://www.elder.com/product-page/elder-disk-for-metastock-v2-0", "mechanical_interpretation",
     "Smoothed Force Index crosses zero in direction of EMA50 trend; exit on opposite Force Index sign."),
    ("william-oneil", "oneil-flat-base", [25, 35], ["1D"],
     "https://shop.investors.com/images/promotional/flat-b-b_112408.pdf", "mechanical_interpretation",
     "Flat base no deeper than 15% over 5-7 trading weeks; close above prior high on at least 1.4x volume; exit below SMA20."),
    ("william-oneil", "oneil-double-bottom", [35, 45], ["1D"],
     "https://get.investors.com/wp-content/uploads/2024/08/IBDD-How-to-buy-Stocks-infographic.pdf", "mechanical_interpretation",
     "Two comparable lows with intervening rally, depth at most 40%; close above prior base high on at least 1.4x volume; exit below SMA20. Mechanical proxy of the published pattern."),
    ("william-oneil", "oneil-cup-handle", [35, 45], ["1D"],
     "https://get.investors.com/wp-content/uploads/2024/08/IBDD-How-to-buy-Stocks-infographic.pdf", "mechanical_interpretation",
     "Base depth 15-35% with final handle no deeper than 15%; close above handle high on at least 1.4x volume; exit below SMA20. Mechanical proxy of the published pattern."),
)


def main() -> None:
    for author, method, lengths, frames, url, evidence, rule in METHODS:
        target = create(author, method)
        protocol = {
            "indicator_id": author, "run_id": method, "method_id": method,
            "status": "PREREGISTERED", "frozen_on": TODAY,
            "hypothesis": f"Test whether the mechanical {method} interpretation improves month-level outcomes over the same-stock buy-and-hold control.",
            "trader_attribution": {"name": author.replace("-", " ").title(),
                                   "source_url": url, "source_type": evidence,
                                   "source_checked_on": TODAY,
                                   "actual_trades_verified": False,
                                   "personal_return_status": "not_available",
                                   "rule_interpretation": rule},
            "source_snapshot": "MOEX ISS local snapshot 2026-10-30",
            "eligible_universe": {"snapshot_file": "data/candles/moex_scan/universe_2026-10-30.json",
                                  "cache_dir": "data/candles/moex_scan", "board": "TQBR",
                                  "requires_source_timeframes": ["1D"]},
            "corporate_actions": {"status": "unchecked", "applied_in_main_results": False,
                                  "splits_status": "unchecked", "dividend_source_status_file": "data/dividends/moex_coverage.json"},
            "signal_timeframes": frames,
            "parameter_grid": {"axes": {"lookback": {"values": lengths}},
                               "variant_template": method + "_{lookback}",
                               "include_baseline": True,
                               "max_combinations": len(lengths) + 1},
            "expected_variants": ["baseline"] + [f"{method}_{length}" for length in lengths],
            "parameter_rationale": "Two preregistered lookbacks bracket the published/default horizon; this is a bounded first grid, not a claim that all possible settings were searched.",
            "min_bars": max(lengths) + 52,
            "baseline": "One 25% long buy-and-hold position on the same stock and timeframe, filled next open",
            "signal_rule": rule + " All signals use completed bars and next-open fills; no current incomplete higher-timeframe bar.",
            "initial_capital_rub": 1000000, "position_weight_pct": 25,
            "simulator_cost_bps_per_side": 15,
            "cost_status": "after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots",
            "start": "2024-01-01", "split": "2026-01-01", "late_sample_status": "seen_history",
            "primary_evaluation": "monthly", "selection": "Research ranking only; no automatic trading approval",
            "run_command": f"python3 -m pipeline.run experiments/{author}/{method}",
            "limitations": ["No verified personal trade journal", "Author's discretionary choices are not reproduced",
                            "MOEX corporate-action coverage is incomplete", "Pattern proxies require chart review"]}
        (target / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (target / "run.py").write_text(
            "from pathlib import Path\nimport sys\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[3]))\n"
            "from src.research.trader_method_run import run\n"
            "if __name__ == '__main__':\n"
            "    run(Path(__file__).resolve().parent, smoke='--smoke' in sys.argv)\n",
            encoding="utf-8")
        summary = target / "SUMMARY.md"
        summary.write_text(f"# {method}\n\n" + summary.read_text(encoding="utf-8"), encoding="utf-8")
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
