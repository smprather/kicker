from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from kicker.runtime_state import RuntimeState

MAX_LOG_BYTES = 10 * 1024 * 1024
TRIM_COOLDOWN_SECONDS = 3600.0
TRIM_TARGET_BYTES = 8 * 1024 * 1024


def _iso_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


class KickerLogger:
    def __init__(self, *, fmt: str, checks_log: Path, actions_log: Path) -> None:
        if fmt not in {"plain-text", "json"}:
            raise ValueError("log format must be 'plain-text' or 'json'")
        self.fmt = fmt
        self.checks_log = checks_log
        self.actions_log = actions_log

    def log_check(
        self,
        *,
        now: float,
        script_name: str,
        command: str,
        stdout: str,
        stderr: str,
        return_code: int,
        state: RuntimeState,
    ) -> None:
        self._append(
            path=self.checks_log,
            trim_key="checks",
            phase="check",
            now=now,
            script_name=script_name,
            command=command,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            state=state,
        )

    def log_action(
        self,
        *,
        now: float,
        script_name: str,
        command: str,
        stdout: str,
        stderr: str,
        return_code: int,
        state: RuntimeState,
    ) -> None:
        self._append(
            path=self.actions_log,
            trim_key="actions",
            phase="action",
            now=now,
            script_name=script_name,
            command=command,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            state=state,
        )

    def _append(
        self,
        *,
        path: Path,
        trim_key: str,
        phase: str,
        now: float,
        script_name: str,
        command: str,
        stdout: str,
        stderr: str,
        return_code: int,
        state: RuntimeState,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._trim_if_needed(path=path, trim_key=trim_key, now=now, state=state)

        if self.fmt == "plain-text":
            lines = self._format_plain(
                now=now,
                phase=phase,
                script_name=script_name,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
            )
            with path.open("a", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(line + "\n")
            return

        records = self._format_json(
            now=now,
            phase=phase,
            script_name=script_name,
            command=command,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
        )
        with path.open("a", encoding="utf-8") as handle:
            for item in records:
                handle.write(json.dumps(item) + "\n")

    def _format_plain(
        self,
        *,
        now: float,
        phase: str,
        script_name: str,
        stdout: str,
        stderr: str,
        return_code: int,
    ) -> list[str]:
        ts = _iso_timestamp(now)
        prefix = f"{ts} [{script_name}] [{phase}]"
        lines: list[str] = []
        for line in stdout.splitlines() or [""]:
            if line:
                lines.append(f"{prefix} [stdout] {line}")
        for line in stderr.splitlines() or [""]:
            if line:
                lines.append(f"{prefix} [stderr] {line}")
        lines.append(f"{prefix} [return_code] {return_code}")
        return lines

    def _format_json(
        self,
        *,
        now: float,
        phase: str,
        script_name: str,
        command: str,
        stdout: str,
        stderr: str,
        return_code: int,
    ) -> list[dict[str, object]]:
        ts = _iso_timestamp(now)
        records: list[dict[str, object]] = []
        for line in stdout.splitlines():
            records.append(
                {
                    "timestamp": ts,
                    "script": script_name,
                    "phase": phase,
                    "stream": "stdout",
                    "message": line,
                    "command": command,
                }
            )
        for line in stderr.splitlines():
            records.append(
                {
                    "timestamp": ts,
                    "script": script_name,
                    "phase": phase,
                    "stream": "stderr",
                    "message": line,
                    "command": command,
                }
            )
        records.append(
            {
                "timestamp": ts,
                "script": script_name,
                "phase": phase,
                "stream": "return_code",
                "value": return_code,
                "command": command,
            }
        )
        return records

    def _trim_if_needed(
        self,
        *,
        path: Path,
        trim_key: str,
        now: float,
        state: RuntimeState,
    ) -> None:
        if not path.exists():
            return
        if path.stat().st_size <= MAX_LOG_BYTES:
            return

        last_trim = state.log_trim_last_at.get(trim_key, 0.0)
        if (now - last_trim) < TRIM_COOLDOWN_SECONDS:
            return

        content = path.read_bytes()
        if len(content) > TRIM_TARGET_BYTES:
            content = content[-TRIM_TARGET_BYTES:]
        path.write_bytes(content)
        state.log_trim_last_at[trim_key] = now

