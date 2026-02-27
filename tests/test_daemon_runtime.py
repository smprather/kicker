from __future__ import annotations

from pathlib import Path

from kicker.config_store import ConfigStore
from kicker.daemon_runtime import run_daemon
from kicker.models import Rule, RuleConfig


class FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def time(self) -> float:
        return self._now

    def sleep(self, amount: float) -> None:
        self._now += amount


def write_script(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\nset -eu\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)


def test_daemon_runs_rules_with_rate_limit(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    scripts_root = tmp_path / "scripts"
    state_dir = tmp_path / "state"
    scripts_root.mkdir(parents=True, exist_ok=True)

    write_script(scripts_root / "check.sh", "exit 1")
    write_script(scripts_root / "action.sh", "echo hit >> action_hits.txt")

    config = RuleConfig(
        version=1,
        default_poll_interval_seconds=1.0,
        rules=[
            Rule(
                id=1,
                check="check.sh",
                action="action.sh",
                trigger_mode="on_nonzero",
                rate_limit_count=1,
                rate_limit_seconds=300.0,
            )
        ],
    )
    store = ConfigStore(config_path)
    store.save(config)

    clock = FakeClock()
    result = run_daemon(
        quiet=True,
        log_format="plain-text",
        config_store=store,
        state_dir_path=state_dir,
        scripts_root=scripts_root,
        home_dir=tmp_path,
        now_fn=clock.time,
        sleep_fn=clock.sleep,
        max_rule_executions=3,
    )
    assert result.exit_code == 0

    action_hits = (tmp_path / "action_hits.txt").read_text(encoding="utf-8").splitlines()
    assert action_hits == ["hit"]

    checks_log = (state_dir / "kicker_checks.log").read_text(encoding="utf-8")
    assert "[return_code] 1" in checks_log
    actions_log = (state_dir / "kicker_actions.log").read_text(encoding="utf-8")
    assert actions_log.count("[return_code] 0") == 1

    assert not (state_dir / "leader.json").exists()
    assert not (state_dir / "leader.lock").exists()


def test_daemon_once_rule_auto_deletes_after_action(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    scripts_root = tmp_path / "scripts"
    state_dir = tmp_path / "state"
    scripts_root.mkdir(parents=True, exist_ok=True)

    write_script(scripts_root / "check.sh", "exit 1")
    write_script(scripts_root / "action.sh", "echo once-hit >> action_hits_once.txt")

    config = RuleConfig(
        version=1,
        default_poll_interval_seconds=1.0,
        rules=[
            Rule(
                id=1,
                check="check.sh",
                action="action.sh",
                trigger_mode="on_nonzero",
                once=True,
            )
        ],
    )
    store = ConfigStore(config_path)
    store.save(config)

    clock = FakeClock()
    result = run_daemon(
        quiet=True,
        log_format="plain-text",
        config_store=store,
        state_dir_path=state_dir,
        scripts_root=scripts_root,
        home_dir=tmp_path,
        now_fn=clock.time,
        sleep_fn=clock.sleep,
        max_rule_executions=1,
    )
    assert result.exit_code == 0

    action_hits = (tmp_path / "action_hits_once.txt").read_text(encoding="utf-8").splitlines()
    assert action_hits == ["once-hit"]

    config_after = store.load()
    assert (config_after.rules or []) == []


def test_daemon_verbose_status_updates(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    scripts_root = tmp_path / "scripts"
    state_dir = tmp_path / "state"
    scripts_root.mkdir(parents=True, exist_ok=True)

    write_script(scripts_root / "check.sh", "exit 1")
    write_script(scripts_root / "action.sh", "exit 0")

    config = RuleConfig(
        version=1,
        default_poll_interval_seconds=1.0,
        rules=[
            Rule(
                id=1,
                check="check.sh",
                action="action.sh",
                trigger_mode="on_nonzero",
            )
        ],
    )
    store = ConfigStore(config_path)
    store.save(config)

    messages: list[str] = []
    clock = FakeClock()
    result = run_daemon(
        quiet=True,
        log_format="plain-text",
        config_store=store,
        state_dir_path=state_dir,
        scripts_root=scripts_root,
        home_dir=tmp_path,
        now_fn=clock.time,
        sleep_fn=clock.sleep,
        max_rule_executions=1,
        status_fn=messages.append,
    )
    assert result.exit_code == 0
    assert any("Daemon starting:" in message for message in messages)
    assert any("rule=#1 check_rc=1" in message for message in messages)
    assert any("rule=#1 action_executed=true action_rc=0" in message for message in messages)
