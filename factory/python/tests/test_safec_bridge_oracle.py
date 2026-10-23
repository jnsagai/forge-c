"""Feature 011 M5 (F011-T034; F011-AT-027/028 at the Forge-C side): a SafeC test oracle is accepted only when it is
bound to the validated contract and every expectation equals the independent Python derivation; observations are
checked case by case, and seeded mutants fail on their own intent.

Two tiers: synthetic register sections (always run) and the real pinned SafeC engine when FORGE_SAFEC_ENGINE_PIN
names one that supports derive_tests.
"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import contracts as C
from forge_factory.safec_bridge import oracle as O
from test_safec_bridge_m2 import PIN, _engine, needs_engine, synthetic  # noqa: F401 - shared fixtures

INTENTS = [
    {"intent_id": "EN-ON", "source_fact_ids": ["F-TST_CR-EN"], "register": "TST_CR", "field": "EN",
     "action": "set_field"},
    {"intent_id": "MODE-5", "source_fact_ids": ["F-TST_CR-MODE"], "register": "TST_CR", "field": "MODE",
     "action": "write_field", "logical_value": "5"},
    {"intent_id": "START", "source_fact_ids": ["F-TST_KR-KEY-V-A1B2"], "register": "TST_KR", "field": "KEY",
     "action": "write_key_sequence", "logical_value": "0xA1B2"},
    {"intent_id": "ON?", "source_fact_ids": ["F-TST_SR-ON"], "register": "TST_SR", "field": "ON",
     "action": "read_field"},
]


def _contract(doc: dict, raw: bytes) -> K.ValidatedContract:
    ops = tuple(K.reference_operation(doc, i) for i in INTENTS)
    return K.ValidatedContract("a" * 64, C.sha256_bytes(raw), ops, (), (), (), (), {})


def _oracle(doc: dict, contract: K.ValidatedContract) -> dict:
    o = {"schema": O.ORACLE_SCHEMA, "profile": "register-io-0.1", "contract_semantic_digest": contract.semantic_digest,
         "cases": O.reference_cases(doc, contract.operations), "limits": ["host register images only"]}
    o["oracle_digest"] = C.sha256_bytes(C.canonical_bytes(o))
    return o


def _redigest(o: dict) -> dict:
    o = {k: v for k, v in o.items() if k != "oracle_digest"}
    o["oracle_digest"] = C.sha256_bytes(C.canonical_bytes(o))
    return o


def _simulate(oracle: dict, mutate: dict | None = None) -> dict[str, list[dict]]:
    """A host 'implementation' that applies each case's expected effect, with optional per-intent mutants."""
    obs: dict[str, list[dict]] = {}
    for c in oracle["cases"]:
        after, ret = c["expected_after"], c["expected_return"]
        if mutate and c["intent_id"] in mutate:
            after, ret = mutate[c["intent_id"]](c)
        obs.setdefault(c["intent_id"], []).append({"initial": c["initial"], "after": after, "return": ret})
    return obs


def test_reference_cases_follow_the_register_rules(synthetic):  # noqa: F811
    doc, raw = synthetic
    cases = O.reference_cases(doc, _contract(doc, raw).operations)
    by = {}
    for c in cases:
        by.setdefault(c["intent_id"], []).append(c)
    assert len(by["MODE-5"]) == 4  # zeros, all defined bits, the field alone, all but the field
    assert by["MODE-5"][0]["expected_after"] == "0x00000050"  # read-modify-write from all zeros
    ones = int(by["MODE-5"][1]["initial"], 16)
    assert by["MODE-5"][1]["expected_after"] == f"0x{(ones & ~0x70) | 0x50:08x}"  # other bits preserved
    assert by["MODE-5"][3]["initial"] == f"0x{ones & ~0x70:08x}"
    assert len({c["expected_after"] for c in by["START"]}) == 1  # whole-register write, whatever the image
    assert not by["ON?"][0]["writes"] and by["ON?"][0]["expected_return"] == "0"
    assert [c["expected_return"] for c in by["ON?"]][2:] == ["1", "0"]  # the field alone, then all but the field
    assert all(c["expected_after"] == c["initial"] for c in by["ON?"])


def test_oracle_verification_catches_tampering_binding_and_disagreement(synthetic):  # noqa: F811
    doc, raw = synthetic
    k = _contract(doc, raw)
    good = _oracle(doc, k)
    assert O.verify(good, k, raw) == []
    assert "ORACLE_DIGEST_MISMATCH" in O.verify({**good, "limits": ["edited"]}, k, raw)
    assert "ORACLE_CONTRACT_MISMATCH" in O.verify(good, replace(k, semantic_digest="b" * 64), raw)
    assert O.verify(good, k, raw + b" ") == ["ORACLE_DOMAIN_MISMATCH"]
    wrong = json.loads(json.dumps(good))
    n = next(i for i, c in enumerate(wrong["cases"]) if c["intent_id"] == "MODE-5")
    wrong["cases"][n]["expected_after"] = "0x00000010"  # a wrong expected value, correctly re-digested
    issues = O.verify(_redigest(wrong), k, raw)
    assert issues and all(i.startswith(f"ENGINES_DISAGREE:case {n} MODE-5:expected_after") for i in issues), issues
    short = json.loads(json.dumps(good))
    short["cases"].pop()
    assert O.verify(_redigest(short), k, raw)[0].startswith("ORACLE_CASE_COUNT")
    assert O.verify({**good, "cases": "x"}, k, raw)[0].startswith("ORACLE_SCHEMA")


def test_seeded_mutants_fail_on_their_own_intent(synthetic):  # noqa: F811
    doc, raw = synthetic
    o = _oracle(doc, _contract(doc, raw))
    assert O.check(o, _simulate(o)) == []
    inverted_key = {"START": lambda c: ("0x0000a1b3", None)}
    absent_write = {"EN-ON": lambda c: (c["initial"], None)}
    clobber = {"MODE-5": lambda c: ("0x00000050", None)}  # writes the field but drops the preserved bits
    wrong_read = {"ON?": lambda c: (c["expected_after"], "7")}
    for mutant, intent, check in ((inverted_key, "START", "ORACLE-REGISTER-EFFECT"),
                                  (absent_write, "EN-ON", "ORACLE-REGISTER-EFFECT"),
                                  (clobber, "MODE-5", "ORACLE-REGISTER-EFFECT"),
                                  (wrong_read, "ON?", "ORACLE-RETURN-VALUE")):
        got = O.check(o, _simulate(o, mutant))
        assert got and {g["intent_id"] for g in got} == {intent} and {g["check"] for g in got} == {check}, got
    read_writes = {"ON?": lambda c: ("0x00000000" if c["initial"] != "0x00000000" else "0x00000001", c["expected_return"])}
    assert {g["check"] for g in O.check(o, _simulate(o, read_writes))} == {"ORACLE-UNEXPECTED-WRITE"}


def test_a_missing_or_vacuous_observation_is_never_a_pass(synthetic):  # noqa: F811
    doc, raw = synthetic
    o = _oracle(doc, _contract(doc, raw))
    assert {g["verdict"] for g in O.check(o, {})} == {"INCONCLUSIVE"}
    obs = _simulate(o)
    obs["MODE-5"] = obs["MODE-5"][:1]
    got = O.check(o, obs)
    n = sum(c["intent_id"] == "MODE-5" for c in o["cases"])
    assert got == [{"intent_id": "MODE-5", "verdict": "INCONCLUSIVE", "check": "ORACLE-NO-OBSERVATION"}] * (n - 1)
    vacuous = _simulate(o)
    for v in vacuous.values():  # a test that never sets up the specified initial image proves nothing
        for x in v:
            x["initial"] = "0xdeadbeef"
    assert {g["check"] for g in O.check(o, vacuous)} == {"ORACLE-OTHER-INITIAL-IMAGE"}


def _supports_derive(tmp) -> bool:
    ident, issues = CL.handshake(_engine(), tmp / "id")
    return not issues and ident["operations"].get("derive_tests") == "SUPPORTED"


@needs_engine
def test_real_engine_oracle_is_bound_and_agrees_with_forge_c(synthetic, tmp_path):  # noqa: F811
    if not _supports_derive(tmp_path):
        pytest.skip("pinned engine predates derive_tests")
    doc, raw = synthetic
    pin = _engine()
    req, rraw = C.build_request(request_id="REQ-ORACLE", operation="derive_tests", engine=pin.expected(),
                                binding={"workorder_id": "WO-F011-M5", "workorder_sha256": "1" * 64,
                                         "source_manifest_sha256": C.sha256_bytes(raw), "policy_sha256": "3" * 64},
                                intents=INTENTS)
    out = CL.invoke(pin, req, rraw, tmp_path / "o", domain=raw)
    assert out.status == "PASS" and out.admissible, out.issues
    vc = K.materialize(out, req, raw, tmp_path / "o", pin)
    o = O.materialize(out, vc, raw, tmp_path / "o")
    assert o["contract_semantic_digest"] == vc.semantic_digest and len(o["cases"]) >= 2 * len(INTENTS)
    assert O.check(o, _simulate(o)) == []
    bad = O.check(o, _simulate(o, {"START": lambda c: ("0x0000a1b3", None)}))
    assert {g["intent_id"] for g in bad} == {"START"}


@needs_engine
def test_real_engine_oracle_on_real_rm_facts(tmp_path):
    from test_safec_bridge_m2 import RM_IWDG, RM_RCC, _rm_domain

    if not (RM_IWDG.is_file() and RM_RCC.is_file()):
        pytest.skip("owner RM0486 inputs not in this checkout")
    if not _supports_derive(tmp_path):
        pytest.skip("pinned engine predates derive_tests")
    pin = _engine()
    got = {}
    for name, path, prefix, reg, intent in (
            ("adc", RM_RCC, "RCC", "RCC_AHB1ENR", {"intent_id": "ADC-ON", "source_fact_ids": ["F-RCC_AHB1ENR-ADC12EN"],
                                                    "register": "RCC_AHB1ENR", "field": "ADC12EN",
                                                    "action": "set_field"}),
            ("start", RM_IWDG, "IWDG", "IWDG_KR", {"intent_id": "START", "source_fact_ids": ["F-IWDG_KR-KEY-V-CCCC"],
                                                    "register": "IWDG_KR", "field": "KEY",
                                                    "action": "write_key_sequence", "logical_value": "0xCCCC"})):
        _, raw = _rm_domain(tmp_path, path, prefix, {reg})
        req, rraw = C.build_request(request_id=f"REQ-{name}", operation="derive_tests", engine=pin.expected(),
                                    binding={"workorder_id": "WO-F011-M5", "workorder_sha256": "1" * 64,
                                             "source_manifest_sha256": C.sha256_bytes(raw), "policy_sha256": "3" * 64},
                                    intents=[intent])
        out = CL.invoke(pin, req, rraw, tmp_path / name, domain=raw)
        vc = K.materialize(out, req, raw, tmp_path / name, pin)
        got[name] = O.materialize(out, vc, raw, tmp_path / name)["cases"]
    assert got["adc"][0]["expected_after"] == "0x00000020"  # set ADC12EN from all zeros: bit 5 only
    assert all(int(c["expected_after"], 16) & 0x20 for c in got["adc"])  # set from every image, other bits kept
    assert {c["expected_after"] for c in got["start"]} == {"0x0000cccc"}  # write-only key: whole-register write
