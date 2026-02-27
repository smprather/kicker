from __future__ import annotations

from click.testing import CliRunner

from kicker.daemon_runtime import DaemonRunResult
from kicker.kickerd import main


def test_kickerd_help_shows_verbose_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--verbose" in result.output


def test_kickerd_verbose_passes_status_fn(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_daemon(**kwargs):
        captured.update(kwargs)
        return DaemonRunResult(0, "ok")

    monkeypatch.setattr("kicker.kickerd.run_daemon", fake_run_daemon)
    runner = CliRunner()
    result = runner.invoke(main, ["--verbose"])
    assert result.exit_code == 0
    assert callable(captured.get("status_fn"))

