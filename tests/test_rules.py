import pytest

from app.rules import DEFAULT_RULE_ID, list_public_rules, public_rule


def test_rule_registry_exposes_switcher_metadata():
    items = list_public_rules()
    assert items[0]["id"] == DEFAULT_RULE_ID
    assert items[0]["label"] == "软件学院 2024 级 · 发布版"
    assert public_rule(DEFAULT_RULE_ID)["id"] == DEFAULT_RULE_ID


def test_unknown_rule_is_rejected_instead_of_silently_falling_back():
    with pytest.raises(KeyError):
        public_rule("unknown-rule")
