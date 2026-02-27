# kickit

`kickit` is a Linux automation tool in active bootstrap phase.

- `kickerd`: daemon that evaluates condition scripts and runs action scripts.
- `kicker`: CLI used to manage and control daemon behavior.

Architecture spec: [docs/architecture.md](docs/architecture.md)

## Install / Run

```bash
uv sync
uv run kicker --help
```

## Command Tree (Implemented)

| Level | Command | Description |
|---|---|---|
| Root | `kicker` | Main CLI entrypoint |
| Group | `kicker daemon` | Daemon lifecycle commands |
| Command | `kicker daemon stop` | Stop active daemon for current user's state directory |

## Complete CLI Reference

### Commands

| Command | Description | Exit Behavior |
|---|---|---|
| `kicker` | Root command group | Exits `0` on help/success |
| `kicker daemon` | Daemon command group | Exits `0` on help/success |
| `kicker daemon stop` | Stops active daemon using leader metadata | Exits non-zero on failure |

### Options

| Scope | Option | Type | Default | Description |
|---|---|---|---|---|
| `kicker` | `--help` | flag | `false` | Show root help and exit |
| `kicker daemon` | `--help` | flag | `false` | Show daemon group help and exit |
| `kicker daemon stop` | `--force` | flag | `false` | Escalate to `SIGKILL` if `SIGTERM` does not stop daemon |
| `kicker daemon stop` | `--quiet` | flag | `false` | Return success when no daemon is running |
| `kicker daemon stop` | `--help` | flag | `false` | Show command help and exit |

## `kicker daemon stop` Behavior

| Step | Behavior |
|---|---|
| Metadata lookup | Reads `~/.local/state/kicker/leader.json` |
| Host safety | Refuses stop if leader host differs from current host |
| Graceful stop | Sends `SIGTERM` first and waits briefly |
| Forced stop | With `--force`, escalates to `SIGKILL` if still alive |
| Stale metadata | Clears stale leader file when PID is not running |
| No daemon | Returns non-zero unless `--quiet` is set |

## Planned (Not Yet Implemented)

Planned rule-management commands from the architecture doc:
- `kicker add ...`
- `kicker list`
- `kicker remove ...`

## Development Notes

- Python `>=3.14`
- Tooling: `uv`, `ruff`, `ty`, `pytest`, Rich Click
- Contributor/agent guidance: [AGENTS.md](AGENTS.md)
