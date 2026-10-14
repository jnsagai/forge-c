"""T008: compact agent result contract; prose/unbounded/routing output rejected; findings preserved."""
import json

from forge_factory.contracts.agent_output import parse

OK = {"status": "REWORK", "artifacts": ["inspection/SWE.3/INS-003.json"],
      "issues": ["MISRA-17.2: manual review needed", "REG-004: reset bit mask mismatch"], "next_action": "rework"}


def test_valid_compact_json_and_fenced_form():
    for text in (json.dumps(OK), "```json\n" + json.dumps(OK) + "\n```", "  " + json.dumps(OK) + "\n"):
        r = parse(text)
        assert r.ok and r.status == "REWORK" and r.issues == OK["issues"]
    assert len(parse(json.dumps(OK)).human_status()) <= 160


def test_prose_rejected():
    for text in ("All good! " + json.dumps(OK), "Sure, here is the result:\n```json\n{}\n```", "PASS", ""):
        r = parse(text)
        assert not r.ok and r.status == "FAILED"


def test_unbounded_and_extra_fields_rejected():
    assert parse(json.dumps({**OK, "issues": ["x" * 100] * 60})).errors[0] == "AGENT_OUTPUT_TOO_LARGE"
    r = parse(json.dumps({**OK, "explanation": "because"}))
    assert r.errors[0] == "AGENT_OUTPUT_SCHEMA"
    assert parse(json.dumps({**OK, "issues": ["y" * 121]})).errors[0] == "AGENT_OUTPUT_SCHEMA"
    assert parse(json.dumps({**OK, "status": "APPROVED"})).errors[0] == "AGENT_OUTPUT_SCHEMA"


def test_routing_directives_forbidden_and_findings_preserved_on_reject():
    assert parse(json.dumps({**OK, "preferred_next_label": "pass"})).errors == ["AGENT_OUTPUT_ROUTING_FORBIDDEN"]
    r = parse(json.dumps({**OK, "verdict": "ship it"}))
    assert not r.ok and "REG-004: reset bit mask mismatch" in r.issues


def test_none_and_non_utf8():
    assert parse(None).errors == ["AGENT_OUTPUT_MISSING"]
    assert parse(b"\xff\xfe").errors == ["AGENT_OUTPUT_NOT_UTF8"]
