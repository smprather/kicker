from __future__ import annotations

from kicker.models import Rule


def parse_rate_limit(text: str) -> tuple[int, float]:
    parts = text.strip().split("/", 1)
    if len(parts) != 2:
        raise ValueError("rate limit must be in number/seconds format")
    count = int(parts[0])
    seconds = float(parts[1])
    if count <= 0:
        raise ValueError("rate limit count must be > 0")
    if seconds <= 0:
        raise ValueError("rate limit seconds must be > 0")
    return count, seconds


def effective_poll_interval(rule: Rule, default_poll_interval: float) -> float:
    return rule.poll_interval_seconds or default_poll_interval


def effective_timeout(rule: Rule, default_poll_interval: float) -> float:
    if rule.timeout_seconds is not None:
        return rule.timeout_seconds
    return effective_poll_interval(rule, default_poll_interval) * 0.9


def effective_rate_limit(rule: Rule, default_poll_interval: float) -> tuple[int, float]:
    if rule.rate_limit_count is not None and rule.rate_limit_seconds is not None:
        return rule.rate_limit_count, rule.rate_limit_seconds
    interval = effective_poll_interval(rule, default_poll_interval)
    return 1, interval


def trigger_matches(rule: Rule, previous_rc: int | None, current_rc: int) -> bool:
    mode = rule.trigger_mode
    if mode == "on_nonzero":
        return current_rc != 0
    if mode == "on_zero":
        return current_rc == 0
    if mode == "on_transition_fail_to_pass":
        return previous_rc is not None and previous_rc != 0 and current_rc == 0
    if mode == "on_transition_pass_to_fail":
        return previous_rc is not None and previous_rc == 0 and current_rc != 0
    if mode == "on_code_n":
        return rule.trigger_code is not None and current_rc == rule.trigger_code
    raise ValueError(f"Unknown trigger mode: {mode}")

