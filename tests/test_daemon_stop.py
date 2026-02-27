from __future__ import annotations

import json
import signal
from pathlib import Path

from kicker.daemon_control import stop_active_daemon


class FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def time(self) -> float:
        return self._now

    def sleep(self, amount: float) -> None:
        self._now += amount


def write_leader(state_dir: Path, *, hostname: str, pid: int) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    leader_file = state_dir / "leader.json"
    leader_file.write_text(
        json.dumps(
            {
                "hostname": hostname,
                "pid": pid,
                "start_time": 1.0,
                "lease_expires_at": 9999999999.0,
            }
        ),
        encoding="utf-8",
    )


def test_stop_no_daemon_without_quiet(tmp_path: Path) -> None:
    result = stop_active_daemon(force=False, quiet=False, state_dir=tmp_path)
    assert result.exit_code == 1
    assert "No daemon is running." in result.message


def test_stop_no_daemon_with_quiet(tmp_path: Path) -> None:
    result = stop_active_daemon(force=False, quiet=True, state_dir=tmp_path)
    assert result.exit_code == 0


def test_stop_refuses_remote_host(tmp_path: Path) -> None:
    write_leader(tmp_path, hostname="other-host", pid=1234)
    result = stop_active_daemon(
        force=False,
        quiet=False,
        state_dir=tmp_path,
        host_fn=lambda: "local-host",
    )
    assert result.exit_code == 1
    assert "Active daemon is on host 'other-host'" in result.message


def test_stop_sends_sigterm_and_clears_metadata(tmp_path: Path) -> None:
    write_leader(tmp_path, hostname="local-host", pid=1234)
    proc_alive = {1234: True}
    sent_signals: list[int] = []

    def fake_kill(pid: int, sig: int) -> None:
        if sig == 0:
            if not proc_alive.get(pid, False):
                raise ProcessLookupError
            return
        sent_signals.append(sig)
        if sig == signal.SIGTERM:
            proc_alive[pid] = False

    result = stop_active_daemon(
        force=False,
        quiet=False,
        state_dir=tmp_path,
        host_fn=lambda: "local-host",
        kill_fn=fake_kill,
    )
    assert result.exit_code == 0
    assert sent_signals == [signal.SIGTERM]
    assert not (tmp_path / "leader.json").exists()


def test_stop_uses_force_when_needed(tmp_path: Path) -> None:
    write_leader(tmp_path, hostname="local-host", pid=1234)
    proc_alive = {1234: True}
    sent_signals: list[int] = []
    clock = FakeClock()

    def fake_kill(pid: int, sig: int) -> None:
        if sig == 0:
            if not proc_alive.get(pid, False):
                raise ProcessLookupError
            return
        sent_signals.append(sig)
        if sig == signal.SIGKILL:
            proc_alive[pid] = False

    result = stop_active_daemon(
        force=True,
        quiet=False,
        state_dir=tmp_path,
        host_fn=lambda: "local-host",
        kill_fn=fake_kill,
        wait_seconds=0.3,
        poll_seconds=0.1,
        now_fn=clock.time,
        sleep_fn=clock.sleep,
    )
    assert result.exit_code == 0
    assert sent_signals[0] == signal.SIGTERM
    assert sent_signals[-1] == signal.SIGKILL
    assert not (tmp_path / "leader.json").exists()


def test_stop_without_force_times_out(tmp_path: Path) -> None:
    write_leader(tmp_path, hostname="local-host", pid=1234)
    proc_alive = {1234: True}
    clock = FakeClock()

    def fake_kill(pid: int, sig: int) -> None:
        if sig == 0:
            if not proc_alive.get(pid, False):
                raise ProcessLookupError
            return
        # Ignore SIGTERM; process stays alive.

    result = stop_active_daemon(
        force=False,
        quiet=False,
        state_dir=tmp_path,
        host_fn=lambda: "local-host",
        kill_fn=fake_kill,
        wait_seconds=0.3,
        poll_seconds=0.1,
        now_fn=clock.time,
        sleep_fn=clock.sleep,
    )
    assert result.exit_code == 1
    assert (tmp_path / "leader.json").exists()

