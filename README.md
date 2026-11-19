# Quant

## Project purpose

Quant is a local workspace for researching trading rules, checking historical results, and observing approved rules in virtual paper accounts. An experiment records its inputs, parameter search, monthly results, and review. A fixed strategy then supplies executable Python and Pine Script for signal comparison and paper trading. **The project does not place real orders.**

The current market-data integration uses MOEX ISS. Historical experiment results and live paper-account PnL are separate: neither is a forecast. The machine-readable admission and review rules live in [guardrails/POLICY.json](guardrails/POLICY.json); each experiment's exact scope lives in its own `protocol.json`.

## Project structure

| Path | Purpose |
| --- | --- |
| `experiments/<indicator>/<run>/` | Frozen protocol, experiment code, monthly results, report, and paper review. Start from [`experiments/template/`](experiments/template/). |
| `pipeline/` | Runs an experiment through validation, review, signal parity, and paper registration. |
| `eval/` and `guardrails/` | Historical evaluation and machine-readable admission and lifecycle rules. |
| `strategies/<id>/` | Fixed executable strategy, Pine Script, selection, and parity evidence. |
| `papertrading/setups/fleet/` | One configuration file per virtual account; generated account state is under `papertrading/live/`. |
| `service/` | Market-data polling and virtual account execution. |
| `web/` | Local dashboard for experiments, strategies, and paper accounts. |
| `data/` | Candle cache, historical snapshots, and corporate-action data. Large candle snapshots are excluded from Git. |
| `src/`, `scripts/`, `workers/`, `skills/`, `spec/`, `tests/` | Shared research code, utilities, automated research jobs, agent workflows, specifications, and tests. |

## Installation and first run

### 1. Install prerequisites

Install Git and Python 3.9 or newer. The runtime uses Python's standard library; there is no `pip install` step. On macOS, Homebrew can provide Python if needed:

```sh
brew install python
git --version
python3 --version
```

### 2. Clone and verify

```sh
git clone https://github.com/katovBash/quant.git
cd quant
python3 -m unittest discover -s tests -t .
```

Run all following commands from the repository root. The tests do not submit orders.

### 3. Start the local dashboard and paper trading

Open two terminal windows in the repository root. In the first, start the dashboard:

```sh
python3 -m web.server
```

In the second, start the virtual-account poller:

```sh
python3 -m service.paper_fleet --poll-seconds 900
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) in a browser. The repository includes paper-account setup files; the poller needs internet access to fetch current MOEX candles. Use `Ctrl+C` in each terminal to stop its process. Virtual account state is stored locally in `papertrading/live/`.

### 4. Reproduce an experiment (optional)

Full historical runs need the frozen snapshot in `data/candles/moex_scan/`, including the universe and candle files named by the experiment protocol. This large directory is not in Git. Copy it from a saved project instance before running:

Replace `<indicator>`, `<run>`, and `<id>` below with the corresponding directory names.

```sh
python3 -m pipeline.run 'experiments/<indicator>/<run>'
```

The resulting `results/PIPELINE.json` gives the current stage and next action. If it reports `NEEDS_FIXED_STRATEGY`, add `strategies/<id>/strategy.py` and `strategy.pine`, measure signal parity, and continue with:

```sh
python3 -m pipeline.run 'experiments/<indicator>/<run>' --existing-results --strategy-dir 'strategies/<id>'
```

The pipeline applies the rules in [`guardrails/POLICY.json`](guardrails/POLICY.json) before registering virtual accounts. For automated hypothesis discovery, see [`spec/daily_discovery.md`](spec/daily_discovery.md) and [`workers/discovery/`](workers/discovery/).
