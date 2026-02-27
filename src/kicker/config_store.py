from __future__ import annotations

import json
from pathlib import Path

from kicker.models import Rule, RuleConfig
from kicker.paths import config_file


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_file()

    def load(self) -> RuleConfig:
        if not self.path.exists():
            return RuleConfig.empty()

        with self.path.open("r", encoding="utf-8") as handle:
            raw_text = handle.read().strip()

        if not raw_text:
            return RuleConfig.empty()

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Config file must be valid JSON-compatible YAML for now."
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError("Config file must contain an object at root")
        return RuleConfig.from_dict(payload)

    def save(self, config: RuleConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = config.to_dict()
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def add_rule(self, rule: Rule) -> Rule:
        config = self.load()
        rules = config.rules or []
        if any(existing.id == rule.id for existing in rules):
            raise ValueError(f"Rule id already exists: {rule.id}")
        rules.append(rule)
        config.rules = sorted(rules, key=lambda item: item.id)
        self.save(config)
        return rule

    def remove_rule(self, rule_id: int) -> bool:
        config = self.load()
        rules = config.rules or []
        remaining = [rule for rule in rules if rule.id != rule_id]
        if len(remaining) == len(rules):
            return False
        config.rules = remaining
        self.save(config)
        return True

