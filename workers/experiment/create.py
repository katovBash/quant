"""Build a new experiment in its own Codex subprocess."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def build(root: Path, day: str, candidate: dict,
          run_agent: Callable[..., str]) -> None:
    prompt = f"""Use the new-experiment skill and spec/daily_discovery.md. Implement
exactly this preregistered hypothesis in a NEW experiment, without touching
current paper accounts or unrelated dirty files:
{json.dumps(candidate, ensure_ascii=False, indent=2)}
Use scripts/create_indicator_run.py so an existing indicator family is reused.
Write a complete protocol.json with the frozen full instrument/timeframe/grid,
run.py and review.pine. Copy source_url, signal_rule, entry_rule and exit_rule
from the candidate into protocol.json verbatim. Record every meaningful indicator role, parameter axis
and excluded variant. Implement causal signals and focused tests. You may run
a tiny smoke test, but DO NOT run the full pipeline, register paper accounts,
or edit the discovery registry. End with the experiment path only.
"""
    run_agent(root, day, "build", prompt, read_only=False, timeout=3600)
