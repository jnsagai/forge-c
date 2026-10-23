"""F011-T016 and S013-T014 at the Forge-C side, against the real pinned SafeC engine (FORGE_SAFEC_ENGINE_PIN).

Reset claims: a requirement's claim of a field's reset value on real RM0486 facts. The correct claim is accepted and
listed in the contract, re-derived independently here; a tampered claim is ENGINES_DISAGREE; a wrong claim is the
engine's RIO-RESET-CONTRADICTION with both values; an undefined reset is UNSUPPORTED.
Sealed evidence: every result of the engine carries a finalized seal that the client checks; a changed sealed file
or an unfinalized seal is refused.
"""
from __future__ import annotations

import json
import shutil

import pytest
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import contracts as C
from test_safec_bridge_m2 import RM_IWDG, _engine, _rm_domain, needs_engine


def _supports_reset(tmp) -> bool:
    req, raw = C.build_request(request_id="REQ-PROBE", operation="validate_intents", engine=_engine().expected(),
                               binding={"workorder_id": "WO", "workorder_sha256": "1" * 64,
                                        "source_manifest_sha256": "2" * 64, "policy_sha256": "3" * 64},
                               intents=[{"intent_id": "R", "source_fact_ids": ["F-X"], "register": "X", "field": "Y",
                                         "action": "check_reset", "logical_value": "0"}])
    out = CL.invoke(_engine(), req, raw, tmp / "probe")
    return not any("REQUEST_SCHEMA" in json.dumps(f) for f in (out.result or {}).get("findings", []))


def _call(tmp_path, name, raw, intents):
    pin = _engine()
    req, rraw = C.build_request(request_id=f"REQ-{name}", operation="validate_intents", engine=pin.expected(),
                                binding={"workorder_id": "WO-F011-T016", "workorder_sha256": "1" * 64,
                                         "source_manifest_sha256": C.sha256_bytes(raw), "policy_sha256": "3" * 64},
                                intents=intents)
    return req, CL.invoke(pin, req, rraw, tmp_path / name, domain=raw)


def _claim(field, value):
    return {"intent_id": f"{field}-RESET", "source_fact_ids": [f"F-IWDG_{'RLR' if field == 'RL' else 'SR'}-{field}"],
            "register": "IWDG_RLR" if field == "RL" else "IWDG_SR", "field": field, "action": "check_reset",
            "logical_value": value}


@needs_engine
def test_reset_claims_on_real_rm_facts(tmp_path):
    if not RM_IWDG.is_file():
        pytest.skip("owner RM0486 inputs not in this checkout")
    if not _supports_reset(tmp_path):
        pytest.skip("pinned engine predates check_reset")
    doc, raw = _rm_domain(tmp_path, RM_IWDG, "IWDG", {"IWDG_RLR", "IWDG_SR"})
    rlr = next(r for r in doc["registers"] if r["register_id"] == "IWDG_RLR")
    rl = next(f for f in rlr["fields"] if f["field_id"] == "RL")
    mask = ((1 << (rl["msb"] - rl["lsb"] + 1)) - 1) << rl["lsb"]
    reset = (int(rlr["reset_value"], 16) & mask) >> rl["lsb"]
    req, ok = _call(tmp_path, "ok", raw, [_claim("RL", str(reset))])
    assert ok.status == "PASS" and ok.admissible, ok.issues
    vc = K.materialize(ok, req, raw, tmp_path / "ok", _engine())
    assert vc.raw["reset_claims"] == [{"intent_id": "RL-RESET", "register": "IWDG_RLR", "field": "RL",
                                      "reset_value": str(reset), "source_fact_ids": ["F-IWDG_RLR-RL"]}]
    assert vc.operations == ()  # a reset claim is no register operation
    # a claim changed after the engine wrote it (digest recomputed): Forge-C's own derivation disagrees
    forged = json.loads(json.dumps(vc.raw))
    forged["reset_claims"][0]["reset_value"] = str(reset - 1)
    forged = {k: v for k, v in forged.items() if k != "semantic_digest"}
    forged["semantic_digest"] = C.sha256_bytes(C.canonical_bytes(forged))
    issues = K.verify(forged, req, raw, _engine())
    assert any(i.startswith("ENGINES_DISAGREE:RL-RESET:reset_claim") for i in issues), issues
    # a wrong claim: the engine's named contradiction, with both values
    _req, bad = _call(tmp_path, "bad", raw, [_claim("RL", str(reset - 1))])
    f = bad.result["findings"][0]
    assert bad.status == "FAIL" and f["check_id"] == "RIO-RESET-CONTRADICTION"
    assert (f["expected"], f["observed"]) == (str(reset), str(reset - 1))
    # IWDG_SR.ONF: the manual leaves its reset undefined (if the extracted domain does too, it cannot be accepted)
    sr = next(r for r in doc["registers"] if r["register_id"] == "IWDG_SR")
    onf = next((f for f in sr["fields"] if f["field_id"] == "ONF"), None)
    if onf is not None and not int(sr["reset_defined_mask"], 16) & (1 << onf["lsb"]):
        _req, und = _call(tmp_path, "und", raw, [_claim("ONF", "0")])
        assert und.status == "UNSUPPORTED" and und.result["findings"][0]["check_id"] == "RIO-RESET-UNDEFINED"


@needs_engine
def test_every_result_is_sealed_and_a_broken_seal_is_refused(tmp_path):
    if not RM_IWDG.is_file():
        pytest.skip("owner RM0486 inputs not in this checkout")
    _doc, raw = _rm_domain(tmp_path, RM_IWDG, "IWDG", {"IWDG_RLR"})
    _req, out = _call(tmp_path, "s", raw, [{"intent_id": "RL-SET", "source_fact_ids": ["F-IWDG_RLR-RL"],
                                            "register": "IWDG_RLR", "field": "RL", "action": "write_field",
                                            "logical_value": "100"}])
    ev = tmp_path / "s/evidence"
    if not (ev / "sealed").exists():
        pytest.skip("pinned engine predates sealed evidence")
    assert out.status == "PASS" and out.admissible and out.issues == [], out.issues
    rq = (tmp_path / "s/request.json").read_bytes()
    assert CL.seal_issues(ev, rq) == []
    # a changed sealed artifact
    work = tmp_path / "tamper"
    shutil.copytree(ev, work)
    for p in work.rglob("*"):
        p.chmod(0o755 if p.is_dir() else 0o644)
    (work / "sealed/payload/artifacts/validated_contract").write_bytes(b"{}")
    got = CL.seal_issues(work, rq)
    assert "SEAL_DIGEST_MISMATCH:artifacts/validated_contract" in got and \
        "SEAL_CONTENT_DIFFERS:artifacts/validated_contract" in got, got
    # an unfinalized seal; a seal of other request bytes
    (work / "sealed/FINALIZED").rename(work / "sealed/INCOMPLETE")
    assert CL.seal_issues(work, rq) == ["SEAL_NOT_FINALIZED"]
    assert "SEAL_CONTENT_DIFFERS:request.json" in CL.seal_issues(ev, rq + b" ")
