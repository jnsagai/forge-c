"""Synthetic native tool events; no model output or functional correctness claim."""
# ruff: noqa: F811 - conventional imported pytest fixture
import json

import pytest
from forge_factory import delivery_first as D
from forge_factory.common import sha256_bytes
from test_delivery_first import (
    candidate,
    prepared,  # noqa: F401 - shared isolated fixture
)

REL = "software/ll/fixture.h"
BEFORE = "static inline unsigned fixture(void) { return 1U; }\n"
AFTER = "static inline unsigned fixture(void) { return 2U; }\n"
ROLES = {"author": {"role": "swe3-author"}, "inspector": {"role": "swe3-inspector"}}


def call(identity, name, args, *, node="author", error=False, complete=True):
    events = [{"event": "agent.tool.started", "node_id": node, "properties": {"event": {"ToolCallStarted": {
        "tool_call_id": identity, "tool_name": name, "arguments": args}}}}]
    if complete:
        events.append({"event": "agent.tool.completed", "node_id": node, "properties": {
            "event": {"ToolCallCompleted": {"tool_call_id": identity, "is_error": error}}}})
    return events


@pytest.mark.parametrize("fault", ["none", "json_args", "failed_edit", "pending", "wrong_role", "wrong_target",
                                  "ambiguous", "tampered_final", "malformed_args", "opaque_patch", "wrong_completion"])
def test_replay_requires_successful_bound_unambiguous_edits(tmp_path, fault):
    initial = BEFORE + BEFORE if fault == "ambiguous" else BEFORE
    events = call("write", "write_file", {"file_path": REL, "content": initial})
    args = {"file_path": REL, "old_string": "return 1U;", "new_string": "return 2U;"}
    expected = AFTER
    if fault == "failed_edit":
        expected = BEFORE
    if fault == "wrong_target":
        args["file_path"] = "workproducts/other.md"
    if fault == "json_args":
        args = json.dumps(args)
    elif fault == "malformed_args":
        args = "not json"
    edits = call("edit", "apply_patch" if fault == "opaque_patch" else "edit_file", args,
                 node="inspector" if fault == "wrong_role" else "author", error=fault == "failed_edit",
                 complete=fault != "pending")
    if fault == "wrong_completion":
        edits[-1]["node_id"] = "inspector"
    if fault == "tampered_final":
        expected = AFTER + "/* unrecorded change */\n"
    if fault == "ambiguous":
        expected = AFTER + BEFORE
    events += [{"event": "agent.message", "properties": {"event": "not a tool event"}}, *edits]
    result = D.native_source_provenance(events, ROLES, tmp_path, {REL: sha256_bytes(expected.encode())})
    status = ("CONFIRMED_NATIVE_WRITE_EDIT_CHAIN" if fault in ("none", "json_args") else
              "CONFIRMED_NATIVE_WRITE_FILE" if fault == "failed_edit" else "UNVERIFIED_EDIT_CHAIN")
    assert result["authorship"] == status, result
    if status == "CONFIRMED_NATIVE_WRITE_EDIT_CHAIN":
        chain, = result["edit_chain_evidence"]
        assert chain["anchor_content"] == BEFORE
        assert chain["final_sha256"] == sha256_bytes(AFTER.encode())
        edit, = chain["edits"]
        assert edit["old_string"] == "return 1U;" and edit["new_string"] == "return 2U;"
        assert edit["before_sha256"] == sha256_bytes(BEFORE.encode())
        assert edit["after_sha256"] == sha256_bytes(AFTER.encode())


def test_partial_edit_without_a_whole_source_anchor_does_not_prove_authorship(tmp_path):
    events = call("edit", "edit_file", {"file_path": REL, "old_string": "return 1U;", "new_string": "return 2U;"})
    out = D.native_source_provenance(events, ROLES, tmp_path, {REL: sha256_bytes(AFTER.encode())})
    assert out["authorship"] == "UNVERIFIED_EDIT_CHAIN"


def test_later_successful_whole_write_anchors_the_actual_final_bytes(tmp_path):
    events = call("bad", "edit_file", {"file_path": REL, "old_string": "not present", "new_string": "x"})
    events += call("write", "write_file", {"file_path": REL, "content": AFTER})
    out = D.native_source_provenance(events, ROLES, tmp_path, {REL: sha256_bytes(AFTER.encode())})
    assert out["authorship"] == "CONFIRMED_NATIVE_WRITE_FILE"
    assert out["write_evidence"] == [{"tool_call_id": "write", "path": REL, "sha256": sha256_bytes(AFTER.encode()),
                                     "node": "author"}]


def test_unfinished_unrelated_document_does_not_erase_source_proof(tmp_path):
    events = call("write", "write_file", {"file_path": REL, "content": BEFORE})
    events += call("doc", "write_file", {"file_path": "workproducts/SWE.1/requirements.md", "content": "draft"},
                   complete=False)
    out = D.native_source_provenance(events, ROLES, tmp_path, {REL: sha256_bytes(BEFORE.encode())})
    assert out["authorship"] == "CONFIRMED_NATIVE_WRITE_FILE"


@pytest.mark.parametrize("second_present", [False, True])
def test_every_declared_candidate_requires_its_own_complete_chain(tmp_path, second_present):
    other = "software/ll/second.h"
    events = call("a", "write_file", {"file_path": REL, "content": BEFORE})
    events += call("edit", "edit_file", {"file_path": REL, "old_string": "return 1U;", "new_string": "return 2U;"})
    if second_present:
        events += call("b", "write_file", {"file_path": other, "content": BEFORE})
    hashes = {REL: sha256_bytes(AFTER.encode()), other: sha256_bytes(BEFORE.encode())}
    out = D.native_source_provenance(events, ROLES, tmp_path, hashes)
    assert out["authorship"] == ("CONFIRMED_NATIVE_WRITE_EDIT_CHAIN" if second_present else "UNVERIFIED_EDIT_CHAIN")


@pytest.mark.parametrize("present", [True, False])
def test_audit_cli_never_executes_candidate_or_mutates_workspace(prepared, monkeypatch, capsys, present):
    ws, _ = prepared
    if present:
        candidate(ws)
    monkeypatch.setattr(D, "native_record", lambda *a: {"status": "OBSERVED", "native_id": "FIXTURE_ONLY",
                                                       "authorship": "CONFIRMED_NATIVE_WRITE_FILE"})

    def forbidden(*args, **kwargs):
        raise AssertionError("READ_ONLY_AUDIT_MUST_NOT_RUN_VERIFICATION_OR_PREFLIGHT")

    monkeypatch.setattr(D, "verify", forbidden)
    monkeypatch.setattr(D, "preflight", forbidden)
    before = {str(p.relative_to(ws)): sha256_bytes(p.read_bytes()) for p in ws.rglob("*") if p.is_file()}
    assert D.main(["--workspace", str(ws), "--step", "source-provenance"]) == (0 if present else 1)
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == ("VERIFIED_SOURCE_PROVENANCE" if present else "UNVERIFIED_SOURCE_PROVENANCE")
    assert out["functional_verification"] == "NOT_EVALUATED_BY_THIS_AUDIT"
    assert before == {str(p.relative_to(ws)): sha256_bytes(p.read_bytes()) for p in ws.rglob("*") if p.is_file()}


def test_audit_detects_candidate_change_during_metadata_collection(prepared, monkeypatch):
    ws, _ = prepared
    path = candidate(ws)

    def changed(*args):
        path.write_text("synthetic concurrent change")
        return {"status": "OBSERVED", "authorship": "CONFIRMED_NATIVE_WRITE_FILE"}

    monkeypatch.setattr(D, "native_record", changed)
    out = D.source_provenance_audit(ws)
    assert out["status"] == "UNVERIFIED_SOURCE_PROVENANCE"
    assert out["candidate_unchanged_during_audit"] is False
    assert out["candidate_hashes"] != out["candidate_hashes_after"]
