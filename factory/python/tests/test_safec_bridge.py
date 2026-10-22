"""Feature 011 M1 (F011-T006, T007, T009, T010; F011-AT-004, AT-006..AT-010): the bridge client against a test
double of the engine. The double is synthetic; a run of the real pinned SafeC engine is separate evidence."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

import pytest
from forge_factory.common import sha256_file
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contracts as C

STUB = Path(__file__).parent / "fixtures/safec_bridge/stub_engine.py"
COMMIT = "c" * 40
BINDING = {"workorder_id": "WO-T-RCC-LL", "workorder_sha256": "1" * 64, "source_manifest_sha256": "2" * 64,
           "policy_sha256": "3" * 64}
INTENT = {"intent_id": "I-001", "source_fact_ids": ["F-RCC-AHB1ENR-ADC12EN"], "register": "RCC_AHB1ENR",
          "field": "ADC12EN", "action": "set_field", "logical_value": "1"}


def engine(tmp_path: Path, mode: str = "unsupported", **conf) -> CL.EnginePin:
    d = tmp_path / "engine"
    d.mkdir(parents=True, exist_ok=True)
    b = d / "safec-bridge"
    shutil.copy(STUB, b)
    b.chmod(0o755)
    (d / "mode.json").write_text(json.dumps({"mode": mode, "marker": str(d / "marker.log"), **conf}))
    return CL.EnginePin(binary=b, binary_sha256=sha256_file(b), source_commit_sha=COMMIT)


def request(pin: CL.EnginePin, **kw) -> tuple[dict, bytes]:
    args = {"request_id": "REQ-1", "operation": "validate_intents", "engine": pin.expected(), "binding": BINDING,
            "intents": [INTENT]} | kw
    return C.build_request(**args)


def run(tmp_path, mode="unsupported", lim=None, cancel=None, **kw):
    pin = engine(tmp_path, mode)
    doc, raw = request(pin, **kw)
    return CL.invoke(pin, doc, raw, tmp_path / "work", lim or CL.Limits(timeout_s=10, cpu_s=10), cancel), pin


# --- F011-AT-006 / AT-007: contract parsing -------------------------------------------------------------------

def test_request_bytes_are_canonical_and_stable():
    pin = CL.EnginePin(Path("/x"), "b" * 64, COMMIT)
    d1, r1 = request(pin)
    d2, r2 = request(pin, intents=[dict(reversed(list(INTENT.items())))])
    assert r1 == r2 and r1 == C.canonical_bytes(d1) and b" " not in r1
    assert C.parse_request(r1) == d1


@pytest.mark.parametrize("raw, code", [
    (b'{"schema": "a", "schema": "b"}', "DUPLICATE_KEY"),
    (b'{"x": NaN}', "NON_FINITE_NUMBER"),
    (b'{"x": "\xff"}', "INVALID_UTF8"),
    (b'[1, 2]', "NOT_AN_OBJECT"),
    (b'{"x": ', "MALFORMED_JSON"),
    (b'   ', "EMPTY"),
    (b'{"x": "' + b"a" * (C.MAX_RESULT_BYTES + 1) + b'"}', "OVERSIZED"),
], ids=["duplicate-key", "nan", "invalid-utf8", "not-object", "truncated", "empty", "oversized"])
def test_hostile_bytes_are_refused_before_interpretation(raw, code):
    with pytest.raises(C.ContractError) as exc:
        C.parse_result(raw)
    assert exc.value.code == code


def test_result_semantics_beyond_the_schema():
    base = json.loads((Path(__file__).parent / "fixtures/safec_bridge/examples.json").read_text())
    ok = next(c["message"] for c in base["cases"] if c["id"] == "result-valid-unsupported")
    assert C.parse_result(C.canonical_bytes(ok))["status"] == "UNSUPPORTED"
    dup = {**ok, "findings": ok["findings"] * 2}
    with pytest.raises(C.ContractError, match="SCHEMA_VIOLATION|DUPLICATE_FINDING_ID"):
        C.parse_result(C.canonical_bytes(dup))
    renamed = {**ok, "findings": [ok["findings"][0], {**ok["findings"][0], "message": "other"}]}
    with pytest.raises(C.ContractError, match="DUPLICATE_FINDING_ID"):
        C.parse_result(C.canonical_bytes(renamed))
    bad = {**ok, "status": "PASS", "findings": [{**ok["findings"][0], "severity": "critical"}]}
    with pytest.raises(C.ContractError, match="CONTRADICTORY_PASS"):
        C.parse_result(C.canonical_bytes(bad))
    with pytest.raises(C.ContractError, match="SCHEMA_VIOLATION"):
        C.parse_result(C.canonical_bytes({**ok, "status": "READY_FOR_OFFLINE_REVIEW"}))


def test_a_request_the_schema_refuses_is_never_built():
    pin = CL.EnginePin(Path("/x"), "b" * 64, COMMIT)
    with pytest.raises(C.ContractError, match="SCHEMA_VIOLATION"):
        request(pin, intents=[{**INTENT, "mask": "0x20"}])  # a model-supplied mask is not a request field
    with pytest.raises(C.ContractError, match="SCHEMA_VIOLATION"):
        request(pin, operation="verify_candidate")
    with pytest.raises(C.ContractError, match="SCHEMA_VIOLATION"):
        C.build_request(request_id="R", operation="validate_intents", binding=BINDING, intents=[INTENT],
                        engine={**pin.expected(), "semantic_profile": "sampled-latch-0.1"})


# --- F011-AT-006: honest round trip ---------------------------------------------------------------------------

def test_honest_unsupported_round_trip_binds_every_identity(tmp_path):
    out, pin = run(tmp_path)
    assert out.status == "UNSUPPORTED" and not out.admissible and out.issues == []
    assert out.input_sha256 == sha256_file(tmp_path / "work/request.json")
    assert out.result["engine"] == pin.expected() and out.result["request_id"] == "REQ-1"
    assert out.result["findings"][0]["check_id"] == "OPERATION_SUPPORTED"


def test_a_verified_pass_is_admissible_only_with_its_evidence_and_artifacts(tmp_path):
    out, _ = run(tmp_path, "pass_with_artifact")
    assert out.status == "PASS" and out.admissible and out.issues == []


# --- F011-AT-004: engine identity before execution ------------------------------------------------------------

def test_wrong_binary_digest_refuses_without_executing(tmp_path):
    pin = engine(tmp_path)
    doc, raw = request(pin)
    wrong = CL.EnginePin(pin.binary, "f" * 64, COMMIT)
    out = CL.invoke(wrong, {**doc, "expected_engine": wrong.expected()}, raw, tmp_path / "w")
    assert out.status == "STALE" and out.refused and out.issues[0].startswith("ENGINE_DIGEST_MISMATCH")
    assert not (pin.binary.parent / "marker.log").exists()


def test_missing_engine_and_request_not_bound_to_the_pin_are_refused(tmp_path):
    pin = engine(tmp_path)
    doc, raw = request(pin)
    gone = CL.EnginePin(tmp_path / "nope", pin.binary_sha256, COMMIT)
    out = CL.invoke(gone, {**doc, "expected_engine": gone.expected()}, raw, tmp_path / "w1")
    assert out.status == "ERROR" and out.refused and out.issues == ["ENGINE_MISSING:nope"]
    other = CL.EnginePin(pin.binary, pin.binary_sha256, "9" * 40)
    out = CL.invoke(other, doc, raw, tmp_path / "w2")
    assert out.status == "STALE" and out.issues == ["REQUEST_ENGINE_NOT_PIN"]


@pytest.mark.parametrize("mode, issue", [
    ("identity_wrong_commit", "ENGINE_SOURCE_COMMIT_MISMATCH"),
    ("identity_no_profile", "PROFILE_NOT_OFFERED:register-io-0.1"),
])
def test_handshake_mismatch_stops_before_the_run(tmp_path, mode, issue):
    out, pin = run(tmp_path, mode)
    assert out.status == "STALE" and out.refused and any(i.startswith(issue) for i in out.issues)
    calls = (pin.binary.parent / "marker.log").read_text()
    assert "['identity']" in calls and "['run']" not in calls


# --- F011-AT-008: forged, broken and hostile engines ----------------------------------------------------------

@pytest.mark.parametrize("mode, status, issue", [
    ("forged_pass_exit1", "ERROR", "ENGINE_EXIT:1"),
    ("wrong_request_id", "ERROR", "RESULT_REQUEST_ID_MISMATCH"),
    ("wrong_input_digest", "STALE", "RESULT_INPUT_DIGEST_MISMATCH"),
    ("wrong_engine", "STALE", "RESULT_ENGINE_MISMATCH"),
    ("missing_evidence", "ERROR", "EVIDENCE_MISSING"),
    ("tampered_evidence", "ERROR", "EVIDENCE_DIGEST_MISMATCH"),
    ("evidence_disagrees", "ERROR", "EVIDENCE_STATUS_MISMATCH"),
    ("missing_artifact", "ERROR", "ARTIFACT_MISSING:C-001"),
    ("artifact_digest_mismatch", "ERROR", "ARTIFACT_DIGEST_MISMATCH:C-001"),
    ("contradictory_pass", "ERROR", "RESULT_CONTRADICTORY_PASS"),
    ("no_result", "ERROR", "RESULT_MISSING"),
    ("duplicate_keys", "ERROR", "RESULT_DUPLICATE_KEY"),
    ("invalid_utf8", "ERROR", "RESULT_INVALID_UTF8"),
    ("unknown_field", "ERROR", "RESULT_SCHEMA_VIOLATION"),
    ("oversized", "ERROR", "RESULT_OVERSIZED"),
    ("huge_stdout", "UNSUPPORTED", None),
])
def test_no_broken_or_forged_engine_output_becomes_admissible(tmp_path, mode, status, issue):
    out, _ = run(tmp_path, mode)
    assert not out.admissible
    if mode == "huge_stdout":  # a correct result with an oversized stream is still not clean
        assert out.issues == ["STREAM_OVERSIZED:stdout_bytes"] and out.status == "ERROR"
        return
    assert out.status == status and issue in out.issues, out.issues


def test_crash_is_an_error(tmp_path):
    out, _ = run(tmp_path, "crash")
    assert out.status == "ERROR" and not out.admissible
    assert any(i.startswith("ENGINE_EXIT:") for i in out.issues) and "RESULT_MISSING" in out.issues


def test_timeout_kills_the_engine_and_everything_it_started(tmp_path):
    t0 = time.monotonic()
    out, pin = run(tmp_path, "spawn_child", lim=CL.Limits(timeout_s=1.5, cpu_s=10))
    assert out.status == "ERROR" and out.issues == ["TIMEOUT"] and time.monotonic() - t0 < 10
    child = int((pin.binary.parent / "child.pid").read_text())
    for _ in range(50):  # reaped by init after the group kill
        if not Path(f"/proc/{child}").exists() or "Z" in Path(f"/proc/{child}/stat").read_text().split()[2]:
            break
        time.sleep(0.05)
    assert not Path(f"/proc/{child}").exists() or "Z" in Path(f"/proc/{child}/stat").read_text().split()[2]


def test_cancellation_stops_a_running_engine(tmp_path):
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    t0 = time.monotonic()
    out, _ = run(tmp_path, "sleep", cancel=cancel)
    assert out.status == "ERROR" and out.issues == ["CANCELLED"] and time.monotonic() - t0 < 5


# --- privacy and environment ----------------------------------------------------------------------------------

def test_engine_gets_an_empty_environment_and_its_streams_stay_out_of_the_record(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "should-not-reach-the-engine")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    out, pin = run(tmp_path)
    calls = (pin.binary.parent / "marker.log").read_text().splitlines()
    assert calls == ["['identity'] ['LANG', 'LC_ALL', 'PATH']", "['run'] ['LANG', 'LC_ALL', 'PATH']"]
    assert "PRIVATE-DETAIL-0001" not in json.dumps(out.record())
    assert "PRIVATE-DETAIL-0001" in (tmp_path / "work/engine.stderr").read_text()


# --- F011-AT-009 / AT-010: statuses, stability and invalidation -----------------------------------------------

def test_only_pass_is_admissible_every_other_status_blocks(tmp_path):
    for i, mode in enumerate(("unsupported", "pass_with_artifact")):
        out, _ = run(tmp_path / str(i), mode)
        assert out.admissible == (out.status == "PASS")


def test_identical_requests_give_byte_identical_results_and_the_cache_binds_inputs(tmp_path):
    pin = engine(tmp_path)
    doc, raw = request(pin)
    a = CL.invoke(pin, doc, raw, tmp_path / "a")
    b = CL.invoke(pin, doc, raw, tmp_path / "b")
    assert (tmp_path / "a/result.json").read_bytes() == (tmp_path / "b/result.json").read_bytes()
    assert a.result == b.result
    cache = CL.ResultCache(tmp_path / "cache")
    cache.put(pin, raw, a, tmp_path / "a")
    assert cache.get(pin, raw).result == a.result
    changed_doc, changed_raw = request(pin, binding={**BINDING, "source_manifest_sha256": "4" * 64})
    assert cache.get(pin, changed_raw) is None
    other_engine = CL.EnginePin(pin.binary, "e" * 64, COMMIT)
    assert cache.get(other_engine, raw) is None
    (tmp_path / "a/evidence/evidence.json").write_text("{}")
    assert cache.get(pin, raw) is None


def test_work_directory_is_never_reused(tmp_path):
    pin = engine(tmp_path)
    doc, raw = request(pin)
    CL.invoke(pin, doc, raw, tmp_path / "w")
    with pytest.raises(FileExistsError):
        CL.invoke(pin, doc, raw, tmp_path / "w")


def test_engine_file_must_be_executable(tmp_path):
    pin = engine(tmp_path)
    os.chmod(pin.binary, 0o644)
    assert CL.verify_engine_file(pin) == ["ENGINE_NOT_EXECUTABLE:safec-bridge"]


# --- the real pinned engine (F011-T008 integration; F011-AT-003 when run inside the profile namespace) ----------

PIN = os.environ.get("FORGE_SAFEC_ENGINE_PIN")


def _real_pin() -> CL.EnginePin:
    p = json.loads(Path(PIN).read_text())
    assert p["schema"] == "forge-c/safec-engine-pin/1"
    return CL.EnginePin(Path(p["binary"]), p["binary_sha256"], p["source_commit_sha"], p["semantic_profile"])


@pytest.mark.skipif(not PIN, reason="FORGE_SAFEC_ENGINE_PIN not set: no pinned private SafeC engine on this host")
def test_real_engine_handshake_and_unsupported_round_trip(tmp_path):
    pin = _real_pin()
    ident, issues = CL.handshake(pin, tmp_path / "id")
    assert issues == [] and set(ident["operations"].values()) == {"UNSUPPORTED"}
    for op in ("validate_intents", "derive_contracts", "derive_tests", "probe_capabilities"):
        doc, raw = request(pin, operation=op, request_id=f"REQ-{op}")
        out = CL.invoke(pin, doc, raw, tmp_path / op)
        assert out.status == "UNSUPPORTED" and not out.admissible and out.issues == [], (op, out.issues)
        assert out.result["findings"][0]["check_id"] == "OPERATION_SUPPORTED"
        assert out.result["engine"] == pin.expected() and out.exit_code == 0


@pytest.mark.skipif(not PIN, reason="FORGE_SAFEC_ENGINE_PIN not set: no pinned private SafeC engine on this host")
def test_real_engine_is_refused_under_a_wrong_pin_and_answers_identically_twice(tmp_path):
    pin = _real_pin()
    wrong = CL.EnginePin(pin.binary, "0" * 64, pin.source_commit_sha)
    doc, raw = request(wrong)
    out = CL.invoke(wrong, doc, raw, tmp_path / "wrong")
    assert out.status == "STALE" and out.refused
    stale_commit = CL.EnginePin(pin.binary, pin.binary_sha256, "a" * 40)
    doc, raw = request(stale_commit)
    out = CL.invoke(stale_commit, doc, raw, tmp_path / "commit")
    assert out.status == "STALE" and any(i.startswith("ENGINE_SOURCE_COMMIT_MISMATCH") for i in out.issues)
    doc, raw = request(pin)
    CL.invoke(pin, doc, raw, tmp_path / "a")
    CL.invoke(pin, doc, raw, tmp_path / "b")
    assert (tmp_path / "a/result.json").read_bytes() == (tmp_path / "b/result.json").read_bytes()
    assert (tmp_path / "a/evidence/evidence.json").read_bytes() == (tmp_path / "b/evidence/evidence.json").read_bytes()


# --- F011-T011: no AI agent role reaches the bridge -----------------------------------------------------------

def test_no_agent_role_can_reach_the_bridge(tmp_path):
    """M1 grants the bridge to no AI agent: only deterministic orchestration calls the CLI. The MCP registry has no
    SafeC operation, and every production role is denied every way to it (MCP names, native shell, a bare tool).
    Granting it later means a narrow, owner-reviewed registry operation with explicit role grants (ADR-0015 #3)."""
    from forge_factory.policy.authz import Authorizer, Binding

    auth = Authorizer(Binding("B-T011", str(tmp_path), {}))
    assert not [op for op in auth.registry.ops() if "safec" in op.lower()]
    nodes = {f"n_{rid}": {"role": rid, "phase": getattr(a, "phase", None)} for rid, a in auth.agents.items()}
    auth = Authorizer(Binding("B-T011", str(tmp_path), nodes))
    tools = ("mcp__forge-safec-mcp__validate_intents", "mcp__safec__run", "safec_bridge", "shell", "run_command",
             "exec_command")
    allowed = [(n, t) for n in nodes for t in tools if auth.decide(n, t, {"command": "safec-bridge run"}).allow]
    assert len(nodes) > 5 and allowed == []
