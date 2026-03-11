from config import load_rules, get_protected_branches, get_allow_direct_actions_to_protected

def test_load_rules_returns_dict():
    rules = load_rules()
    assert isinstance(rules, dict)

def test_protected_branches_default():
    branches = get_protected_branches()
    assert isinstance(branches, list)
    assert len(branches) > 0
