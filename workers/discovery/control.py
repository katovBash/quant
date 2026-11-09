"""Persistent local control shared by the CLI and the dashboard."""

from __future__ import annotations

import json
import fcntl
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def runtime(root: Path = ROOT) -> Path:
    return root / "workers" / "discovery" / "runtime"


def read_json(path: Path, default: dict | None = None) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else (default or {})
    except (FileNotFoundError, OSError, ValueError):
        return dict(default or {})


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".discovery-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def _state_lock(root: Path):
    folder = runtime(root)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "state.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def status(root: Path = ROOT) -> dict:
    data = read_json(runtime(root) / "state.json")
    return {"enabled": data.get("enabled") is True,
            "last_run_day": data.get("last_run_day"),
            "last_result": data.get("last_result"),
            "last_report": data.get("last_report"),
            "updated_at_utc": data.get("updated_at_utc")}


def set_enabled(enabled: bool, root: Path = ROOT) -> dict:
    path = runtime(root) / "state.json"
    with _state_lock(root):
        data = read_json(path)
        data["enabled"] = bool(enabled)
        data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(path, data)
    return status(root)


def record_run(day: str, result: str, report: str | None,
               root: Path = ROOT) -> dict:
    path = runtime(root) / "state.json"
    with _state_lock(root):
        data = read_json(path)
        data["last_run_day"] = day
        data["last_result"] = result
        data["last_report"] = report
        data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(path, data)
    return status(root)
