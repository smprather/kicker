# Repository Guidelines

## Project Structure & Module Organization

This repository hosts a Python CLI (`kicker`) and daemon (`kickerd`) for script-based condition monitoring and actions.

- `src/kicker/`: application code (CLI, daemon loop, trigger evaluation, logging).
- `tests/`: pytest suite mirroring `src/` modules.
- `docs/`: design notes and behavior decisions.
- `examples/`: sample condition/action scripts and CLI usage.

Do not commit runtime data. User config and state live outside the repo:

- `~/.config/kicker/` (config and user scripts)
- `~/.local/state/kicker/` (PID/state files and logs)

## Build, Test, and Development Commands

Use `uv` for environment and command execution.

- `uv sync`: install/update dependencies.
- `uv run kicker --help`: validate CLI wiring locally.
- `uv run ruff check .`: run lint checks.
- `uv run ruff format .`: apply formatting.
- `uv run pytest -q`: run tests.

If/when type checking is enabled with `ty`, run it via `uv run ty check`.

## Coding Style & Naming Conventions

- Target Python `>=3.14`.
- Use 4-space indentation and explicit type hints on public APIs.
- Prefer `pathlib.Path` over `os.path`.
- Naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`.
- Keep CLI behavior deterministic: explicit exit codes and stable output for automation.

## Testing Guidelines

- Framework: `pytest`; test files use `test_*.py`.
- Mirror source paths (for example, `src/kicker/daemon.py` -> `tests/test_daemon.py`).
- Add tests for new trigger logic, return-code transitions, and logging behavior.
- For bug fixes, include a regression test that fails before the fix.

## Commit & Pull Request Guidelines

Use Conventional Commits:

- `feat(daemon): add state transition trigger`
- `fix(cli): handle missing config file`
- `test(logging): cover hourly log trim`

PRs should include:

- Clear summary and rationale.
- Linked issue/task ID when available.
- Test evidence (`uv run pytest -q` output summary).
- Example CLI usage or log snippet when behavior changes.
