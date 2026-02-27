# kicker

`kicker` is a Linux automation tool for script-driven condition checks and actions.

- `kicker`: management CLI (rules + daemon control)
- `kickerd`: foreground daemon process

Architecture spec: [docs/architecture.md](docs/architecture.md)

## Install

```bash
uv sync
```

## Paths

| Purpose | Path |
|---|---|
| Rule config | `~/.config/kicker/config.yaml` |
| User scripts | `~/.config/kicker/scripts/` |
| Daemon state | `~/.local/state/kicker/` |
| Check log | `~/.local/state/kicker/kicker_checks.log` |
| Action log | `~/.local/state/kicker/kicker_actions.log` |

## Command Reference

### `kicker` Commands

| Command | Description |
|---|---|
| `kicker add ACTION ...` | Add a trigger/action rule |
| `kicker list` | List configured rules |
| `kicker stats` | Show per-rule action execution totals and last-24h counts |
| `kicker remove RULE_ID` | Remove a rule by id |
| `kicker daemon run ...` | Run daemon loop in foreground |
| `kicker daemon status` | Show leader metadata/liveness |
| `kicker daemon stop [--force] [--quiet]` | Stop active daemon |

### `kicker add` Trigger Options

Exactly one trigger mode is required.

| Option | Meaning |
|---|---|
| `--if CHECK` / `--if-pass CHECK` | Trigger when check exits zero (pass) |
| `--if-fail CHECK` | Trigger when check exits non-zero (fail) |
| `--if-fail-to-pass CHECK` | Trigger on non-zero -> zero transition |
| `--if-pass-to-fail CHECK` | Trigger on zero -> non-zero transition |
| `--if-code N --check CHECK` | Trigger when check exits exactly `N` |

### `kicker add` Optional Rule Controls

| Option | Format | Default |
|---|---|---|
| `--interval` | seconds (float) | global default (`60s`) |
| `--rate-limit` | `number/seconds` | `1/<poll_interval>` |
| `--timeout` | seconds (float) | `poll_interval * 0.9` |
| `--once` | flag | off |

### `kicker daemon run` Options

| Option | Default | Description |
|---|---|---|
| `--log-format [plain-text\|json]` | `plain-text` | Check/action log format |
| `--poll-interval FLOAT` | config default | Override global poll interval |
| `--lease-seconds FLOAT` | auto | Leader lease duration |
| `--lease-grace-seconds FLOAT` | `10.0` | Grace period for takeover |
| `--quiet` | off | Suppress duplicate-instance style noise where possible |
| `--verbose` | off | Print daemon lifecycle and per-rule execution debug updates to stdout |

### `kicker daemon stop` Options

| Option | Description |
|---|---|
| `--force` | Escalate to `SIGKILL` if `SIGTERM` does not stop daemon |
| `--quiet` | Return success if no daemon is running |

### `kickerd` (standalone daemon entrypoint)

`kickerd` supports the same daemon-run options, plus:

| Option | Description |
|---|---|
| `--verbose` | Print daemon lifecycle and per-rule execution debug updates to stdout |

```bash
kickerd --log-format plain-text --poll-interval 60 --verbose
```

## Examples

```bash
# Add a rule: run action when check passes
kicker add run_this.sh --if check_this.sh

# Add a rule: run action when check fails
kicker add run_this.sh --if-fail check_this.sh

# Add a transition rule with a custom interval/rate limit
kicker add run_this.sh --if-fail-to-pass check_this.sh --interval 30 --rate-limit 1/300

# Add a one-shot rule (auto-deletes after first action execution)
kicker add run_once.sh --if-fail check_this.sh --once

# Inspect rules
kicker list

# Show action execution stats
kicker stats

# Start daemon in foreground
kickerd --log-format json

# Stop daemon
kicker daemon stop --force
```

## Notes

- Check/action commands execute with working directory set to the invoking user's home directory.
- Config file is stored at `config.yaml` and currently written/read as JSON-compatible YAML.
- Leader metadata includes host/pid/lease fields and is used to enforce single active daemon per filespace.
