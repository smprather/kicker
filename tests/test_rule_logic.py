from __future__ import annotations

from kicker.models import Rule
from kicker.rule_logic import (
    effective_poll_interval,
    effective_rate_limit,
    effective_timeout,
    parse_rate_limit,
    trigger_matches,
)


def test_parse_rate_limit() -> None:
    count, seconds = parse_rate_limit("5/300")
    assert count == 5
    assert seconds == 300.0


def test_effective_defaults() -> None:
    rule = Rule(
        id=1,
        check="check.sh",
        action="action.sh",
        trigger_mode="on_nonzero",
    )
    assert effective_poll_interval(rule, 60.0) == 60.0
    assert effective_timeout(rule, 60.0) == 54.0
    assert effective_rate_limit(rule, 60.0) == (1, 60.0)


def test_trigger_modes() -> None:
    assert trigger_matches(
        Rule(id=1, check="c", action="a", trigger_mode="on_nonzero"),
        previous_rc=None,
        current_rc=1,
    )
    assert trigger_matches(
        Rule(id=1, check="c", action="a", trigger_mode="on_zero"),
        previous_rc=None,
        current_rc=0,
    )
    assert trigger_matches(
        Rule(id=1, check="c", action="a", trigger_mode="on_transition_fail_to_pass"),
        previous_rc=2,
        current_rc=0,
    )
    assert trigger_matches(
        Rule(id=1, check="c", action="a", trigger_mode="on_transition_pass_to_fail"),
        previous_rc=0,
        current_rc=2,
    )
    assert trigger_matches(
        Rule(
            id=1,
            check="c",
            action="a",
            trigger_mode="on_code_n",
            trigger_code=7,
        ),
        previous_rc=None,
        current_rc=7,
    )

