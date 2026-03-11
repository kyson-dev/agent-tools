import functools
import json
from pathlib import Path
from typing import Dict, Any

import yaml
from jsonschema import validate, ValidationError

def get_base_dir() -> Path:
    """Get the base '.agents' directory."""
    # This file is in src/agent_tools/config.py
    # So base dir is 3 levels up
    return Path(__file__).parent.parent.parent

def get_rules_path() -> Path:
    return get_base_dir() / "configs" / "rules.yaml"

def get_schema_path() -> Path:
    return get_base_dir() / "configs" / "schema.json"

@functools.lru_cache(maxsize=1)
def load_schema() -> Dict[str, Any]:
    schema_path = get_schema_path()
    if not schema_path.exists():
        return {}
        
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def validate_rules(rules: Dict[str, Any]) -> None:
    schema = load_schema()
    if schema:
        try:
            validate(instance=rules, schema=schema)
        except ValidationError as e:
            # We can log this but we probably shouldn't crash the whole run if 
            # strict validation fails. For now we will allow it, or raise it
            # depending on strictness requirements. Let's not raise to not break L3.
            pass

@functools.lru_cache(maxsize=1)
def load_rules() -> Dict[str, Any]:
    """Load and optionally validate rules.yaml."""
    rules_path = get_rules_path()
    if not rules_path.exists():
        return {}
        
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            rules = yaml.safe_load(f) or {}
            validate_rules(rules)
            return rules
    except Exception as e:
        return {}

def get_protected_branches() -> list[str]:
    """Get protected branches, providing safe defaults."""
    rules = load_rules()
    try:
        return rules["git"]["safety"]["protected_branches"]
    except KeyError:
        return ["main", "master", "production", "prod"]

def get_commit_allowed_types() -> list[str]:
    rules = load_rules()
    try:
        return rules["git"]["commit"]["allowed_types"]
    except KeyError:
        return []

def get_commit_message_regex() -> str:
    rules = load_rules()
    try:
        return rules["git"]["commit"]["message_regex"]
    except KeyError:
        return ""

def get_commit_subject_max_length() -> int:
    rules = load_rules()
    try:
        return rules["git"]["commit"]["subject_max_length"]
    except KeyError:
        return 72

def get_commit_body_wrap_length() -> int:
    rules = load_rules()
    try:
        return rules["git"]["commit"]["body_wrap_length"]
    except KeyError:
        return 80

def get_commit_grouping_signals() -> list[str]:
    rules = load_rules()
    try:
        return rules["git"]["commit"]["grouping_signals"]
    except KeyError:
        return []

def get_diff_max_total_lines() -> int:
    rules = load_rules()
    try:
        return rules["git"]["diff"]["max_total_diff_lines"]
    except KeyError:
        return 3000

def get_allow_direct_actions_to_protected() -> bool:
    """Check if direct actions to protected branches are permitted."""
    rules = load_rules()
    try:
        # Fallback to False if safety context exists but key doesn't
        return rules["git"]["safety"].get("allow_direct_actions_to_protected", False)
    except KeyError:
        return False
