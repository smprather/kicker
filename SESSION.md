# Session Notes

## Status
- Repository is on `main` with recent pushes completed.
- Latest known test status: `21 passed` via `uv run pytest -q`.

## Latest Completed Work
- Added `kicker stats` with per-rule totals and last-24h execution counts.
- Added `--once` on `kicker add` to auto-delete a rule after first action execution.
- Updated condition semantics:
  - `--if` and `--if-pass` trigger on check exit code `0`.
  - `--if-fail` triggers on non-zero check exit code.
- Added `--verbose` to `kickerd` and ensured option parity with `kicker daemon run`.
- Added tests for daemon option parity and `kickerd` CLI behavior.

## Documentation State
- `README.md` includes complete command and option documentation in tabular format.
- User-facing docs now refer directly to `kicker` / `kickerd` (not `uv run ...`).
- Architecture details live in `docs/architecture.md`.

## Suggested Next Steps
1. Run full test suite after any further CLI/daemon changes.
2. Consider adding integration tests for end-to-end daemon lifecycle (`run` -> `status` -> `stop`).
3. If needed, expand stats to include failure counts for checks/actions.
