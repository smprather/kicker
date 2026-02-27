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

