"""Persistent job control shared by the dashboard and improvement worker."""

from __future__ import annotations

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from workers.discovery.control import read_json, write_json

ROOT = Path(__file__).resolve().parents[2]
STRATEGY_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
ACTIVE = {"PLANNING", "WAITING_REVIEW", "RUNNING", "BUILDING", "CALCULATING"}


def runtime(root: Path = ROOT) -> Path:
    return root / "workers/optimization/runtime"


def job_path(job_id: str, root: Path = ROOT) -> Path:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("invalid job id")
    return runtime(root) / "jobs" / job_id / "state.json"


@contextmanager
def locked(root: Path = ROOT):
    folder = runtime(root)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "jobs.lock").open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def read_job(job_id: str, root: Path = ROOT) -> dict:
    value = read_json(job_path(job_id, root))
    if not value:
        raise ValueError("job not found")
    return value


def update_job(job_id: str, patch: dict, root: Path = ROOT) -> dict:
    with locked(root):
        state = read_job(job_id, root)
        if state["stage"] == "CANCELLED" and patch.get("stage") != "CANCELLED":
            return state
        state.update(patch)
        state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(job_path(job_id, root), state)
        return state


def eligible(strategy_id: str, root: Path = ROOT) -> tuple[str, str]:
    if not STRATEGY_ID.fullmatch(strategy_id):
        raise ValueError("invalid strategy id")
    catalog = read_json(root / "strategies/catalog.json")
    rule = next((item for item in catalog.get("rules", []) if item.get("id") == strategy_id), None)
    if rule is None:
        raise ValueError("strategy is not in catalog")
    active = any(read_json(path).get("strategy") == strategy_id
                 for path in (root / "papertrading/setups/fleet").glob("*.json"))
    if not active:
        raise ValueError("strategy has no active paper setup")
    return str(rule.get("experiment") or ""), str(rule.get("label") or strategy_id)


def _spawn(job_id: str, phase: str, root: Path) -> int:
    folder = job_path(job_id, root).parent
    with (folder / "worker.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-m", "workers.optimization.worker", job_id, phase,
                                    "--root", str(root)], cwd=root, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return process.pid


def list_jobs(root: Path = ROOT, limit: int = 20) -> list[dict]:
    rows = [read_json(path) for path in (runtime(root) / "jobs").glob("*/state.json")]
    rows = [row for row in rows if row.get("id")]
    rows.sort(key=lambda row: row.get("created_at_utc", ""), reverse=True)
    for row in rows[:limit]:
        log = job_path(row["id"], root).parent / "worker.log"
        try:
            with log.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 12000))
                row["log_tail"] = stream.read().decode("utf-8", errors="replace")[-8000:]
        except OSError:
            row["log_tail"] = ""
    return rows[:limit]


def start(strategy_id: str, root: Path = ROOT) -> dict:
    experiment, label = eligible(strategy_id, root)
    with locked(root):
        existing = [read_json(path) for path in (runtime(root) / "jobs").glob("*/state.json")]
        if any(row.get("stage") in ACTIVE for row in existing):
            raise ValueError("another improvement job is active; finish or stop it first")
        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        state = {"id": job_id, "strategy_id": strategy_id, "strategy_label": label,
                 "parent_experiment": experiment, "stage": "PLANNING",
                 "created_at_utc": now, "updated_at_utc": now,
                 "plan": None, "guidance": "", "experiment": None, "error": None}
        write_json(job_path(job_id, root), state)
        try:
            pid = _spawn(job_id, "plan", root)
        except OSError as exc:
            state["stage"] = "FAILED"
            state["error"] = str(exc)
        else:
            state["worker_pid"] = pid
        write_json(job_path(job_id, root), state)
    return state


def continue_job(job_id: str, guidance: str, root: Path = ROOT) -> dict:
    if not isinstance(guidance, str) or len(guidance) > 4000:
        raise ValueError("guidance must be 4000 characters or fewer")
    with locked(root):
        state = read_job(job_id, root)
        if state["stage"] != "WAITING_REVIEW":
            raise ValueError("job is not awaiting review")
        state["guidance"] = guidance.strip()
        state["stage"] = "RUNNING"
        state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(job_path(job_id, root), state)
        try:
            state["worker_pid"] = _spawn(job_id, "run", root)
        except OSError as exc:
            state["stage"] = "FAILED"
            state["error"] = str(exc)
        write_json(job_path(job_id, root), state)
    return state


def cancel(job_id: str, root: Path = ROOT) -> dict:
    with locked(root):
        state = read_job(job_id, root)
        if state["stage"] not in ACTIVE:
            raise ValueError("job is not active")
        was_running = state["stage"] in ("PLANNING", "RUNNING", "BUILDING", "CALCULATING")
        state["stage"] = "CANCELLED"
        state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(job_path(job_id, root), state)
        pid = state.get("worker_pid")
    # A worker owns a separate process group, including its Codex child.
    if was_running and pid:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return state
