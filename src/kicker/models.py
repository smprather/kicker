from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


TriggerMode = Literal[
    "on_nonzero",
    "on_zero",
    "on_transition_fail_to_pass",
    "on_transition_pass_to_fail",
    "on_code_n",
]


VALID_TRIGGER_MODES: set[str] = {
    "on_nonzero",
    "on_zero",
    "on_transition_fail_to_pass",
    "on_transition_pass_to_fail",
    "on_code_n",
}


@dataclass(slots=True)
class Rule:
    id: int
    check: str
    action: str
    trigger_mode: TriggerMode
    once: bool = False
    trigger_code: int | None = None
    poll_interval_seconds: float | None = None
    rate_limit_count: int | None = None
    rate_limit_seconds: float | None = None
    timeout_seconds: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Rule":
        trigger_mode = str(payload["trigger_mode"])
        if trigger_mode not in VALID_TRIGGER_MODES:
            raise ValueError(f"Unknown trigger_mode: {trigger_mode}")

        trigger_code_raw = payload.get("trigger_code")
        trigger_code = int(trigger_code_raw) if trigger_code_raw is not None else None

        poll_raw = payload.get("poll_interval_seconds")
        timeout_raw = payload.get("timeout_seconds")
        rate_count_raw = payload.get("rate_limit_count")
        rate_seconds_raw = payload.get("rate_limit_seconds")

        rule = cls(
            id=int(payload["id"]),
            check=str(payload["check"]),
            action=str(payload["action"]),
            trigger_mode=trigger_mode,  # type: ignore[arg-type]
            once=bool(payload.get("once", False)),
            trigger_code=trigger_code,
            poll_interval_seconds=float(poll_raw) if poll_raw is not None else None,
            rate_limit_count=int(rate_count_raw) if rate_count_raw is not None else None,
            rate_limit_seconds=float(rate_seconds_raw)
            if rate_seconds_raw is not None
            else None,
            timeout_seconds=float(timeout_raw) if timeout_raw is not None else None,
        )
        rule.validate()
        return rule

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "check": self.check,
            "action": self.action,
            "trigger_mode": self.trigger_mode,
            "once": self.once,
            "trigger_code": self.trigger_code,
            "poll_interval_seconds": self.poll_interval_seconds,
            "rate_limit_count": self.rate_limit_count,
            "rate_limit_seconds": self.rate_limit_seconds,
            "timeout_seconds": self.timeout_seconds,
        }

    def validate(self) -> None:
        if self.id <= 0:
            raise ValueError("Rule id must be positive")
        if not self.check.strip():
            raise ValueError("Rule check command must not be empty")
        if not self.action.strip():
            raise ValueError("Rule action command must not be empty")
        if self.trigger_mode not in VALID_TRIGGER_MODES:
            raise ValueError(f"Unknown trigger mode: {self.trigger_mode}")
        if self.trigger_mode == "on_code_n" and self.trigger_code is None:
            raise ValueError("trigger_code is required for on_code_n")
        if self.trigger_mode != "on_code_n" and self.trigger_code is not None:
            raise ValueError("trigger_code only allowed for on_code_n")
        if self.poll_interval_seconds is not None and self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if (self.rate_limit_count is None) != (self.rate_limit_seconds is None):
            raise ValueError(
                "rate_limit_count and rate_limit_seconds must be set together"
            )
        if self.rate_limit_count is not None:
            if self.rate_limit_count <= 0:
                raise ValueError("rate_limit_count must be > 0")
            if self.rate_limit_seconds is None or self.rate_limit_seconds <= 0:
                raise ValueError("rate_limit_seconds must be > 0")


@dataclass(slots=True)
class RuleConfig:
    version: int = 1
    default_poll_interval_seconds: float = 60.0
    rules: list[Rule] | None = None

    @classmethod
    def empty(cls) -> "RuleConfig":
        return cls(version=1, default_poll_interval_seconds=60.0, rules=[])

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuleConfig":
        version = int(payload.get("version", 1))
        if version != 1:
            raise ValueError(f"Unsupported config version: {version}")

        global_payload = payload.get("global", {})
        if not isinstance(global_payload, dict):
            raise ValueError("'global' must be an object")

        default_poll_interval_seconds = float(
            global_payload.get("default_poll_interval_seconds", 60.0)
        )
        if default_poll_interval_seconds <= 0:
            raise ValueError("default_poll_interval_seconds must be > 0")

        rules_raw = payload.get("rules", [])
        if not isinstance(rules_raw, list):
            raise ValueError("'rules' must be an array")

        rules = [Rule.from_dict(item) for item in rules_raw]
        ids = [rule.id for rule in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Rule ids must be unique")

        return cls(
            version=version,
            default_poll_interval_seconds=default_poll_interval_seconds,
            rules=rules,
        )

    def to_dict(self) -> dict[str, Any]:
        rules = self.rules or []
        return {
            "version": self.version,
            "global": {
                "default_poll_interval_seconds": self.default_poll_interval_seconds,
            },
            "rules": [rule.to_dict() for rule in rules],
        }

    def next_rule_id(self) -> int:
        rules = self.rules or []
        if not rules:
            return 1
        return max(rule.id for rule in rules) + 1
