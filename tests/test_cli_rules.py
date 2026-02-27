from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from kicker.cli import main


def read_config(tmp_path: Path) -> dict[str, object]:
    config_path = tmp_path / ".config" / "kicker" / "config.yaml"
    return json.loads(config_path.read_text(encoding="utf-8"))


def test_rule_add_list_remove(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    added = runner.invoke(main, ["add", "run_this.sh", "--if", "check_this.sh"])
    assert added.exit_code == 0
    assert "Added rule #1" in added.output

    listed = runner.invoke(main, ["list"])
    assert listed.exit_code == 0
    assert "#1" in listed.output
    assert "run_this.sh" in listed.output

    payload = read_config(tmp_path)
    rules = payload["rules"]
    assert isinstance(rules, list)
    assert len(rules) == 1
    first = rules[0]
    assert isinstance(first, dict)
    assert first["trigger_mode"] == "on_zero"
    assert first["once"] is False

    removed = runner.invoke(main, ["remove", "1"])
    assert removed.exit_code == 0
    assert "Removed rule #1" in removed.output

    listed_after = runner.invoke(main, ["list"])
    assert listed_after.exit_code == 0
    assert "No rules configured." in listed_after.output


def test_add_if_code_requires_check(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, ["add", "action.sh", "--if-code", "5"])
    assert result.exit_code != 0
    assert "--check is required with --if-code" in result.output


def test_add_if_pass_alias_and_if_fail(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    add_pass = runner.invoke(main, ["add", "act-pass.sh", "--if-pass", "chk-pass.sh"])
    assert add_pass.exit_code == 0

    add_fail = runner.invoke(main, ["add", "act-fail.sh", "--if-fail", "chk-fail.sh"])
    assert add_fail.exit_code == 0

    payload = read_config(tmp_path)
    rules = payload["rules"]
    assert isinstance(rules, list)
    assert len(rules) == 2
    assert isinstance(rules[0], dict)
    assert isinstance(rules[1], dict)
    assert rules[0]["trigger_mode"] == "on_zero"
    assert rules[1]["trigger_mode"] == "on_nonzero"


def test_add_once_flag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, ["add", "act.sh", "--if", "chk.sh", "--once"])
    assert result.exit_code == 0

    payload = read_config(tmp_path)
    rules = payload["rules"]
    assert isinstance(rules, list)
    assert len(rules) == 1
    assert isinstance(rules[0], dict)
    assert rules[0]["once"] is True


def test_stats_lists_action_execution_count(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    add_one = runner.invoke(main, ["add", "a1.sh", "--if", "c1.sh"])
    add_two = runner.invoke(main, ["add", "a2.sh", "--if-fail", "c2.sh"])
    assert add_one.exit_code == 0
    assert add_two.exit_code == 0

    runtime_path = tmp_path / ".local" / "state" / "kicker" / "runtime_state.json"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        json.dumps(
            {
                "rules": {
                    "1": {"action_executions": 3},
                    "2": {"action_executions": 0},
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0
    assert "rule_id  action_executions  action_executions_24h" in result.output
    assert "1        3                  0" in result.output
    assert "2        0                  0" in result.output


def test_stats_last_24h_column(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    add_rule = runner.invoke(main, ["add", "a1.sh", "--if", "c1.sh"])
    assert add_rule.exit_code == 0

    now = 1_700_000_000.0
    runtime_path = tmp_path / ".local" / "state" / "kicker" / "runtime_state.json"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        json.dumps(
            {
                "rules": {
                    "1": {
                        "action_executions": 5,
                        "action_timestamps_24h": [now - 100.0, now - 3600.0, now - 90000.0],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as ctx:
        ctx.setattr("kicker.cli.time.time", lambda: now)
        result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0
    assert "1        5                  2" in result.output
