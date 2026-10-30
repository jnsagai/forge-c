"""Reuse independently revalidated author packets without importing phase verdicts."""
import copy
import json

import pytest
from forge_factory.common import sha256_bytes
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import visit as V


@pytest.fixture
def task(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    parent = state / "workorders/WO-PARENT/workspace"
    child = state / "workorders/WO-CHILD/workspace"
    (child / ".forge-run").mkdir(parents=True)
    (child / ".forge-run/manifest.json").write_text(json.dumps({"resumed_from": {"source_work_order": "WO-PARENT"}}))
    base = {"role": "swe1-author", "input_hash": "bound-complete-input", "output_schema": {
        "type": "object", "properties": {"effect": {"type": "integer"}}, "required": ["effect"],
        "additionalProperties": False}}
    record = {"task": "requirements:TEST", "status": "VALID", "doc": {"effect": 4}, "base_hash": base["input_hash"],
              "errors": [], "attempts": [{"usage": {"prompt_tokens": 1000, "completion_tokens": 200}}]}
    path = V._ckpt(parent, "SWE.1", record["task"])
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record))
    def check(doc):
        return [] if doc["effect"] == 4 else ["independent effect mismatch"]
    return parent, child, path, base, record, check


def test_hash_bound_validated_packet_is_reused_without_calls_or_phase_pass(task, monkeypatch):
    parent, child, path, base, record, check = task
    before = path.read_bytes()
    monkeypatch.setattr(S, "call", lambda *a, **kw: pytest.fail("validated identical task must not regenerate"))
    budget = {"calls": 0, "max_calls": 1}
    result = V.run_task(child, "SWE.1", record["task"], lambda *a: base, check, budget)
    assert result["doc"] == record["doc"] and result["reused"] is True and budget["calls"] == 0
    assert result["attempts"] == record["attempts"]  # Historical usage is retained, not charged as new usage.
    assert result["inherited_from"]["record_sha256"] == sha256_bytes(before)
    assert path.read_bytes() == before
    assert V._ckpt(child, "SWE.1", record["task"]).is_file()
    assert not (child / "inspection").exists() and not (child / "configuration/baselines").exists()


@pytest.mark.parametrize("case", ["changed-input", "schema-invalid", "validator-fails", "wrong-task", "invalid-status",
                                  "inspector", "symlink", "outside-lineage"])
def test_unqualified_or_other_role_checkpoint_is_not_reused(task, case):
    _, child, path, base, record, check = task
    base, record = copy.deepcopy(base), copy.deepcopy(record)
    if case == "changed-input":
        base["input_hash"] = "changed-authoritative-input"
    elif case == "schema-invalid":
        record["doc"] = {"effect": "4"}
    elif case == "validator-fails":
        record["doc"]["effect"] = 5
    elif case == "wrong-task":
        record["task"] = "requirements:OTHER"
    elif case == "invalid-status":
        record["status"] = "INVALID"
    elif case == "inspector":
        base["role"] = "swe1-inspector"
    elif case == "outside-lineage":
        (child / ".forge-run/manifest.json").write_text(json.dumps({"resumed_from": {"source_work_order": "../escape"}}))
    if case == "symlink":
        original = path.with_suffix(".old")
        path.rename(original)
        path.symlink_to(original)
    else:
        path.write_text(json.dumps(record))
    assert V.inherited_task(child, "SWE.1", "requirements:TEST", base, check) is None


def test_existing_valid_checkpoint_still_rechecks_current_validator(task, monkeypatch):
    _, child, _, base, record, _ = task
    path = V._ckpt(child, "SWE.1", record["task"])
    path.parent.mkdir(parents=True)
    record["doc"]["effect"] = 5
    path.write_text(json.dumps(record))
    called = []

    def correct(packet, **kw):
        called.append(packet)
        return {"doc": {"effect": 4}, "errors": [], "usage": {}, "wall_ms": 1, "finish_reason": "stop"}

    base.update(model="fixture", accounting={})
    monkeypatch.setattr(S, "call", correct)
    monkeypatch.setattr(S, "schema_mode_for", lambda _: ("json_schema", "fixture"))
    result = V.run_task(child, "SWE.1", record["task"], lambda *a: base,
                        lambda doc: [] if doc["effect"] == 4 else ["wrong effect"], {"calls": 0, "max_calls": 1})
    assert result["status"] == "VALID" and result["doc"] == {"effect": 4} and len(called) == 1
