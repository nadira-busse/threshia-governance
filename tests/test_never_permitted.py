"""Tests for threshia.rules.never_permitted."""

from threshia.models.policy import Policy
from threshia.rules.never_permitted import (
    check_all_policies_for_unparsed_restrictions,
    check_policy_for_unparsed_restrictions,
    extract_all_never_permitted_actions,
    extract_never_permitted_actions,
)


def make_policy(content: str, policy_id: str = "test-001") -> Policy:
    return Policy(
        id=policy_id,
        category="test",
        risk_level="low",
        applicable_tools=["Test.Tool"],
        source="test fixture",
        content=content,
        file_path="<memory>",
    )


def test_extracts_simple_bullet_list():
    content = """# Some Policy

The following actions are never permitted for an autonomous agent:

- `approve_invoice`
- `release_payment`

These represent final authorization steps.
"""
    policy = make_policy(content)
    actions = extract_never_permitted_actions(policy)
    assert actions == {"approve_invoice", "release_payment"}


def test_stops_at_prose_after_list():
    content = """Never permitted:

- `action_one`
- `action_two`

This paragraph should not be parsed as a bullet.

- `action_three`
"""
    policy = make_policy(content)
    actions = extract_never_permitted_actions(policy)
    # action_three appears after prose broke the block, so it's a
    # *new* unrelated list — not part of the never-permitted section.
    assert actions == {"action_one", "action_two"}


def test_no_never_permitted_section_returns_empty_set():
    content = "# A policy with no restrictions\n\nEverything here is ALLOW.\n"
    policy = make_policy(content)
    assert extract_never_permitted_actions(policy) == set()


def test_real_erp_policy_extracts_expected_actions():
    """Integration check against the actual ERP policy document."""
    from threshia.policies.loader import load_all_policies

    policies = load_all_policies()
    erp_policy = next(p for p in policies if p.id == "erp-controlled-actions-001")
    actions = extract_never_permitted_actions(erp_policy)

    assert actions == {
        "approve_invoice",
        "approve_payment",
        "release_payment",
        "modify_vendor_bank_details",
        "bypass_purchase_order_matching",
        "override_invoice_exception",
        "approve_employee_expense",
        "create_financial_commitment",
    }


def test_extract_all_combines_across_policies():
    policy_a = make_policy(
        "Never permitted:\n\n- `action_a`\n",
        policy_id="policy-a",
    )
    policy_b = make_policy(
        "Never permitted:\n\n- `action_b`\n",
        policy_id="policy-b",
    )
    lookup = extract_all_never_permitted_actions([policy_a, policy_b])
    assert lookup == {"action_a": "policy-a", "action_b": "policy-b"}


def test_extract_all_first_policy_wins_on_duplicate():
    policy_a = make_policy(
        "Never permitted:\n\n- `shared_action`\n",
        policy_id="policy-a",
    )
    policy_b = make_policy(
        "Never permitted:\n\n- `shared_action`\n",
        policy_id="policy-b",
    )
    lookup = extract_all_never_permitted_actions([policy_a, policy_b])
    assert lookup["shared_action"] == "policy-a"


def test_check_policy_warns_on_unparsed_restriction_language():
    """
    A policy that describes a restriction in prose, without the expected
    bullet-list format, should trigger a warning rather than silently
    enforcing nothing.
    """
    content = (
        "## Rule\n\n"
        "Agents are prohibited from modifying vendor bank details. "
        "This is described in prose only, not as a bullet list.\n"
    )
    policy = make_policy(content, policy_id="badly-formatted-policy")

    warnings = check_policy_for_unparsed_restrictions(policy)

    assert len(warnings) == 1
    assert "badly-formatted-policy" in warnings[0]
    assert "prohibited" in warnings[0]


def test_check_policy_no_warning_when_properly_parsed():
    content = "Never permitted:\n\n- `approve_invoice`\n"
    policy = make_policy(content, policy_id="good-policy")
    assert check_policy_for_unparsed_restrictions(policy) == []


def test_check_policy_no_warning_when_no_restriction_language_at_all():
    content = "## Rule\n\nEverything here is ALLOW. No restrictions apply.\n"
    policy = make_policy(content, policy_id="no-restrictions-policy")
    assert check_policy_for_unparsed_restrictions(policy) == []


def test_check_all_policies_real_kelvior_documents_have_no_warnings():
    """
    Integration check: none of the three real policy documents should
    trigger a false positive from this validation check.
    """
    from threshia.policies.loader import load_all_policies

    policies = load_all_policies()
    warnings = check_all_policies_for_unparsed_restrictions(policies)
    assert warnings == []


def test_broadened_markers_recognize_synonym_phrasing():
    """
    The marker set now recognizes phrasing beyond the exact words
    "never permitted" — e.g. "not permitted" and "must not be performed".
    """
    content = "The following action is not permitted:\n\n- `some_action`\n"
    policy = make_policy(content, policy_id="synonym-policy")
    assert extract_never_permitted_actions(policy) == {"some_action"}
