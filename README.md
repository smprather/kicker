# kickit

`kickit` is a planned Linux automation tool built around user scripts.

- `kickerd`: a daemon that periodically runs condition-check scripts.
- `kicker`: a CLI for defining and managing trigger/action rules.

When a condition matches, `kickerd` runs a user-defined action script.

## Project Status

This repository is currently in architecture/scaffolding phase. Core implementation files have not been added yet.

## Planned Behavior

- Evaluate user-provided check scripts and react to exit codes/state transitions.
- Support trigger modes such as:
  - non-zero / zero result matching
  - transition matching (fail -> pass, pass -> fail)
  - specific return code matching
- Keep daemon state under `~/.local/state/kicker/`.
- Store user config and scripts under `~/.config/kicker/`.

Reference design: [docs/architecture.md](docs/architecture.md)

## Planned CLI Shape

```bash
kicker add run_this.sh --if check_this.sh
kicker add run_this.sh --if-fail-to-pass check_if_file_exists.sh
kicker list
kicker remove 3
```

## Implemented CLI Today

The daemon stop path is implemented:

```bash
uv run kicker daemon stop
uv run kicker daemon stop --force
uv run kicker daemon stop --quiet
```

Behavior:
- Reads daemon metadata from `~/.local/state/kicker/leader.json`.
- Sends `SIGTERM` first; `--force` escalates to `SIGKILL` if needed.
- Returns non-zero when no daemon is running unless `--quiet` is set.

## Logging Expectations

`kickerd` is expected to log check/action stdout, stderr, and return codes to:

- `~/.local/state/kicker/kicker_checks.log`
- `~/.local/state/kicker/kicker_actions.log`

## Development Notes

- Intended stack: Python `>=3.14`, `uv`, `ruff`, `ty`, `pytest`, Rich Click.
- Contributor and workflow guidance: [AGENTS.md](AGENTS.md)
