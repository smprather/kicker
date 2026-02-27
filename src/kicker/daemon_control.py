from __future__ import annotations

import json
import os
import signal
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "kicker"


def leader_file_path(state_dir: Path | None = None) -> Path:
    return (state_dir or default_state_dir()) / "leader.json"


@dataclass(slots=True)
class LeaderInfo:
    hostname: str
    pid: int
    start_time: float | None = None
    lease_expires_at: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LeaderInfo":
        hostname = str(payload["hostname"])
        pid = int(payload["pid"])
        start_time_raw = payload.get("start_time")
        lease_raw = payload.get("lease_expires_at")
        start_time = float(start_time_raw) if start_time_raw is not None else None
        lease_expires_at = float(lease_raw) if lease_raw is not None else None
        return cls(
            hostname=hostname,
            pid=pid,
            start_time=start_time,
            lease_expires_at=lease_expires_at,
        )


@dataclass(slots=True)
class StopResult:
    exit_code: int
    message: str


def load_leader_info(state_dir: Path | None = None) -> LeaderInfo | None:
    leader_file = leader_file_path(state_dir)
    if not leader_file.exists():
        return None

    with leader_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("leader metadata must be a JSON object")
    return LeaderInfo.from_dict(payload)


def _is_pid_alive(pid: int, kill_fn: Callable[[int, int], None]) -> bool:
    if pid <= 0:
        return False

    try:
        kill_fn(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _try_signal(
    pid: int,
    sig: int,
    kill_fn: Callable[[int, int], None],
) -> bool:
    try:
        kill_fn(pid, sig)
    except ProcessLookupError:
        return False
    return True


def stop_active_daemon(
    *,
    force: bool,
    quiet: bool,
    state_dir: Path | None = None,
    wait_seconds: float = 5.0,
    poll_seconds: float = 0.1,
    host_fn: Callable[[], str] = socket.gethostname,
    now_fn: Callable[[], float] = time.time,
    sleep_fn: Callable[[float], None] = time.sleep,
    kill_fn: Callable[[int, int], None] = os.kill,
) -> StopResult:
    try:
        leader = load_leader_info(state_dir=state_dir)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return StopResult(1, f"Invalid daemon metadata: {exc}")

    if leader is None:
        if quiet:
            return StopResult(0, "No daemon is running.")
        return StopResult(1, "No daemon is running.")

    current_host = host_fn()
    if leader.hostname != current_host:
        return StopResult(
            1,
            f"Active daemon is on host '{leader.hostname}', current host is '{current_host}'.",
        )

    if leader.pid <= 0:
        return StopResult(1, f"Invalid daemon pid in metadata: {leader.pid}")

    leader_file = leader_file_path(state_dir)
    alive_before = _is_pid_alive(leader.pid, kill_fn=kill_fn)
    if not alive_before:
        # Stale metadata; clear it.
        try:
            leader_file.unlink(missing_ok=True)
        except OSError as exc:
            return StopResult(1, f"Failed to clear stale metadata: {exc}")
        return StopResult(0, "No daemon is running. Cleared stale metadata.")

    _try_signal(leader.pid, signal.SIGTERM, kill_fn=kill_fn)

    deadline = now_fn() + wait_seconds
    while now_fn() < deadline:
        if not _is_pid_alive(leader.pid, kill_fn=kill_fn):
            break
        sleep_fn(poll_seconds)

    still_alive = _is_pid_alive(leader.pid, kill_fn=kill_fn)
    if still_alive and force:
        _try_signal(leader.pid, signal.SIGKILL, kill_fn=kill_fn)
        # Give the OS a short chance to reap.
        deadline = now_fn() + min(1.0, wait_seconds)
        while now_fn() < deadline and _is_pid_alive(leader.pid, kill_fn=kill_fn):
            sleep_fn(poll_seconds)
        still_alive = _is_pid_alive(leader.pid, kill_fn=kill_fn)

    if still_alive:
        return StopResult(
            1,
            f"Failed to stop daemon pid {leader.pid}. Retry with --force.",
        )

    try:
        leader_file.unlink(missing_ok=True)
    except OSError as exc:
        return StopResult(1, f"Daemon stopped but failed to clear metadata: {exc}")

    return StopResult(0, f"Stopped daemon pid {leader.pid}.")

