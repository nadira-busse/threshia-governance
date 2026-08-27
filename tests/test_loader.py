"""
Tests for the policy loader.

Covers: parsing valid documents, frontmatter validation, and error handling
for malformed files. Uses tmp_path (pytest's built-in temp directory fixture)
so tests never touch the real threshia/policies/documents/ folder.
"""

from pathlib import Path

import pytest

from threshia.policies.loader import (
    PolicyLoadError,
    load_all_policies,
    load_policy_file,
)

VALID_DOC = """---
id: test-policy-001
category: test
risk_level: low
applicable_tools:
  - Test.ToolOne
  - Test.ToolTwo
never_permitted:
  - delete_everything
source: Unit test fixture
---

# Test Policy

This is the body content.
"""


def write_doc(tmp_path: Path, filename: str, content: str) -> Path:
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_loads_valid_policy_file(tmp_path):
    path = write_doc(tmp_path, "test-policy-001.md", VALID_DOC)
    policy = load_policy_file(path)

    assert policy.id == "test-policy-001"
    assert policy.category == "test"
    assert policy.risk_level == "low"
    assert policy.applicable_tools == ["Test.ToolOne", "Test.ToolTwo"]
    assert policy.never_permitted == ["delete_everything"]
    assert policy.source == "Unit test fixture"
    assert "This is the body content." in policy.content
    assert policy.file_path == str(path)


def test_missing_frontmatter_delimiter_raises(tmp_path):
    path = write_doc(tmp_path, "bad.md", "# No frontmatter here\n\nJust text.")
    with pytest.raises(PolicyLoadError, match="must start with"):
        load_policy_file(path)


def test_missing_closing_delimiter_raises(tmp_path):
    broken = "---\nid: test\ncategory: test\n\n# Body without closing delimiter"
    path = write_doc(tmp_path, "bad.md", broken)
    with pytest.raises(PolicyLoadError, match="closing"):
        load_policy_file(path)


def test_missing_required_field_raises(tmp_path):
    incomplete = """---
id: test-policy-002
category: test
---

Body text.
"""
    path = write_doc(tmp_path, "incomplete.md", incomplete)
    with pytest.raises(PolicyLoadError, match="missing required frontmatter field"):
        load_policy_file(path)


def test_applicable_tools_must_be_list(tmp_path):
    bad_type = """---
id: test-policy-003
category: test
risk_level: low
applicable_tools: not-a-list
never_permitted:
  - some_action
source: test
---

Body text.
"""
    path = write_doc(tmp_path, "badtype.md", bad_type)
    with pytest.raises(PolicyLoadError, match="must be a YAML list"):
        load_policy_file(path)


def test_invalid_yaml_raises(tmp_path):
    invalid_yaml = """---
id: test-policy-004
category: [unclosed list
---

Body text.
"""
    path = write_doc(tmp_path, "invalidyaml.md", invalid_yaml)
    with pytest.raises(PolicyLoadError, match="invalid YAML"):
        load_policy_file(path)


def test_load_all_policies_returns_sorted_list(tmp_path):
    write_doc(tmp_path, "z-policy.md", VALID_DOC.replace("test-policy-001", "z-policy"))
    write_doc(tmp_path, "a-policy.md", VALID_DOC.replace("test-policy-001", "a-policy"))

    policies = load_all_policies(policies_dir=tmp_path)

    assert len(policies) == 2
    assert [p.id for p in policies] == ["a-policy", "z-policy"]


def test_load_all_policies_missing_directory_raises(tmp_path):
    nonexistent = tmp_path / "does_not_exist"
    with pytest.raises(PolicyLoadError, match="does not exist"):
        load_all_policies(policies_dir=nonexistent)


def test_load_all_policies_empty_directory_raises(tmp_path):
    with pytest.raises(PolicyLoadError, match="No policy files"):
        load_all_policies(policies_dir=tmp_path)


def test_repository_policy_documents_load_successfully():
    """
    Integration check: the actual three repository policy documents in
    threshia/policies/documents/ must parse without error. This test uses
    the real POLICIES_DIR, so it also confirms config.py path resolution
    is correct.
    """
    policies = load_all_policies()
    assert len(policies) == 3

    ids = {p.id for p in policies}
    assert ids == {
        "erp-controlled-actions-001",
        "hr-restricted-data-001",
        "itsm-readonly-001",
    }

    applicable_tools = {
        policy.id: policy.applicable_tools for policy in policies
    }
    assert applicable_tools == {
        "erp-controlled-actions-001": [
            "ERP.InvoiceApprovalPrepare",
            "ERP.PaymentReviewTrigger",
            "ERP.InvoiceLookup",
            "ERP.PurchaseOrderMatch",
        ],
        "hr-restricted-data-001": [
            "HR.EmployeeProfileLookup",
            "HR.TrainingStatusLookup",
        ],
        "itsm-readonly-001": [
            "ITSM.IncidentLookup",
            "ITSM.ClassificationSuggest",
            "ITSM.AssignmentGroupRecommend",
        ],
    }
    assert sum(len(tools) for tools in applicable_tools.values()) == 9

    gated_tools = {policy.id: policy.gated_tools for policy in policies}
    assert gated_tools == {
        "erp-controlled-actions-001": [
            "ERP.InvoiceApprovalPrepare",
            "ERP.PaymentReviewTrigger",
        ],
        "hr-restricted-data-001": [
            "HR.EmployeeProfileLookup",
            "HR.TrainingStatusLookup",
        ],
        "itsm-readonly-001": [],
    }
    assert sum(len(tools) for tools in gated_tools.values()) == 4

    never_permitted = {policy.id: policy.never_permitted for policy in policies}
    assert never_permitted == {
        "erp-controlled-actions-001": [
            "approve_invoice",
            "approve_payment",
            "release_payment",
            "modify_vendor_bank_details",
            "bypass_purchase_order_matching",
            "override_invoice_exception",
            "approve_employee_expense",
            "create_financial_commitment",
        ],
        "hr-restricted-data-001": [
            "modify_employee_record",
            "approve_hiring_decision",
            "approve_employee_status_change",
            "change_training_completion_status",
            "access_compensation_data",
            "access_medical_or_absence_records",
            "provide_legal_or_disciplinary_advice",
            "send_personalized_hr_guidance_without_review",
        ],
        "itsm-readonly-001": [
            "close_ticket",
            "update_incident_status",
            "change_priority_without_review",
            "assign_ticket_without_review",
            "trigger_change_request",
            "access_privileged_credentials",
            "modify_production_system",
            "execute_remediation_action",
        ],
    }
    assert sum(len(actions) for actions in never_permitted.values()) == 24

    for policy in policies:
        assert policy.content  # body is never empty
        assert len(policy.applicable_tools) > 0
        assert len(policy.never_permitted) > 0
        assert policy.source  # provenance metadata is retained


# --- Structured never_permitted frontmatter validation ---

VALID_NEVER_PERMITTED_DOC = """---
id: test-policy-005
category: test
risk_level: low
applicable_tools:
  - Test.ToolOne
never_permitted:
{never_permitted_yaml}
source: test
---

Body text.
"""


def _doc_with_never_permitted(never_permitted_yaml: str) -> str:
    return VALID_NEVER_PERMITTED_DOC.format(never_permitted_yaml=never_permitted_yaml)


def test_missing_never_permitted_raises(tmp_path):
    missing = """---
id: test-policy-006
category: test
risk_level: low
applicable_tools:
  - Test.ToolOne
source: test
---

Body text.
"""
    path = write_doc(tmp_path, "missing-never-permitted.md", missing)
    with pytest.raises(PolicyLoadError, match="missing required frontmatter field"):
        load_policy_file(path)


def test_never_permitted_scalar_instead_of_list_raises(tmp_path):
    doc = """---
id: test-policy-007
category: test
risk_level: low
applicable_tools:
  - Test.ToolOne
never_permitted: delete_everything
source: test
---

Body text.
"""
    path = write_doc(tmp_path, "scalar.md", doc)
    with pytest.raises(PolicyLoadError, match="must be a YAML list"):
        load_policy_file(path)


def test_never_permitted_null_raises(tmp_path):
    doc = """---
id: test-policy-008
category: test
risk_level: low
applicable_tools:
  - Test.ToolOne
never_permitted:
source: test
---

Body text.
"""
    path = write_doc(tmp_path, "null.md", doc)
    with pytest.raises(PolicyLoadError, match="must be a YAML list"):
        load_policy_file(path)


def test_never_permitted_empty_list_raises(tmp_path):
    path = write_doc(tmp_path, "empty.md", _doc_with_never_permitted("  []"))
    with pytest.raises(PolicyLoadError, match="at least one action name"):
        load_policy_file(path)


def test_never_permitted_integer_item_raises(tmp_path):
    path = write_doc(tmp_path, "int-item.md", _doc_with_never_permitted("  - 12345"))
    with pytest.raises(PolicyLoadError, match="must be strings"):
        load_policy_file(path)


def test_never_permitted_boolean_item_raises(tmp_path):
    path = write_doc(tmp_path, "bool-item.md", _doc_with_never_permitted("  - true"))
    with pytest.raises(PolicyLoadError, match="must be strings"):
        load_policy_file(path)


def test_never_permitted_null_item_raises(tmp_path):
    path = write_doc(tmp_path, "null-item.md", _doc_with_never_permitted("  - null"))
    with pytest.raises(PolicyLoadError, match="must be strings"):
        load_policy_file(path)


def test_never_permitted_nested_object_item_raises(tmp_path):
    yaml_block = "  - action: some_action\n    reason: because"
    path = write_doc(tmp_path, "nested.md", _doc_with_never_permitted(yaml_block))
    with pytest.raises(PolicyLoadError, match="must be strings"):
        load_policy_file(path)


def test_never_permitted_empty_string_item_raises(tmp_path):
    path = write_doc(tmp_path, "empty-string.md", _doc_with_never_permitted('  - ""'))
    with pytest.raises(PolicyLoadError, match="empty or whitespace-only"):
        load_policy_file(path)


def test_never_permitted_whitespace_only_item_raises(tmp_path):
    yaml_block = '  - "   "'
    path = write_doc(tmp_path, "whitespace.md", _doc_with_never_permitted(yaml_block))
    with pytest.raises(PolicyLoadError, match="empty or whitespace-only"):
        load_policy_file(path)


def test_never_permitted_duplicate_action_raises(tmp_path):
    yaml_block = "  - approve_invoice\n  - approve_invoice"
    path = write_doc(tmp_path, "duplicate.md", _doc_with_never_permitted(yaml_block))
    with pytest.raises(PolicyLoadError, match="duplicate action"):
        load_policy_file(path)


def test_never_permitted_valid_list_loads(tmp_path):
    yaml_block = "  - action_one\n  - action_two"
    path = write_doc(tmp_path, "valid.md", _doc_with_never_permitted(yaml_block))
    policy = load_policy_file(path)
    assert policy.never_permitted == ["action_one", "action_two"]
