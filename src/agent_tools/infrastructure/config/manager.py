import functools
import json
import logging
import os
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import ValidationError, validate

logger = logging.getLogger(__name__)


def get_base_dir() -> Path:
    """Get the base '.agents' directory."""
    return Path(__file__).parent.parent.parent.parent.parent


def get_internal_base_rules_path() -> Path:
    """The tool's internal default rules.yaml (The Single Source of Truth)."""
    return Path(__file__).parent / "resources" / "rules.yaml"


def get_rules_path() -> Path:
    """Get the cascading overrides for user/project."""
    from agent_tools.infrastructure.config.context import REPO_CWD

    cwd = REPO_CWD.get() or os.getcwd()

    # Check Project first, then User Home
    paths = [
        Path(cwd) / ".agent" / "configs" / "rules.yaml",
        Path.home() / ".agent" / "configs" / "rules.yaml",
    ]
    for p in paths:
        if p.exists():
            return p
    return Path("")  # Signifies no user overrides


def get_schema_path() -> Path:
    """Schema is usually tool-internal, but can be overridden by project."""
    return Path(__file__).parent / "resources" / "schema.json"


@functools.lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    schema_path = get_schema_path()
    if not schema_path.exists():
        return {}
    try:
        with open(schema_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))
    except Exception:
        return {}


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def validate_rules(rules: dict[str, Any]) -> None:
    schema = load_schema()
    if schema:
        try:
            validate(instance=rules, schema=schema)
        except ValidationError as e:
            logger.warning(f"rules.yaml validation failed: {e.message}")


@functools.lru_cache(maxsize=1)
def load_rules() -> dict[str, Any]:
    """
    Load rules with the Single Source of Truth Chain:
    1. Base: Load Internal rules.yaml (providing all human-readable defaults)
    2. Overrides: Mix in User/Project partial rules
    3. Sanity: Clean 'version' (Legacy) and Validate against Schema
    """
    # 1. Start with the internal readable base
    base_path = get_internal_base_rules_path()
    try:
        with open(base_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"FATAL: Missing internal base rules at {base_path}: {e}")
        config = {}

    # 2. Layer user overrides
    user_rules_path = get_rules_path()
    if user_rules_path and user_rules_path.is_file():
        try:
            with open(user_rules_path, encoding="utf-8") as f:
                user_overrides = yaml.safe_load(f) or {}
                config = deep_merge(config, user_overrides)
        except Exception as e:
            logger.error(f"Failed to load user rules from {user_rules_path}: {e}")

    # 3. Cleanup & Integrity Check
    config.pop("version", None)
    validate_rules(config)
    return config


# --- Specialized Getters (Zero Callbacks) ---


def get_protected_branches() -> list[str]:
    rules = load_rules()
    return cast(list[str], rules["git"]["safety"]["protected_branches"])


def get_commit_allowed_types() -> list[str]:
    rules = load_rules()
    return cast(list[str], rules["git"]["commit"]["allowed_types"])


def get_commit_message_regex() -> str:
    rules = load_rules()
    return cast(str, rules["git"]["commit"]["message_regex"])


def get_commit_subject_max_length() -> int:
    rules = load_rules()
    return cast(int, rules["git"]["commit"]["subject_max_length"])


def get_commit_body_wrap_length() -> int:
    rules = load_rules()
    return cast(int, rules["git"]["commit"]["body_wrap_length"])


def get_commit_grouping_signals() -> list[str]:
    rules = load_rules()
    return cast(list[str], rules["git"]["commit"]["grouping_signals"])


def get_commit_max_groups() -> int:
    rules = load_rules()
    return cast(int, rules["git"]["commit"]["max_groups"])


def get_diff_max_lines_per_file() -> int:
    rules = load_rules()
    return cast(int, rules["git"]["diff"]["max_diff_lines_per_file"])


def get_diff_max_total_lines() -> int:
    rules = load_rules()
    return cast(int, rules["git"]["diff"]["max_total_diff_lines"])


def get_allow_direct_actions_to_protected() -> bool:
    rules = load_rules()
    return cast(bool, rules["git"]["safety"]["allow_direct_actions_to_protected"])


def get_release_tag_regex() -> str:
    rules = load_rules()
    return cast(str, rules["git"]["release"]["tag_regex"])


def get_full_commit_rules() -> dict[str, Any]:
    return {
        "allowed_types": get_commit_allowed_types(),
        "message_regex": get_commit_message_regex(),
        "subject_max_length": get_commit_subject_max_length(),
        "body_wrap_length": get_commit_body_wrap_length(),
        "grouping_signals": get_commit_grouping_signals(),
        "max_groups": get_commit_max_groups(),
    }
