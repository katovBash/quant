"""Read-only local dashboard for paper trading accounts."""

from __future__ import annotations

import argparse
import fcntl
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from service.account_record import account_record

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "papertrading/live"
INDEX = Path(__file__).with_name("index.html")
CATALOG = ROOT / "strategies/catalog.json"
STRATEGIES = ROOT / "strategies"
SETUPS = ROOT / "papertrading/setups/fleet"
POLL_SECONDS = 900


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
    for row in fleet.get("accounts", []):
        account_id = row.get("account_id", "")
        if not account_id or not all(c.isalnum() or c in "-_" for c in account_id):
            continue
        state = _read_json(live / account_id / "state.json") or {}
        accounts.append(account_record(row, state))
    failures = [row for row in accounts if row["status"] != "OK"]
    shared_source_error = bool(failures and len(failures) == len(accounts)
                               and all(row["status"] == "DATA_UNAVAILABLE" for row in failures)
                               and len({row["error"] for row in failures}) == 1)
    catalog = _read_json(CATALOG) or {}
    configured = {}
    for path in SETUPS.glob("*.json"):
        setup = _read_json(path) or {}
        if setup.get("strategy") and setup.get("symbol"):
            configured.setdefault(setup["strategy"], set()).add(setup["symbol"])
    rules = []
    for rule in catalog.get("rules", []):
        selected = _read_json(STRATEGIES / rule["id"] / "selection.json") or {}
        rules.append({"id": rule["id"], "label": rule.get("label", rule["id"]),
                      "experiment": rule["experiment"],
                      "timeframe": rule["timeframe"],
                      "history_snapshot": selected.get("snapshot"),
                      "status": selected.get("status"),
                      "median_return_pct": selected.get("median_return_pct"),
                      "profitable_tickers": selected.get("profitable_tickers"),
                      "tested_tickers": selected.get("tested_tickers"),
                      "top10": selected.get("top10", []),
                      "configured_symbols": sorted(configured.get(rule["id"], set())),
                      "limitation": selected.get("limitation")})
    return {
        "observed_at": observed, "age_seconds": age_seconds,
        "fleet_running": _fleet_running(live),
        "fresh": age_seconds is not None and age_seconds <= 2 * POLL_SECONDS,
        "shared_source_error": shared_source_error,
        "source_error": failures[0]["error"] if shared_source_error else None,
        "accounts": accounts,
        "rules": rules,
        "fleet_requests": recent_json_lines(live / "fleet_requests.ndjson", 16),
        "web_requests": recent_json_lines(live / "web_access.ndjson", 8),
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
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
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
