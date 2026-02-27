from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kicker.paths import runtime_state_file


@dataclass(slots=True)
class RuleRuntimeState:
    last_check_exit: int | None = None
    last_check_at: float | None = None
    action_timestamps: list[float] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuleRuntimeState":
        last_check_exit_raw = payload.get("last_check_exit")
        last_check_at_raw = payload.get("last_check_at")
        action_timestamps_raw = payload.get("action_timestamps", [])

        if not isinstance(action_timestamps_raw, list):
            raise ValueError("action_timestamps must be a list")

        return cls(
            last_check_exit=(
                int(last_check_exit_raw) if last_check_exit_raw is not None else None
            ),
            last_check_at=float(last_check_at_raw) if last_check_at_raw is not None else None,
            action_timestamps=[float(item) for item in action_timestamps_raw],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_check_exit": self.last_check_exit,
            "last_check_at": self.last_check_at,
            "action_timestamps": self.action_timestamps,
        }


@dataclass(slots=True)
class RuntimeState:
    rules: dict[int, RuleRuntimeState] = field(default_factory=dict)
    log_trim_last_at: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeState":
        rules_payload = payload.get("rules", {})
        if not isinstance(rules_payload, dict):
            raise ValueError("rules state must be an object")

        parsed_rules: dict[int, RuleRuntimeState] = {}
        for key, value in rules_payload.items():
            if not isinstance(value, dict):
                raise ValueError("rule state entries must be objects")
            parsed_rules[int(key)] = RuleRuntimeState.from_dict(value)

        trim_payload = payload.get("log_trim_last_at", {})
        if not isinstance(trim_payload, dict):
            raise ValueError("log_trim_last_at must be an object")
        log_trim_last_at = {str(key): float(value) for key, value in trim_payload.items()}

        return cls(rules=parsed_rules, log_trim_last_at=log_trim_last_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules": {str(key): value.to_dict() for key, value in self.rules.items()},
            "log_trim_last_at": self.log_trim_last_at,
        }

    def get_rule(self, rule_id: int) -> RuleRuntimeState:
        state = self.rules.get(rule_id)
        if state is None:
            state = RuleRuntimeState()
            self.rules[rule_id] = state
        return state


class RuntimeStateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or runtime_state_file()

    def load(self) -> RuntimeState:
        if not self.path.exists():
            return RuntimeState()

        with self.path.open("r", encoding="utf-8") as handle:
            raw_text = handle.read().strip()

        if not raw_text:
            return RuntimeState()

        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError("Runtime state file must contain an object at root")
        return RuntimeState.from_dict(payload)

    def save(self, state: RuntimeState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")

