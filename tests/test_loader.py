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


def test_real_kelvior_policy_documents_load_successfully():
    """
    Integration check: the actual three Kelvior-based policy documents in
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

    for policy in policies:
        assert policy.content  # body is never empty
        assert len(policy.applicable_tools) > 0
