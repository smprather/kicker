from __future__ import annotations

import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from kicker.config_store import ConfigStore
from kicker.daemon_control import claim_leader, refresh_leader_lease, release_leader_claim
from kicker.logging_backend import KickerLogger
from kicker.models import Rule
from kicker.paths import actions_log_file, checks_log_file, scripts_dir
from kicker.rule_logic import (
    effective_poll_interval,
    effective_rate_limit,
    effective_timeout,
    trigger_matches,
)
from kicker.runtime_state import RuntimeState, RuntimeStateStore


@dataclass(slots=True)
class CommandResult:
    return_code: int
    stdout: str
    stderr: str


@dataclass(slots=True)
class DaemonRunResult:
    exit_code: int
    message: str


class _StopFlag:
    def __init__(self) -> None:
        self.value = False

    def set(self, _signum: int, _frame: object) -> None:
        self.value = True


def _resolve_command(command: str, scripts_root: Path) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    if not parts:
        return command

    first = parts[0]
    if "/" in first:
        return command
    candidate = scripts_root / first
    if candidate.exists():
        parts[0] = str(candidate)
        return shlex.join(parts)
    return command


def _script_name(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    if not parts:
        return command
    return Path(parts[0]).name


def _execute_command(
    *,
    command: str,
    timeout_seconds: float,
    cwd: Path,
) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nCommand timed out after {timeout_seconds:.2f}s."
        return CommandResult(return_code=124, stdout=stdout, stderr=stderr)

    return CommandResult(
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _should_allow_action(
    *,
    rule: Rule,
    runtime_state: RuntimeState,
    now: float,
    default_poll_interval: float,
) -> bool:
    rule_state = runtime_state.get_rule(rule.id)
    count, window_seconds = effective_rate_limit(rule, default_poll_interval)

    kept = [
        timestamp
        for timestamp in rule_state.action_timestamps
        if (now - timestamp) < window_seconds
    ]
    rule_state.action_timestamps = kept
    return len(kept) < count


def _record_action_execution(
    *,
    rule: Rule,
    runtime_state: RuntimeState,
    now: float,
) -> None:
    rule_state = runtime_state.get_rule(rule.id)
    rule_state.action_timestamps.append(now)


def _run_rule_once(
    *,
    rule: Rule,
    runtime_state: RuntimeState,
    logger: KickerLogger,
    scripts_root: Path,
    home_dir: Path,
    now: float,
    default_poll_interval: float,
) -> None:
    rule_state = runtime_state.get_rule(rule.id)
    previous_rc = rule_state.last_check_exit

    check_timeout = effective_timeout(rule, default_poll_interval)
    check_command = _resolve_command(rule.check, scripts_root)
    check_result = _execute_command(
        command=check_command,
        timeout_seconds=check_timeout,
        cwd=home_dir,
    )
    logger.log_check(
        now=now,
        script_name=_script_name(check_command),
        command=check_command,
        stdout=check_result.stdout,
        stderr=check_result.stderr,
        return_code=check_result.return_code,
        state=runtime_state,
    )

    current_rc = check_result.return_code
    rule_state.last_check_exit = current_rc
    rule_state.last_check_at = now

    if not trigger_matches(rule, previous_rc, current_rc):
        return

    if not _should_allow_action(
        rule=rule,
        runtime_state=runtime_state,
        now=now,
        default_poll_interval=default_poll_interval,
    ):
        return

    action_timeout = effective_timeout(rule, default_poll_interval)
    action_command = _resolve_command(rule.action, scripts_root)
    action_result = _execute_command(
        command=action_command,
        timeout_seconds=action_timeout,
        cwd=home_dir,
    )
    _record_action_execution(rule=rule, runtime_state=runtime_state, now=now)
    logger.log_action(
        now=now,
        script_name=_script_name(action_command),
        command=action_command,
        stdout=action_result.stdout,
        stderr=action_result.stderr,
        return_code=action_result.return_code,
        state=runtime_state,
    )


def run_daemon(
    *,
    quiet: bool,
    log_format: str,
    default_poll_interval: float | None = None,
    lease_seconds: float | None = None,
    lease_grace_seconds: float = 10.0,
    config_store: ConfigStore | None = None,
    runtime_state_store: RuntimeStateStore | None = None,
    state_dir_path: Path | None = None,
    checks_log_path: Path | None = None,
    actions_log_path: Path | None = None,
    scripts_root: Path | None = None,
    home_dir: Path | None = None,
    now_fn: Callable[[], float] = time.time,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_rule_executions: int | None = None,
) -> DaemonRunResult:
    store = config_store or ConfigStore()
    config = store.load()

    effective_default_poll = (
        default_poll_interval
        if default_poll_interval is not None
        else config.default_poll_interval_seconds
    )
    if effective_default_poll <= 0:
        return DaemonRunResult(1, "default polling interval must be > 0")

    effective_lease_seconds = (
        lease_seconds if lease_seconds is not None else max(30.0, effective_default_poll * 2)
    )
    claim = claim_leader(
        lease_seconds=effective_lease_seconds,
        grace_seconds=lease_grace_seconds,
        quiet=quiet,
        state_dir=state_dir_path,
        now_fn=now_fn,
    )
    if not claim.claimed:
        return DaemonRunResult(1, claim.message)

    state_store = runtime_state_store
    if state_store is None:
        runtime_state_path = (
            state_dir_path / "runtime_state.json"
            if state_dir_path is not None
            else None
        )
        state_store = RuntimeStateStore(runtime_state_path)
    runtime_state = state_store.load()

    rules = sorted(config.rules or [], key=lambda item: item.id)
    rule_next_due = {rule.id: now_fn() for rule in rules}
    checks_path = checks_log_path
    if checks_path is None:
        checks_path = (
            state_dir_path / "kicker_checks.log"
            if state_dir_path is not None
            else checks_log_file()
        )
    actions_path = actions_log_path
    if actions_path is None:
        actions_path = (
            state_dir_path / "kicker_actions.log"
            if state_dir_path is not None
            else actions_log_file()
        )
    logger = KickerLogger(
        fmt=log_format,
        checks_log=checks_path,
        actions_log=actions_path,
    )
    command_cwd = home_dir or Path.home()
    scripts_root_path = scripts_root or scripts_dir()

    stop_flag = _StopFlag()
    previous_int = signal.getsignal(signal.SIGINT)
    previous_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, stop_flag.set)
    signal.signal(signal.SIGTERM, stop_flag.set)

    executions = 0
    next_lease_refresh = now_fn() + max(1.0, effective_lease_seconds / 2.0)
    try:
        while not stop_flag.value:
            now = now_fn()
            if now >= next_lease_refresh:
                refresh_leader_lease(
                    lease_seconds=effective_lease_seconds,
                    now_fn=now_fn,
                    state_dir=state_dir_path,
                )
                next_lease_refresh = now + max(1.0, effective_lease_seconds / 2.0)

            due_rules = [rule for rule in rules if rule_next_due.get(rule.id, now) <= now]
            if due_rules:
                for rule in due_rules:
                    _run_rule_once(
                        rule=rule,
                        runtime_state=runtime_state,
                        logger=logger,
                        scripts_root=scripts_root_path,
                        home_dir=command_cwd,
                        now=now,
                        default_poll_interval=effective_default_poll,
                    )
                    rule_next_due[rule.id] = now + effective_poll_interval(
                        rule, effective_default_poll
                    )
                    executions += 1
                    if (
                        max_rule_executions is not None
                        and executions >= max_rule_executions
                    ):
                        stop_flag.value = True
                        break
                state_store.save(runtime_state)
                continue

            next_due = min(rule_next_due.values(), default=now + effective_default_poll)
            sleep_for = min(max(0.05, next_due - now), 0.5)
            sleep_fn(sleep_for)
    finally:
        state_store.save(runtime_state)
        release_leader_claim(state_dir_path)
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)

    return DaemonRunResult(0, "Daemon stopped.")
