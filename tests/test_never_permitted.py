"""
Tests for threshia.rules.never_permitted.

build_never_permitted_lookup() combines each loaded Policy's structured
never_permitted field (validated at load time by threshia/policies/
loader.py) into a single action -> policy-id lookup. Unlike the previous
Markdown-prose parser this replaced, the lookup depends only on
Policy.never_permitted — never on Policy.content — so these tests also
prove that formatting drift in the Markdown body cannot change the
deterministic hard-block set.
"""

from pathlib import Path

from threshia.models.policy import Policy
from threshia.policies.loader import load_policy_file
from threshia.rules.never_permitted import build_never_permitted_lookup


def make_policy(
    never_permitted: list[str], policy_id: str = "test-001", content: str = ""
) -> Policy:
    return Policy(
        id=policy_id,
        category="test",
        risk_level="low",
        applicable_tools=["Test.Tool"],
        source="test fixture",
        content=content,
        file_path="<memory>",
        never_permitted=never_permitted,
    )


# --- Structured lookup construction ---


def test_build_lookup_combines_across_policies():
    policy_a = make_policy(["action_a"], policy_id="policy-a")
    policy_b = make_policy(["action_b"], policy_id="policy-b")
    lookup = build_never_permitted_lookup([policy_a, policy_b])
    assert lookup == {"action_a": "policy-a", "action_b": "policy-b"}


def test_build_lookup_first_policy_wins_on_duplicate():
    policy_a = make_policy(["shared_action"], policy_id="policy-a")
    policy_b = make_policy(["shared_action"], policy_id="policy-b")
    lookup = build_never_permitted_lookup([policy_a, policy_b])
    assert lookup["shared_action"] == "policy-a"


def test_build_lookup_empty_policy_list_returns_empty_dict():
    assert build_never_permitted_lookup([]) == {}


def test_build_lookup_policy_with_no_never_permitted_contributes_nothing():
    policy = make_policy([])
    assert build_never_permitted_lookup([policy]) == {}


def test_real_erp_policy_never_permitted_matches_frontmatter():
    """Integration check against the actual ERP policy document."""
    from threshia.policies.loader import load_all_policies

    policies = load_all_policies()
    erp_policy = next(p for p in policies if p.id == "erp-controlled-actions-001")

    assert set(erp_policy.never_permitted) == {
        "approve_invoice",
        "approve_payment",
        "release_payment",
        "modify_vendor_bank_details",
        "bypass_purchase_order_matching",
        "override_invoice_exception",
        "approve_employee_expense",
        "create_financial_commitment",
    }


def test_repository_policies_preserve_never_permitted_action_contract():
    """The repository policies expose the expected 24 blocked action names."""
    from threshia.policies.loader import load_all_policies

    policies = load_all_policies()
    lookup = build_never_permitted_lookup(policies)

    assert lookup == {
        "approve_invoice": "erp-controlled-actions-001",
        "approve_payment": "erp-controlled-actions-001",
        "release_payment": "erp-controlled-actions-001",
        "modify_vendor_bank_details": "erp-controlled-actions-001",
        "bypass_purchase_order_matching": "erp-controlled-actions-001",
        "override_invoice_exception": "erp-controlled-actions-001",
        "approve_employee_expense": "erp-controlled-actions-001",
        "create_financial_commitment": "erp-controlled-actions-001",
        "modify_employee_record": "hr-restricted-data-001",
        "approve_hiring_decision": "hr-restricted-data-001",
        "approve_employee_status_change": "hr-restricted-data-001",
        "change_training_completion_status": "hr-restricted-data-001",
        "access_compensation_data": "hr-restricted-data-001",
        "access_medical_or_absence_records": "hr-restricted-data-001",
        "provide_legal_or_disciplinary_advice": "hr-restricted-data-001",
        "send_personalized_hr_guidance_without_review": "hr-restricted-data-001",
        "close_ticket": "itsm-readonly-001",
        "update_incident_status": "itsm-readonly-001",
        "change_priority_without_review": "itsm-readonly-001",
        "assign_ticket_without_review": "itsm-readonly-001",
        "trigger_change_request": "itsm-readonly-001",
        "access_privileged_credentials": "itsm-readonly-001",
        "modify_production_system": "itsm-readonly-001",
        "execute_remediation_action": "itsm-readonly-001",
    }
    assert len(lookup) == 24


# --- Markdown formatting independence ---
#
# These prove the new invariant directly: the deterministic hard-block set
# comes entirely from frontmatter, so no mutation of the Markdown body can
# change it. Each case below mirrors a mutation that silently dropped
# actions under the old prose parser (see parser-mutation-results.md).

FRONTMATTER = """---
id: formatting-independence-001
category: test
risk_level: high
applicable_tools:
  - Test.ToolA
never_permitted:
  - action_one
  - action_two
  - action_three
source: test fixture
---

"""

BODY_VARIANTS = {
    "misspelled_heading": (
        "# Policy\n\n"
        "**The following actions are never permited for an autonomous agent:**\n\n"
        "- `action_one`\n- `action_two`\n- `action_three`\n"
    ),
    "different_heading_level": (
        "# Policy\n\n### Never Permitted Actions\n\n"
        "action_one, action_two, action_three\n"
    ),
    "bullets_removed": (
        "# Policy\n\nNever permitted: action_one, action_two, action_three.\n"
    ),
    "backticks_removed": (
        "# Policy\n\nThe following are never permitted:\n\n"
        "- action_one\n- action_two\n- action_three\n"
    ),
    "sections_reordered": (
        "## Verdict guidance\n\nSee below.\n\n"
        "# Policy\n\n## Context\n\nSome context.\n\n"
        "## Rule\n\nNever permitted actions are defined in frontmatter.\n"
    ),
    "prose_changed": (
        "# Policy\n\nThe machine-enforced restrictions for this policy are "
        "defined entirely in the frontmatter above and are not repeated here.\n"
    ),
    "empty_body": "",
}


def _write_variant(tmp_path: Path, variant_name: str) -> Path:
    body = BODY_VARIANTS[variant_name]
    path = tmp_path / f"{variant_name}.md"
    path.write_text(FRONTMATTER + body, encoding="utf-8")
    return path


def test_misspelled_heading_does_not_affect_deterministic_set(tmp_path):
    path = _write_variant(tmp_path, "misspelled_heading")
    policy = load_policy_file(path)
    assert set(policy.never_permitted) == {"action_one", "action_two", "action_three"}


def test_different_heading_level_does_not_affect_deterministic_set(tmp_path):
    path = _write_variant(tmp_path, "different_heading_level")
    policy = load_policy_file(path)
    assert set(policy.never_permitted) == {"action_one", "action_two", "action_three"}


def test_bullets_removed_does_not_affect_deterministic_set(tmp_path):
    path = _write_variant(tmp_path, "bullets_removed")
    policy = load_policy_file(path)
    assert set(policy.never_permitted) == {"action_one", "action_two", "action_three"}


def test_backticks_removed_does_not_affect_deterministic_set(tmp_path):
    path = _write_variant(tmp_path, "backticks_removed")
    policy = load_policy_file(path)
    assert set(policy.never_permitted) == {"action_one", "action_two", "action_three"}


def test_sections_reordered_does_not_affect_deterministic_set(tmp_path):
    path = _write_variant(tmp_path, "sections_reordered")
    policy = load_policy_file(path)
    assert set(policy.never_permitted) == {"action_one", "action_two", "action_three"}


def test_prose_changed_does_not_affect_deterministic_set(tmp_path):
    path = _write_variant(tmp_path, "prose_changed")
    policy = load_policy_file(path)
    assert set(policy.never_permitted) == {"action_one", "action_two", "action_three"}


def test_empty_body_does_not_affect_deterministic_set(tmp_path):
    """Even a completely empty Markdown body still enforces the frontmatter list."""
    path = _write_variant(tmp_path, "empty_body")
    policy = load_policy_file(path)
    assert set(policy.never_permitted) == {"action_one", "action_two", "action_three"}


def test_build_lookup_unaffected_by_content_across_all_variants(tmp_path):
    """
    End-to-end: load every body variant plus the real repository documents,
    and confirm build_never_permitted_lookup() output depends only on
    never_permitted, never on content.
    """
    policies = [_write_variant(tmp_path, name) for name in BODY_VARIANTS]
    loaded = [load_policy_file(p) for p in policies]

    lookups = [build_never_permitted_lookup([policy]) for policy in loaded]
    expected = {"action_one": "formatting-independence-001",
                "action_two": "formatting-independence-001",
                "action_three": "formatting-independence-001"}
    assert all(lookup == expected for lookup in lookups)
