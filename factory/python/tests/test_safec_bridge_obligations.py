"""Feature 011 F011-T033 (Forge-C side of S013-T018): SafeC's C11/ACSL obligations are accepted only when they are
bound to the validated contract and every obligation equals the independent Python derivation.

Two tiers: synthetic register sections (always run) and the real pinned SafeC engine when FORGE_SAFEC_ENGINE_PIN
names one that supports derive_contracts.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import contracts as C
from forge_factory.safec_bridge import obligations as OB
from test_safec_bridge_m2 import _engine, needs_engine, synthetic  # noqa: F401 - shared fixtures
from test_safec_bridge_oracle import INTENTS, _contract

TEXT = {"SUPPORTED": "SUPPORTED: measured", "INCONCLUSIVE": "INCONCLUSIVE: measured",
        "NOT_APPLICABLE": "NOT_APPLICABLE: not temporal"}


def _doc(contract: K.ValidatedContract) -> dict:
    ops = []
    for op in OB.reference(contract.operations):
        ops.append({**op, "obligations": [{**o, "applicability": {t: TEXT[v] for t, v in o["applicability"].items()}}
                                          for o in op["obligations"]],
                    "unsupported": [{"obligation": u, "reason": "not lowered"} for u in op["unsupported"]]})
    d = {"schema": OB.OBLIGATIONS_SCHEMA, "profile": "register-io-0.1", "contract_semantic_digest":
         contract.semantic_digest, "register_array": "R", "model": ["registers as plain memory"],
         "tools": [{"tool": "cbmc", "version": "6.11.0"}], "operations": ops}
    d["obligations_digest"] = C.sha256_bytes(C.canonical_bytes(d))
    return d


def _redigest(d: dict) -> dict:
    d = {k: v for k, v in d.items() if k != "obligations_digest"}
    d["obligations_digest"] = C.sha256_bytes(C.canonical_bytes(d))
    return d


def test_obligations_follow_the_operation_kind(synthetic):  # noqa: F811
    doc, raw = synthetic
    by = {o["intent_id"]: o for o in OB.reference(_contract(doc, raw).operations)}
    assert [o["id"] for o in by["EN-ON"]["obligations"]] == ["FIELD_VALUE", "PRESERVED_BITS", "FRAME"]
    assert [o["id"] for o in by["START"]["obligations"]] == ["WHOLE_WORD", "FRAME"]
    assert [o["id"] for o in by["ON?"]["obligations"]] == ["RETURN_FIELD", "NO_WRITE"]
    assert by["START"]["unsupported"][0] == "KEY_SEQUENCE_ORDER" and "KEY_SEQUENCE_ORDER" not in by["EN-ON"][
        "unsupported"]
    pres = next(o for o in by["EN-ON"]["obligations"] if o["id"] == "PRESERVED_BITS")
    assert pres["applicability"] == {"cbmc": "SUPPORTED", "frama-c-wp": "INCONCLUSIVE", "kind2": "NOT_APPLICABLE"}


def test_obligations_verification_catches_tampering_binding_and_disagreement(synthetic):  # noqa: F811
    doc, raw = synthetic
    vc = _contract(doc, raw)
    good = _doc(vc)
    assert OB.verify(good, vc, raw) == []
    assert OB.verify({**good, "obligations_digest": "0" * 64}, vc, raw) == ["OBLIGATIONS_DIGEST_MISMATCH"]
    assert "OBLIGATIONS_CONTRACT_MISMATCH" in OB.verify(good, replace(vc, semantic_digest="b" * 64), raw)
    assert "OBLIGATIONS_DOMAIN_MISMATCH" in OB.verify(good, vc, raw + b" ")
    assert OB.verify({**good, "extra": 1}, vc, raw)[0].startswith("OBLIGATIONS_SCHEMA")
    # an obligation weakened with its digest recomputed: the engines disagree
    weak = _redigest({**good, "operations": [dict(o) for o in good["operations"]]})
    weak["operations"][0] = {**weak["operations"][0], "obligations": [
        {**weak["operations"][0]["obligations"][0], "acsl": "ensures \\true;"}, *weak["operations"][0]["obligations"][1:]]}
    weak = _redigest(weak)
    assert any(i.startswith("ENGINES_DISAGREE:EN-ON:obligations") for i in OB.verify(weak, vc, raw))
    # a tool claimed applicable where it was measured inconclusive
    over = _redigest({**good, "operations": [dict(o) for o in good["operations"]]})
    obs = [dict(o) for o in over["operations"][0]["obligations"]]
    obs[1] = {**obs[1], "applicability": {**obs[1]["applicability"], "frama-c-wp": "SUPPORTED: claimed"}}
    over["operations"][0] = {**over["operations"][0], "obligations": obs}
    assert any("ENGINES_DISAGREE:EN-ON" in i for i in OB.verify(_redigest(over), vc, raw))
    # an unsupported obligation dropped (a gap hidden)
    hidden = _redigest({**good, "operations": [dict(o) for o in good["operations"]]})
    start = next(n for n, o in enumerate(hidden["operations"]) if o["intent_id"] == "START")
    hidden["operations"][start] = {**hidden["operations"][start],
                                   "unsupported": hidden["operations"][start]["unsupported"][1:]}
    assert any(i.startswith("ENGINES_DISAGREE:START:unsupported") for i in OB.verify(_redigest(hidden), vc, raw))


def _supports_contracts(tmp) -> bool:
    ident, issues = CL.handshake(_engine(), tmp / "id")
    return not issues and ident["operations"].get("derive_contracts") == "SUPPORTED"


@needs_engine
def test_real_engine_obligations_are_bound_and_agree_with_forge_c(synthetic, tmp_path):  # noqa: F811
    if not _supports_contracts(tmp_path):
        pytest.skip("pinned engine predates derive_contracts")
    doc, raw = synthetic
    pin = _engine()
    req, rraw = C.build_request(request_id="REQ-OBLIGATIONS", operation="derive_contracts", engine=pin.expected(),
                                binding={"workorder_id": "WO-F011-T033", "workorder_sha256": "1" * 64,
                                         "source_manifest_sha256": C.sha256_bytes(raw), "policy_sha256": "3" * 64},
                                intents=INTENTS)
    out = CL.invoke(pin, req, rraw, tmp_path / "o", domain=raw)
    assert out.status == "PASS" and out.admissible, out.issues
    vc = K.materialize(out, req, raw, tmp_path / "o", pin)
    ob = OB.materialize(out, vc, raw, tmp_path / "o")
    assert ob["contract_semantic_digest"] == vc.semantic_digest
    assert [o["intent_id"] for o in ob["operations"]] == [i["intent_id"] for i in INTENTS]
    # a result without the obligations artifact is refused
    stripped = replace(out, result={**out.result, "output_artifacts": out.result["output_artifacts"][:1]})
    with pytest.raises(OB.ObligationsRejected):
        OB.materialize(stripped, vc, raw, tmp_path / "o")
