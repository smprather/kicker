from __future__ import annotations

import rich_click as click

from kicker.daemon_runtime import run_daemon


@click.command()
@click.option(
    "--log-format",
    type=click.Choice(["plain-text", "json"], case_sensitive=True),
    default="plain-text",
    show_default=True,
    help="Log format for daemon check/action logs.",
)
@click.option(
    "--poll-interval",
    type=float,
    default=None,
    help="Override global default polling interval in seconds.",
)
@click.option(
    "--lease-seconds",
    type=float,
    default=None,
    help="Leader lease duration in seconds.",
)
@click.option(
    "--lease-grace-seconds",
    type=float,
    default=10.0,
    show_default=True,
    help="Grace period after lease expiry before takeover is allowed.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress duplicate-instance style noise where possible.",
)
def main(
    log_format: str,
    poll_interval: float | None,
    lease_seconds: float | None,
    lease_grace_seconds: float,
    quiet: bool,
) -> None:
    """Run the kickerd daemon loop in the foreground."""
    result = run_daemon(
        quiet=quiet,
        log_format=log_format,
        default_poll_interval=poll_interval,
        lease_seconds=lease_seconds,
        lease_grace_seconds=lease_grace_seconds,
    )
    if result.message and not (quiet and result.exit_code == 0):
        click.echo(result.message)
    raise click.exceptions.Exit(result.exit_code)


if __name__ == "__main__":
    main()

