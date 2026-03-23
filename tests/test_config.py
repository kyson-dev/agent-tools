import logging

import yaml

from agent_tools.infrastructure.config.manager import (
    deep_merge,
    get_allow_direct_actions_to_protected,
    get_commit_allowed_types,
    get_commit_body_wrap_length,
    get_commit_grouping_signals,
    get_commit_max_groups,
    get_commit_subject_regex,
    get_commit_subject_max_length,
    get_diff_max_lines_per_file,
    get_diff_max_total_lines,
    get_protected_branches,
    get_release_tag_regex,
    load_rules,
    load_schema,
    validate_rules,
)

# --- 核心引擎逻辑测试 ---


def test_deep_merge():
    """验证深度递归合并算法。"""
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    overrides = {"a": {"b": 99}, "e": 4}
    result = deep_merge(base, overrides)

    assert result["a"]["b"] == 99
    assert result["a"]["c"] == 2
    assert result["d"] == 3
    assert result["e"] == 4


def test_load_rules_minimal_override(tmp_path, monkeypatch):
    """
    【最小覆盖测试】：
    在 user rules.yaml 中只写一个字段，确认内部 base rules 的默认值依然生效。
    """
    custom_rules = {"git": {"commit": {"max_groups": 999}}}
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(yaml.dump(custom_rules))

    monkeypatch.setattr("agent_tools.infrastructure.config.manager.get_rules_path", lambda: rules_file)

    load_rules.cache_clear()
    load_schema.cache_clear()

    rules = load_rules()

    # 1. 确认覆盖生效
    assert rules["git"]["commit"]["max_groups"] == 999
    # 2. 确认默认值透传生效 (来自内部 base rules.yaml)
    assert rules["git"]["commit"]["subject_max_length"] == 85
    assert "main" in rules["git"]["safety"]["protected_branches"]


def test_validate_rules_additional_properties(caplog):
    """
    【非法字段拦截测试】：
    由于 Schema 设置了 additionalProperties: false，写了乱七八糟的字段应该报错。
    """
    # 构建一个满足 required，但有额外字段的假 rules
    bad_rules = {
        "git": {
            "foo": "bar",  # 非法额外字段
            "safety": {
                "protected_branches": [],
                "allow_direct_actions_to_protected": False,
            },
            "commit": {
                "allowed_types": [],
                "subject_max_length": 0,
                "body_wrap_length": 0,
                "grouping_signals": [],
                "max_groups": 0,
            },
            "diff": {"max_diff_lines_per_file": 0, "max_total_diff_lines": 0},
            "release": {"tag_regex": ""},
        }
    }

    with caplog.at_level(logging.WARNING):
        validate_rules(bad_rules)

    assert "validation failed" in caplog.text
    assert "Additional properties are not allowed" in caplog.text


def test_validate_rules_missing_required_properties(caplog):
    """
    【必填字段拦截测试】：
    Schema 设置了 required 约束，缺少必须字段应该迅速拦截。
    """
    # 构建一个不满足必填项的规则字典
    missing_required_rules = {
        "git": {
            # 缺少 safety 字段
            "commit": {
                "allowed_types": [],
                "subject_max_length": 0,
                "body_wrap_length": 0,
                "grouping_signals": [],
                "max_groups": 0,
            },
            "diff": {"max_diff_lines_per_file": 0, "max_total_diff_lines": 0},
            "release": {"tag_regex": ""},
        }
    }

    with caplog.at_level(logging.WARNING):
        validate_rules(missing_required_rules)

    assert "validation failed" in caplog.text
    assert "'safety' is a required property" in caplog.text


def test_production_config_physical_alignment(caplog):
    """
    【生产环境物理对齐测试】：
    验证 src/agent_tools.infrastructure.config.managers 下的 internal rules.yaml 是否 100% 遵守 schema.json。
    """
    load_rules.cache_clear()
    load_schema.cache_clear()
    rules = load_rules()

    with caplog.at_level(logging.WARNING):
        validate_rules(rules)

    # 物理资产绝对不应该打破 Schema 的束缚
    assert "validation failed" not in caplog.text, f"Production config is invalid or incomplete: {caplog.text}"


def test_all_getters_return_typed_values():
    """验证所有 Getter 函数能正确穿透 Loader 且不会抛出 KeyError (得益于 SSOT 的完备性)。"""
    load_rules.cache_clear()
    load_schema.cache_clear()

    assert isinstance(get_protected_branches(), list)
    assert isinstance(get_commit_allowed_types(), list)
    assert isinstance(get_commit_subject_regex(), str)
    assert isinstance(get_commit_subject_max_length(), int)
    assert isinstance(get_commit_body_wrap_length(), int)
    assert isinstance(get_commit_grouping_signals(), list)
    assert isinstance(get_commit_max_groups(), int)
    assert isinstance(get_diff_max_lines_per_file(), int)
    assert isinstance(get_diff_max_total_lines(), int)
    assert isinstance(get_allow_direct_actions_to_protected(), bool)
    assert isinstance(get_release_tag_regex(), str)
