# Kicker Architecture

## Overview

Kicker is a Linux automation tool with:
- `kickerd`: daemon that evaluates condition scripts and runs action scripts.
- `kicker`: CLI that manages persisted trigger/action rules.

## Scope and Non-Goals

In scope:
- Script-based condition checks.
- Rule-based action execution.
- Per-filespace daemon singleton behavior.
- Persistent logs and rule configuration.

Out of scope (for first version):
- Network coordination between hosts.
- GUI or web interface.

## Runtime Model

`kickerd` MUST run once per NFS filespace (effectively once per home directory).

State directory:
- `~/.local/state/kicker/`

Startup contract:
1. Read active daemon marker (`hostname:pid`).
2. Validate marker points to a live `kickerd` process.
3. If valid daemon exists, exit (unless `--quiet`).
4. If stale, replace marker and continue.

No network handshake/ports are required for singleton detection.

Polling behavior:
- Global default polling interval MUST be `60s`.
- Each rule MAY define its own polling interval override.
- If no override is set, the rule uses the global default.
- Scheduler model MUST be per-rule pseudo-loops: each rule is evaluated independently as if no other rules exist.
- Implementation detail may use a central event loop, but observed behavior MUST match independent rule loops.
- Daemon runtime MUST remain single-threaded with one global event loop.

Leader election and cross-process safety:
- In-process locking is not required beyond the single-threaded event loop.
- A cross-process leader claim MUST still be used to prevent startup races on shared NFS homes.
- Leader claim MUST be implemented using an NFS-safe atomic primitive (for example, lock directory creation).
- Leader metadata MUST include at least `hostname`, `pid`, `start_time`, and `lease_expires_at`.
- Leader lease MUST be periodically refreshed by the active daemon.
- A new daemon MAY take over only when the prior lease is expired beyond a configured grace period.

## Rules and Trigger Semantics

Each rule has:
- A check script.
- An action script.
- A trigger mode.
- Optional one-shot execution mode (`once`) that auto-deletes the rule after the first action execution.

Supported trigger modes:
- `on_nonzero`: fire when check exits non-zero.
- `on_zero`: fire when check exits zero.
- `on_transition_fail_to_pass`: previous non-zero, current zero.
- `on_transition_pass_to_fail`: previous zero, current non-zero.
- `on_code_n`: fire when check exits exactly `N`.

Each check execution SHOULD persist prior and current exit code per rule.

Action rate limiting:
- Rate limiting MUST be configurable per rule.
- Rate limit units MUST be `number/seconds` (for example, `1/60`, `5/300`).
- Default rate limit MUST be one action per polling interval for that rule.

Execution timeouts:
- Check and action execution timeouts MUST be configurable per rule.
- If not explicitly set, timeout default MUST be `poll_interval * 0.9` for that rule.

## Configuration and Paths

- User scripts: `~/.config/kicker/scripts/`
- Config/rules: `~/.config/kicker/config.yaml`

YAML is preferred for v1; switching formats is acceptable if human readability is preserved.

Execution directory behavior:
- Default working directory for check/action script execution MUST be the invoking user's home directory.
- v1 SHOULD NOT support per-rule working-directory overrides.
- Future versions MAY add:
  - a daemon-wide default working directory at `kickerd` launch time, and/or
  - per-rule working-directory overrides.

## CLI (Planned)

- `kicker add run_this.sh --if check_this.sh` (check returns zero / pass)
- `kicker add run_this.sh --if-fail check_this.sh` (check returns non-zero / fail)
- `kicker add run_this.sh --if-fail-to-pass check_if_file_exists.sh`
- `kicker add run_once.sh --if-fail check_this.sh --once`
- `kicker list`
- `kicker stats`
- `kicker remove N`
- `kicker daemon stop [--force] [--quiet]`

`kicker list` SHOULD show stable rule IDs and the original trigger definition.
`kicker daemon stop` SHOULD:
- target only the active leader daemon from lease metadata,
- send `SIGTERM` first and wait briefly,
- optionally escalate with `--force` (for example, `SIGKILL`) if still running,
- return non-zero when no daemon is running unless `--quiet` is set.

## Logging Contract

Log outputs MUST include check/action stdout, stderr, and return codes.
Log format MUST be configurable via `kickerd` command-line option.
Supported formats MUST be:
- `plain-text`
- `json`
`kickerd` SHOULD expose this as a flag similar to `--log-format {plain-text,json}`.

Log files:
- `~/.local/state/kicker/kicker_checks.log`
- `~/.local/state/kicker/kicker_actions.log`

Rotation/trimming:
- Max size 10 MB per log.
- Trim no more than once per hour.
- Each line MUST include timestamp and script name.

## Tech Stack

- Python `>= 3.14`
- `uv` for dependency and command management
- `ruff` and `ty` for lint/type checks
- `pytest` for tests
- Rich Click for CLI UX
- Prefer `pathlib.Path` over `os.path`

## Acceptance Criteria for v1

- Daemon singleton behavior works across hosts sharing the same home directory.
- `kicker daemon stop` can gracefully stop the active daemon and supports forced termination.
- Rules persist across restarts and are editable via `kicker`.
- Trigger modes above execute correctly with tests for transitions.
- Logs contain required fields and enforce size/trim limits.
