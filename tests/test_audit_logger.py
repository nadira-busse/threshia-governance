"""Tests for threshia.audit.logger."""

import json

from threshia.audit.logger import log_verdict, read_audit_log
from threshia.engine.evaluator import evaluate, evaluate_and_log
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies


def test_log_verdict_writes_one_json_line(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    verdict = evaluate(call, policies)

    log_verdict(verdict, log_path=log_path)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["decision"] == "ALLOW"
    assert entry["tool_call"]["tool_name"] == "ERP.InvoiceLookup"


def test_log_verdict_appends_across_multiple_calls(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()

    call_a = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    call_b = ToolCall(tool_name="release_payment", parameters={})

    log_verdict(evaluate(call_a, policies), log_path=log_path)
    log_verdict(evaluate(call_b, policies), log_path=log_path)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    decisions = [json.loads(line)["decision"] for line in lines]
    assert decisions == ["ALLOW", "BLOCK"]


def test_log_verdict_creates_parent_directory(tmp_path):
    log_path = tmp_path / "nested" / "dir" / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="ITSM.IncidentLookup", parameters={})

    log_verdict(evaluate(call, policies), log_path=log_path)

    assert log_path.exists()


def test_read_audit_log_returns_empty_list_when_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.jsonl"
    assert read_audit_log(log_path=missing_path) == []


def test_read_audit_log_round_trips_entries(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="ERP.PaymentReviewTrigger",
        parameters={"human_approval_evidenced": True},
    )
    log_verdict(evaluate(call, policies), log_path=log_path)

    entries = read_audit_log(log_path=log_path)

    assert len(entries) == 1
    assert entries[0]["decision"] == "ALLOW"
    assert entries[0]["decision_source"] == "rule"


def test_evaluate_and_log_writes_to_configured_audit_path(tmp_path, monkeypatch):
    """
    evaluate_and_log() should use the real AUDIT_LOG_PATH from config by
    default. We redirect that config value to a temp path so this test
    never touches the project's actual audit.jsonl.
    """
    import threshia.audit.logger as logger_module

    temp_log = tmp_path / "audit.jsonl"
    monkeypatch.setattr(logger_module, "AUDIT_LOG_PATH", temp_log)

    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})

    verdict = evaluate_and_log(call, policies)

    assert verdict.decision == "ALLOW"
    assert temp_log.exists()
    assert len(read_audit_log(log_path=temp_log)) == 1
