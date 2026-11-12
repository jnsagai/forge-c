"""Explicit new-profile checks; synthetic facts, real-engine lane separately pinned."""

import copy
import json
import os
from pathlib import Path

import pytest
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import contracts as C
from forge_factory.safec_bridge import domain as D
from forge_factory.safec_bridge import obligations as OB
from forge_factory.safec_bridge import oracle as O
from test_safec_bridge_m2 import section


@pytest.fixture
def special(tmp_path):
    rows = [
        ("9.9.1", "Test control", "TST_CR", 0, "0x0000 007F", [("LATCH", 7, 7, "rs", []), ("VALUE", 6, 0, "rw", [])]),
        ("9.9.2", "Test status", "TST_SR", 4, "0x0000 0000", [("FLAG", 0, 0, "rc_w0", [])]),
    ]
    sources = []
    for num, title, reg, offset, reset, fields in rows:
        p = tmp_path / (num + ".md")
        p.write_text(section(num, title, reg, offset, reset, fields))
        sources.append({"section": num, "file": p.name, "path": p, "pages": [1]})
    doc = D.from_sections(sources, prefix="TST", peripheral="TST", document="SYNTH Rev 1", semantic_profile="register-io-0.2")
    return doc, C.canonical_bytes(doc)


def intent(register, field, action, value=None):
    d = {
        "intent_id": register + "-" + field + "-" + action,
        "register": register,
        "field": field,
        "action": action,
        "source_fact_ids": ["F-" + register + "-" + field],
    }
    if value is not None:
        d["logical_value"] = value
    return d


def test_schema_families_are_explicit_and_legacy_rejects_new_domain(special):
    doc, _ = special
    assert C.schema_errors("domain", doc, profile="register-io-0.2") == []
    assert C.schema_errors("domain", doc)
    old = C.schema("domain")
    assert old["properties"]["schema"]["const"] == "forge-c/register-io-domain/2"
    assert old["properties"]["profile"]["const"] == "register-io-0.1"


@pytest.mark.parametrize(
    "register,field,action,value,access,mask,encoded,preserved,kind",
    [
        ("TST_CR", "LATCH", "set_field", None, "RS", "0x00000080", "0x00000080", "0xffffff7f", "read_modify_write"),
        ("TST_CR", "VALUE", "write_field", "127", "RW", "0x0000007f", "0x0000007f", "0xffffff80", "read_modify_write"),
        ("TST_SR", "FLAG", "write_field", "0", "RC_W0", "0x00000001", "0x00000000", "0x00000000", "full_register_write"),
        ("TST_CR", "LATCH", "read_field", None, "RS", "0x00000080", None, "0xffffffff", "none"),
        ("TST_SR", "FLAG", "read_field", None, "RC_W0", "0x00000001", None, "0xffffffff", "none"),
    ],
)
def test_independent_source_arithmetic(special, register, field, action, value, access, mask, encoded, preserved, kind):
    doc, _ = special
    op = K.reference_operation(doc, intent(register, field, action, value))
    assert (op["access"], op["field_mask"], op["encoded_value"], op["preserved_mask"], op["write_kind"]) == (
        access,
        mask,
        encoded,
        preserved,
        kind,
    )


@pytest.mark.parametrize(
    "change", ["clear-rs", "zero-rs", "one-rcw0", "mixed-rcw0", "unknown-reset", "unsafe-sibling", "wrong-domain", "multibit"]
)
def test_independent_checker_does_not_derive_unsafe_special_operations(special, change):
    doc, _ = special
    doc = copy.deepcopy(doc)
    it = intent("TST_CR", "LATCH", "set_field")
    if change == "clear-rs":
        it = intent("TST_CR", "LATCH", "clear_field")
    elif change == "zero-rs":
        it = intent("TST_CR", "LATCH", "write_field", "0")
    elif change == "one-rcw0":
        it = intent("TST_SR", "FLAG", "write_field", "1")
    elif change == "mixed-rcw0":
        doc["registers"][1]["fields"].append(copy.deepcopy(doc["registers"][0]["fields"][0]))
        it = intent("TST_SR", "FLAG", "clear_field")
    elif change == "unknown-reset":
        doc["registers"][1]["reset_defined_mask"] = "0x1"
        it = intent("TST_SR", "FLAG", "clear_field")
    elif change == "unsafe-sibling":
        doc["registers"][0]["fields"][0]["access_tokens"] = ["rc_w0"]
        it = intent("TST_CR", "VALUE", "write_field", "127")
    elif change == "wrong-domain":
        doc["schema"] = "forge-c/register-io-domain/2"
    else:
        doc["registers"][0]["fields"][0]["msb"] = 8
    with pytest.raises(ValueError):
        K.reference_operation(doc, it)


def test_new_request_family_is_bound_to_the_explicit_engine_profile():
    engine = {"source_commit_sha": "c" * 40, "binary_sha256": "b" * 64, "semantic_profile": "register-io-0.2"}
    req, raw = C.build_request(
        request_id="v02-request",
        operation="validate_intents",
        engine=engine,
        binding={
            "workorder_id": "synthetic",
            "workorder_sha256": "a" * 64,
            "source_manifest_sha256": "d" * 64,
            "policy_sha256": "e" * 64,
        },
        intents=[intent("TST_CR", "LATCH", "read_field")],
    )
    assert C.parse_request(raw) == req
    assert C.schema_errors("request", req)
    for bad in ("register-io-9.9", {"forged": "profile"}):
        with pytest.raises(C.ContractError, match="SCHEMA_VIOLATION"):
            C.build_request(
                request_id="bad",
                operation="validate_intents",
                engine={**engine, "semantic_profile": bad},
                binding=req["binding"],
                intents=[intent("TST_CR", "LATCH", "read_field")],
            )


PIN = os.environ.get("FORGE_SAFEC_V02_ENGINE_PIN")


@pytest.mark.skipif(not PIN, reason="FORGE_SAFEC_V02_ENGINE_PIN not set: new engine must be qualified separately")
def test_actual_v02_engine_artifacts_survive_independent_checks(special, tmp_path):
    doc, raw = special
    data = json.loads(Path(PIN).read_bytes())
    pin = CL.EnginePin(Path(data["binary"]), data["binary_sha256"], data["source_commit_sha"], data["semantic_profile"])
    assert pin.semantic_profile == "register-io-0.2"
    its = [
        intent("TST_CR", "LATCH", "set_field"),
        intent("TST_CR", "VALUE", "write_field", "127"),
        intent("TST_SR", "FLAG", "clear_field"),
    ]
    for operation in ("validate_intents", "derive_tests", "derive_contracts"):
        request, rraw = C.build_request(
            request_id="new-" + operation,
            operation=operation,
            engine=pin.expected(),
            binding={
                "workorder_id": "synthetic-v02",
                "workorder_sha256": "a" * 64,
                "source_manifest_sha256": C.sha256_bytes(raw),
                "policy_sha256": "d" * 64,
            },
            intents=its,
        )
        work = tmp_path / operation
        outcome = CL.invoke(pin, request, rraw, work, domain=raw)
        assert outcome.admissible and outcome.status == "PASS", outcome.record()
        contract = K.materialize(outcome, request, raw, work, pin)
        assert contract.raw["profile"] == "register-io-0.2"
        assert contract.raw["schema"] == "forge-c/register-io-contract/2"
        # Rehashing a corrupt artifact cannot replace independent source arithmetic.
        corrupt = copy.deepcopy(contract.raw)
        corrupt["operations"][0]["encoded_value"] = "0x00000000"
        corrupt["semantic_digest"] = C.sha256_bytes(
            C.canonical_bytes({k: v for k, v in corrupt.items() if k != "semantic_digest"})
        )
        assert any("ENGINES_DISAGREE" in issue for issue in K.verify(corrupt, request, raw, pin))
        corrupt = copy.deepcopy(contract.raw)
        corrupt["schema"] = "forge-c/register-io-contract/1"
        assert K.verify(corrupt, request, raw, pin)
        if operation == "derive_tests":
            oracle = O.materialize(outcome, contract, raw, work)
            assert oracle["schema"] == "forge-c/register-io-oracle/2"
            corrupt = copy.deepcopy(oracle)
            corrupt["cases"][0]["expected_after"] = "0x00000000"
            corrupt["oracle_digest"] = C.sha256_bytes(
                C.canonical_bytes({k: v for k, v in corrupt.items() if k != "oracle_digest"})
            )
            assert any("ENGINES_DISAGREE" in issue for issue in O.verify(corrupt, contract, raw))
        if operation == "derive_contracts":
            obligations = OB.materialize(outcome, contract, raw, work)
            assert obligations["schema"] == "forge-c/register-io-obligations/2"
            corrupt = copy.deepcopy(obligations)
            corrupt["operations"][0]["reference_c11"] = "R[0U] = 0U;"
            corrupt["obligations_digest"] = C.sha256_bytes(
                C.canonical_bytes({k: v for k, v in corrupt.items() if k != "obligations_digest"})
            )
            assert any("ENGINES_DISAGREE" in issue for issue in OB.verify(corrupt, contract, raw))
    # A legacy domain may not be silently relabelled by the new engine.
    legacy = copy.deepcopy(doc)
    legacy.update(schema="forge-c/register-io-domain/2", profile="register-io-0.1")
    outcome = CL.invoke(pin, request, rraw, tmp_path / "legacy-domain", domain=C.canonical_bytes(legacy))
    assert outcome.status == "STALE" and not outcome.admissible
