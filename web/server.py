"""Local dashboard for experiments and paper trading accounts."""

from __future__ import annotations

import argparse
import fcntl
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from workers.discovery.control import set_enabled as set_discovery_enabled
from workers.discovery.control import status as discovery_status
from workers.optimization.control import cancel as cancel_improvement
from workers.optimization.control import continue_job as continue_improvement
from workers.optimization.control import list_jobs as improvement_jobs
from workers.optimization.control import start as start_improvement
from service.account_record import account_record
from src.research.corporate_actions import load_dividend_snapshot
from src.research.data_quality import candle_quality

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "papertrading/live"
INDEX = Path(__file__).with_name("index.html")
CATALOG = ROOT / "strategies/catalog.json"
STRATEGIES = ROOT / "strategies"
SETUPS = ROOT / "papertrading/setups/fleet"
DIVIDEND_FILES = (ROOT / "data/dividends/latest.json",
                  ROOT / "data/dividends/sfin_2026-11-04.json")
CACHE = ROOT / "data/candles/moex_scan"
POLL_SECONDS = 900
EXPERIMENT_ID = re.compile(r"[a-z0-9-]+(?:/[a-z0-9-]+)*\Z")


def recent_json_lines(path: Path, limit: int = 12) -> list[dict]:
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - 65536))
            lines = stream.read().splitlines()
            if size > 65536:
                lines = lines[1:]
    except OSError:
        return []
    result = []
    for line in reversed(lines):
        try:
            result.append(json.loads(line))
        except (ValueError, UnicodeDecodeError):
            continue
        if len(result) >= limit:
            break
    return result


def render_page(data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return INDEX.read_text(encoding="utf-8").replace("__INITIAL_SNAPSHOT__", payload).encode("utf-8")


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def pine_path(strategy_id: str) -> Path | None:
    """Resolve only a catalogued strategy's own TradingView source."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", strategy_id):
        return None
    catalog = _read_json(CATALOG) or {}
    if strategy_id not in {row.get("id") for row in catalog.get("rules", [])}:
        return None
    directory = (STRATEGIES / strategy_id).resolve()
    if directory.parent != STRATEGIES.resolve():
        return None
    source = directory / "strategy.pine"
    if source.is_symlink() or not source.is_file() or source.resolve().parent != directory:
        return None
    return source


def experiment_rows(root: Path) -> list[dict]:
    """Read current experiment artifacts; the generated registry is only an index."""
    registry = _read_json(root / "experiments/PACKAGE_STATUS.json") or {}
    rows = []
    for indexed in registry.get("experiments", []):
        relative = str(indexed.get("experiment", ""))
        if not relative.startswith("experiments/"):
            continue
        experiment_id = relative.removeprefix("experiments/")
        if not EXPERIMENT_ID.fullmatch(experiment_id):
            continue
        results = root / "experiments" / experiment_id / "results"
        package = _read_json(results / "PACKAGE_STATUS.json") or indexed
        review = _read_json(results / "paper_review.json") or {}
        decision = _read_json(results / "decision.json") or review.get("decision") or {}
        if review.get("activation") and not review.get("deactivation"):
            continue
        state = ("PAPER_STOPPED" if review.get("deactivation") else
                 "CLOSED" if decision.get("status") == "CLOSED" else
                 package.get("status", "REVIEW_ONLY"))
        reason = (str(decision.get("reason") or "") if state == "CLOSED" else
                  str(review.get("deactivation", {}).get("reason") or "") if state == "PAPER_STOPPED" else
                  "; ".join(str(value) for value in (package.get("missing_required_evidence") or
                                                      review.get("blockers") or [])[:2]))
        if not reason and state == "READY_FOR_FIXED_STRATEGY":
            reason = "Нужны фиксированная стратегия и сверка сигналов до запуска paper trading"
        elif not reason and state != "CLOSED":
            reason = "Ожидает проверки результатов"
        rule = review.get("rule") or {}
        rows.append({"id": experiment_id, "status": state,
                     "review_state": "closed" if state == "CLOSED" else "pending",
                     "reason": reason, "decided_by": decision.get("decided_by"),
                     "rule": rule.get("variant"), "timeframe": rule.get("timeframe"),
                     "candidate_stocks": len(review.get("stocks") or []),
                     "paper_gate": package.get("paper_gate"),
                     "has_report": (results / "REPORT.md").is_file(),
                     "has_paper_review": (results / "PAPER_REVIEW.md").is_file()})
    return sorted(rows, key=lambda row: (row["review_state"] == "closed", row["id"]))


def experiment_report_path(root: Path, experiment_id: str, kind: str) -> Path | None:
    if not EXPERIMENT_ID.fullmatch(experiment_id) or kind not in ("final", "paper"):
        return None
    if experiment_id not in {row["id"] for row in experiment_rows(root)}:
        return None
    folder = (root / "experiments" / experiment_id / "results").resolve()
    if not folder.is_relative_to((root / "experiments").resolve()):
        return None
    source = folder / ("REPORT.md" if kind == "final" else "PAPER_REVIEW.md")
    return source if source.is_file() and not source.is_symlink() and source.resolve().parent == folder else None


def _fleet_running(live: Path) -> bool:
    lock_path = live / "fleet.lock"
    if not lock_path.exists():
        return False
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock, fcntl.LOCK_UN)
        return False


def snapshot(live: Path = LIVE, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    fleet = _read_json(live / "fleet_status.json") or {}
    observed = fleet.get("observed_at")
    age_seconds = None
    if observed:
        try:
            age_seconds = max(0, int((now - datetime.fromisoformat(observed)).total_seconds()))
        except (ValueError, TypeError):
            pass
    accounts = []
    events = []
    configured = {}
    active_account_ids = set()
    for path in SETUPS.glob("*.json"):
        setup = _read_json(path) or {}
        if setup.get("strategy") and setup.get("symbol"):
            configured.setdefault(setup["strategy"], set()).add(setup["symbol"])
            if setup.get("account_id"):
                active_account_ids.add(setup["account_id"])
    for row in fleet.get("accounts", []):
        account_id = row.get("account_id", "")
        if not account_id or not all(c.isalnum() or c in "-_" for c in account_id):
            continue
        if live.resolve() == LIVE.resolve() and account_id not in active_account_ids:
            continue
        state = _read_json(live / account_id / "state.json") or {}
        accounts.append(account_record(row, state))
        events.extend({"account_id": account_id, **event}
                      for event in state.get("trades_log", []))
    events.sort(key=lambda event: (event.get("fill_bar") or event.get("observed_at") or "",
                                   event.get("observed_at") or ""), reverse=True)
    failures = [row for row in accounts if row["status"] != "OK"]
    shared_source_error = bool(failures and len(failures) == len(accounts)
                               and all(row["status"] == "DATA_UNAVAILABLE" for row in failures)
                               and len({row["error"] for row in failures}) == 1)
    catalog = _read_json(CATALOG) or {}
    rules = []
    action_snapshot = {"covered_symbols": [], "events": []}
    for event_file in DIVIDEND_FILES:
        if not event_file.is_file():
            continue
        try:
            action_snapshot, _ = load_dividend_snapshot(event_file)
            break
        except (OSError, ValueError, KeyError, TypeError):
            continue
    for rule in catalog.get("rules", []):
        active_symbols = configured.get(rule["id"], set())
        if not active_symbols:
            continue
        selected = _read_json(STRATEGIES / rule["id"] / "selection.json") or {}
        research_update = (_read_json(ROOT / selected["research_update_file"]) or {}
                           if selected.get("research_update_file") else {})
        updated_symbols = research_update.get("symbols", {})
        history = _read_json(STRATEGIES / rule["id"] / "history_snapshot.json") or {}
        history_symbols = history.get("symbols", {})
        top10 = [dict(row, **updated_symbols.get(row.get("symbol"), {}),
                      history=history_symbols.get(row.get("symbol"), {}))
                 for row in selected.get("top10", []) if row.get("symbol") in active_symbols]
        symbols = sorted(set(configured.get(rule["id"], set()))
                         | {row.get("symbol") for row in top10 if row.get("symbol")})
        data_quality = {}
        for symbol in symbols:
            dividends = [event for event in action_snapshot["events"] if event["symbol"] == symbol]
            data_quality[symbol] = {
                "dividends": "verified_unapplied" if symbol in action_snapshot["covered_symbols"]
                             else "unverified",
                "dividend_events": len(dividends),
                "splits": "unverified",
                "candles": candle_quality(CACHE, symbol, rule["timeframe"])}
        rules.append({"id": rule["id"], "label": rule.get("label", rule["id"]),
                      "experiment": rule["experiment"],
                      "timeframe": rule["timeframe"],
                      "history_snapshot": selected.get("snapshot"),
                      "history_cost_status": selected.get("cost_status"),
                      "status": selected.get("status"),
                      "median_return_pct": selected.get("median_return_pct"),
                      "profitable_tickers": selected.get("profitable_tickers"),
                      "tested_tickers": selected.get("tested_tickers"),
                      "top10": top10,
                      "data_quality": data_quality,
                      "configured_symbols": sorted(configured.get(rule["id"], set())),
                      "pine_available": pine_path(rule["id"]) is not None,
                      "limitation": selected.get("limitation")})
    return {
        "observed_at": observed, "age_seconds": age_seconds,
        "fleet_running": _fleet_running(live),
        "fresh": age_seconds is not None and age_seconds <= 2 * POLL_SECONDS,
        "shared_source_error": shared_source_error,
        "source_error": failures[0]["error"] if shared_source_error else None,
        "accounts": accounts,
        "events": events,
        "rules": rules,
        "experiments": experiment_rows(ROOT),
        "fleet_requests": recent_json_lines(live / "fleet_requests.ndjson", 16),
        "web_requests": recent_json_lines(live / "web_access.ndjson", 8),
        "discovery": discovery_status(ROOT),
        "improvements": improvement_jobs(ROOT),
    }


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        row = {"at": datetime.now(timezone.utc).isoformat(), "process": "quant-paper-web",
               "method": self.command, "path": urlsplit(self.path).path, "http_status": code}
        try:
            with (LIVE / "web_access.ndjson").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass
        super().log_request(code, size)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            body = render_page(snapshot())
            content_type = "text/html; charset=utf-8"
        elif path == "/api/status":
            body = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif path.startswith("/api/strategies/") and path.endswith("/pine"):
            parts = path.split("/")
            source = pine_path(parts[3]) if len(parts) == 5 else None
            if source is None:
                self.send_error(404)
                return
            try:
                body = source.read_bytes()
            except OSError:
                self.send_error(500)
                return
            content_type = "text/plain; charset=utf-8"
        elif path.startswith("/api/experiments/") and path.endswith("/report"):
            experiment_id = unquote(path[len("/api/experiments/"):-len("/report")].rstrip("/"))
            kind = "paper" if urlsplit(self.path).query == "kind=paper" else "final"
            source = experiment_report_path(ROOT, experiment_id, kind)
            if source is None:
                self.send_error(404)
                return
            try:
                body = source.read_bytes()
            except OSError:
                self.send_error(500)
                return
            content_type = "text/markdown; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in ("/api/discovery", "/api/improvements"):
            self.send_error(404)
            return
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if self.headers.get("Origin") != expected_origin:
            self.send_error(403, "Same-origin request required")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > (8192 if path == "/api/improvements" else 128):
                raise ValueError("invalid body size")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("expected object")
        except (ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid JSON body")
            return
        try:
            if path == "/api/discovery":
                if type(payload.get("enabled")) is not bool:
                    raise ValueError("enabled must be boolean")
                result = set_discovery_enabled(payload["enabled"], ROOT)
            elif payload.get("action") == "start":
                result = start_improvement(payload.get("strategy_id", ""), ROOT)
            elif payload.get("action") == "continue":
                result = continue_improvement(payload.get("job_id", ""),
                                              payload.get("guidance", ""), ROOT)
            elif payload.get("action") == "cancel":
                result = cancel_improvement(payload.get("job_id", ""), ROOT)
            else:
                raise ValueError("unknown improvement action")
        except (ValueError, TypeError) as exc:
            self.send_error(400, str(exc))
            return
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Paper trading dashboard: http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
