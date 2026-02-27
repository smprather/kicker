from __future__ import annotations

import re

from click.testing import CliRunner

from kicker.cli import main as kicker_main
from kicker.kickerd import main as kickerd_main


def _extract_long_options(help_text: str) -> set[str]:
    return set(re.findall(r"--[a-z][a-z-]*", help_text))


def test_kicker_daemon_run_and_kickerd_options_are_identical() -> None:
    runner = CliRunner()

    kicker_help = runner.invoke(kicker_main, ["daemon", "run", "--help"])
    kickerd_help = runner.invoke(kickerd_main, ["--help"])

    assert kicker_help.exit_code == 0
    assert kickerd_help.exit_code == 0

    kicker_opts = _extract_long_options(kicker_help.output)
    kickerd_opts = _extract_long_options(kickerd_help.output)
    assert kicker_opts == kickerd_opts

