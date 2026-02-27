from __future__ import annotations

import rich_click as click

from kicker.daemon_control import stop_active_daemon


@click.group()
def main() -> None:
    """kicker command line interface."""


@main.group()
def daemon() -> None:
    """Manage the kickerd daemon."""


@daemon.command("stop")
@click.option(
    "--force",
    is_flag=True,
    help="Escalate to SIGKILL if the daemon does not stop after SIGTERM.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Return success when no daemon is running.",
)
def daemon_stop(force: bool, quiet: bool) -> None:
    """Stop the active daemon for this user's state directory."""
    result = stop_active_daemon(force=force, quiet=quiet)
    if result.message and not (quiet and result.exit_code == 0):
        click.echo(result.message)
    raise click.exceptions.Exit(result.exit_code)


if __name__ == "__main__":
    main()

