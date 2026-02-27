from __future__ import annotations

import os
import socket

import rich_click as click

from kicker.config_store import ConfigStore
from kicker.daemon_control import load_leader_info, stop_active_daemon
from kicker.daemon_runtime import run_daemon
from kicker.models import Rule
from kicker.rule_logic import parse_rate_limit


def _resolve_trigger_definition(
    *,
    if_nonzero: str | None,
    if_zero: str | None,
    if_fail_to_pass: str | None,
    if_pass_to_fail: str | None,
    if_code: int | None,
    check: str | None,
) -> tuple[str, str, int | None]:
    selected = [
        ("on_nonzero", if_nonzero, None),
        ("on_zero", if_zero, None),
        ("on_transition_fail_to_pass", if_fail_to_pass, None),
        ("on_transition_pass_to_fail", if_pass_to_fail, None),
    ]
    chosen = [(mode, cmd, code) for mode, cmd, code in selected if cmd is not None]

    if if_code is not None:
        if check is None:
            raise click.BadParameter("--check is required with --if-code")
        chosen.append(("on_code_n", check, if_code))

    if len(chosen) != 1:
        raise click.BadParameter(
            "Specify exactly one trigger mode: --if / --if-zero / "
            "--if-fail-to-pass / --if-pass-to-fail / --if-code + --check"
        )

    mode, command, code = chosen[0]
    if command is None:
        raise click.BadParameter("check command cannot be empty")
    return mode, command, code


def _format_rule_line(rule: Rule, default_poll_interval: float) -> str:
    poll = rule.poll_interval_seconds or default_poll_interval
    if rule.rate_limit_count is not None and rule.rate_limit_seconds is not None:
        rate = f"{rule.rate_limit_count}/{rule.rate_limit_seconds:g}"
    else:
        rate = f"1/{poll:g}"

    timeout = rule.timeout_seconds if rule.timeout_seconds is not None else poll * 0.9

    trigger_text = rule.trigger_mode
    if rule.trigger_mode == "on_code_n" and rule.trigger_code is not None:
        trigger_text = f"on_code_n({rule.trigger_code})"

    return (
        f"#{rule.id} trigger={trigger_text} interval={poll:g}s rate={rate} "
        f"timeout={timeout:g}s check={rule.check!r} action={rule.action!r}"
    )


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@click.group()
def main() -> None:
    """kicker command line interface."""


@main.command("add")
@click.argument("action")
@click.option("if_nonzero", "--if", help="Run action when check returns non-zero.")
@click.option("if_zero", "--if-zero", help="Run action when check returns zero.")
@click.option(
    "if_fail_to_pass",
    "--if-fail-to-pass",
    help="Run action when check transitions non-zero -> zero.",
)
@click.option(
    "if_pass_to_fail",
    "--if-pass-to-fail",
    help="Run action when check transitions zero -> non-zero.",
)
@click.option("if_code", "--if-code", type=int, help="Run action when check returns this code.")
@click.option("check", "--check", help="Check command (required with --if-code).")
@click.option(
    "interval",
    "--interval",
    type=float,
    default=None,
    help="Per-rule polling interval in seconds.",
)
@click.option(
    "rate_limit",
    "--rate-limit",
    default=None,
    help="Per-rule action rate limit in number/seconds format (example: 2/60).",
)
@click.option(
    "timeout",
    "--timeout",
    type=float,
    default=None,
    help="Per-rule check/action timeout in seconds.",
)
def add_rule_command(
    action: str,
    if_nonzero: str | None,
    if_zero: str | None,
    if_fail_to_pass: str | None,
    if_pass_to_fail: str | None,
    if_code: int | None,
    check: str | None,
    interval: float | None,
    rate_limit: str | None,
    timeout: float | None,
) -> None:
    """Add a trigger/action rule."""
    mode, check_command, trigger_code = _resolve_trigger_definition(
        if_nonzero=if_nonzero,
        if_zero=if_zero,
        if_fail_to_pass=if_fail_to_pass,
        if_pass_to_fail=if_pass_to_fail,
        if_code=if_code,
        check=check,
    )

    if interval is not None and interval <= 0:
        raise click.BadParameter("--interval must be > 0")
    if timeout is not None and timeout <= 0:
        raise click.BadParameter("--timeout must be > 0")

    rate_count: int | None = None
    rate_seconds: float | None = None
    if rate_limit is not None:
        try:
            rate_count, rate_seconds = parse_rate_limit(rate_limit)
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

    store = ConfigStore()
    config = store.load()
    rule = Rule(
        id=config.next_rule_id(),
        check=check_command,
        action=action,
        trigger_mode=mode,  # type: ignore[arg-type]
        trigger_code=trigger_code,
        poll_interval_seconds=interval,
        rate_limit_count=rate_count,
        rate_limit_seconds=rate_seconds,
        timeout_seconds=timeout,
    )
    rule.validate()

    rules = config.rules or []
    rules.append(rule)
    config.rules = sorted(rules, key=lambda item: item.id)
    store.save(config)
    click.echo(f"Added rule #{rule.id}")


@main.command("list")
def list_rules_command() -> None:
    """List configured rules."""
    store = ConfigStore()
    config = store.load()
    rules = sorted(config.rules or [], key=lambda item: item.id)
    if not rules:
        click.echo("No rules configured.")
        return

    click.echo(f"default_poll_interval={config.default_poll_interval_seconds:g}s")
    for rule in rules:
        click.echo(_format_rule_line(rule, config.default_poll_interval_seconds))


@main.command("remove")
@click.argument("rule_id", type=int)
def remove_rule_command(rule_id: int) -> None:
    """Remove a rule by id."""
    store = ConfigStore()
    removed = store.remove_rule(rule_id)
    if not removed:
        raise click.ClickException(f"Rule #{rule_id} does not exist")
    click.echo(f"Removed rule #{rule_id}")


@main.group()
def daemon() -> None:
    """Manage the kickerd daemon."""


@daemon.command("run")
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
@click.option("--quiet", is_flag=True, help="Suppress non-essential messages.")
def daemon_run(
    log_format: str,
    poll_interval: float | None,
    lease_seconds: float | None,
    lease_grace_seconds: float,
    quiet: bool,
) -> None:
    """Run the daemon loop in the foreground."""
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


@daemon.command("status")
def daemon_status() -> None:
    """Show daemon leader metadata and liveness."""
    leader = load_leader_info()
    if leader is None:
        click.echo("No daemon metadata found.")
        raise click.exceptions.Exit(1)

    current_host = socket.gethostname()
    local = leader.hostname == current_host
    alive = _is_pid_alive(leader.pid) if local else False
    click.echo(f"host={leader.hostname} pid={leader.pid} local={str(local).lower()} alive={str(alive).lower()}")
    if leader.lease_expires_at is not None:
        click.echo(f"lease_expires_at={leader.lease_expires_at:.3f}")

    raise click.exceptions.Exit(0 if (local and alive) else 1)


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
