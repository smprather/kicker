from __future__ import annotations

from pathlib import Path


def config_dir() -> Path:
    return Path.home() / ".config" / "kicker"


def state_dir() -> Path:
    return Path.home() / ".local" / "state" / "kicker"


def scripts_dir() -> Path:
    return config_dir() / "scripts"


def config_file() -> Path:
    return config_dir() / "config.yaml"


def runtime_state_file() -> Path:
    return state_dir() / "runtime_state.json"


def checks_log_file() -> Path:
    return state_dir() / "kicker_checks.log"


def actions_log_file() -> Path:
    return state_dir() / "kicker_actions.log"

