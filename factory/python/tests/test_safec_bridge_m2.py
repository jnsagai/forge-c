"""Feature 011 M2 (F011-T013, T018; F011-AT-011..016 at the Forge-C side): the register-io domain extracted from RM
sections, the client's domain binding, and the materialized contract checked against an independent Python
derivation.

Three tiers:
- synthetic public register sections, always run;
- the owner's RM0486 inputs when present in the checkout (git-ignored);
- the real pinned SafeC engine when FORGE_SAFEC_ENGINE_PIN names one that supports validate_intents.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import contracts as C
from forge_factory.safec_bridge import domain as D

COL = 7


def _rows(fields: list[tuple]) -> list[str]:
    """Bit-number rows and access rows of a register diagram, laid out the way the RM text extraction does."""
    out = []
    for hi in (31, 15):
        bits = list(range(hi, hi - 16, -1))
        out.append("".join(f"{b:>{COL}}" for b in bits))
        line = [" "] * (COL * 16 + 2)
        for _, msb, lsb, tok, _ in fields:
            for b in bits:
                if lsb <= b <= msb:
                    center = (bits.index(b) * COL) + COL - 1
                    for i, ch in enumerate(tok):
                        line[center - len(tok) // 2 + i] = ch
        out.append("".join(line).rstrip())
    return out


def section(num: str, title: str, reg: str, offset: int, reset: str, fields: list[tuple]) -> str:
    """fields: (name, msb, lsb, access token, [(value, text)])"""
    lines = [f"#### {num} {title} ({reg})", "```text", f"                Address offset: 0x{offset:02X}",
             f"                Reset value: {reset}", *_rows(fields)]
    for name, msb, lsb, _tok, values in fields:
        span = f"{msb}:{lsb}" if msb != lsb else f"{msb}"
        lines.append(f"          Bit{'s' if msb != lsb else ''} {span} {name}{f'[{msb - lsb}:0]' if msb != lsb else ''}: "
                     f"Synthetic field {name}")
        lines += [f"                      - {v}: {t}" for v, t in values]
    return "\n".join(lines + ["```", ""])


SYNTH = [
    ("9.9.1", "Test key register", "TST_KR", 0x0, "0x0000 0000",
     [("KEY", 15, 0, "w", [("0xA1B2", "starts the synthetic block"), ("0x0F0F", "stops the synthetic block")])]),
    ("9.9.2", "Test control register", "TST_CR", 0x4, "0x0000 0010",
     [("MODE", 6, 4, "rw", []), ("EN", 0, 0, "rw", [])]),
    ("9.9.3", "Test status register", "TST_SR", 0x8, "0x0000 0000 (0xFFFF FEFF)",
     [("ON", 8, 8, "r", []), ("CLR", 1, 1, "rc_w1", [])]),
]


@pytest.fixture
def synthetic(tmp_path) -> tuple[dict, bytes]:
    secs = []
    for num, title, reg, off, reset, fields in SYNTH:
        p = tmp_path / f"{num}.md"
        p.write_text(section(num, title, reg, off, reset, fields))
        secs.append({"section": num, "file": f"inputs/sections/TST/{num}.md", "path": p, "pages": [7]})
    doc = D.from_sections(secs, prefix="TST", peripheral="TST", document="TST0001 Rev 1",
                          out_of_scope=["TST_WINR"])
    return doc, C.canonical_bytes(doc)


# --- F011-T013: the extracted domain -----------------------------------------------------------------------------------

def test_synthetic_sections_become_a_schema_valid_source_bound_domain(synthetic):
    doc, raw = synthetic
    assert C.schema_errors("domain", doc) == []
    regs = {r["register_id"]: r for r in doc["registers"]}
    key = regs["TST_KR"]["fields"][0]
    assert (key["lsb"], key["msb"], key["access_tokens"]) == (0, 15, ["w"])
    assert [v["value"] for v in key["values"]] == ["0xa1b2", "0xf0f"]
    assert key["values"][0]["fact_id"] == "F-TST_KR-KEY-V-A1B2"
    assert regs["TST_SR"]["reset_defined_mask"] == "0xfffffeff"
    assert regs["TST_CR"]["reset_value"] == "0x10" and regs["TST_CR"]["reset_defined_mask"] == "0xffffffff"
    sr = {f["field_id"]: f for f in regs["TST_SR"]["fields"]}
    assert sr["CLR"]["access_tokens"] == ["rc_w1"]  # kept as observed; SafeC decides it is unsupported
    assert doc["errata"] == {"status": "NOT_PROVIDED", "source_ids": []}
    assert all(len(s["file_sha256"]) == 64 for s in doc["sources"]) and doc["out_of_scope_registers"] == ["TST_WINR"]
    assert raw == C.canonical_bytes(json.loads(raw))


def test_a_field_without_access_in_the_diagram_is_unknown_not_guessed(tmp_path):
    p = tmp_path / "s.md"
    p.write_text(section("9.9.9", "Odd register", "TST_OR", 0xC, "0x0000 0000", [("X", 3, 0, "", [])]))
    doc = D.from_sections([{"section": "9.9.9", "file": "f.md", "path": p, "pages": [1]}], prefix="TST",
                          peripheral="TST", document="TST0001 Rev 1")
    assert doc["registers"][0]["fields"][0]["access_tokens"] == ["unknown"]


RM_IWDG = REPO_ROOT / "examples/0009-iwdg-st/inputs/RM0486-rev4-ch59-iwdg.md"
RM_RCC = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/RM0486-rev4-ch14-rcc.md"


def _rm_domain(tmp_path: Path, path: Path, prefix: str, keep: set[str]) -> tuple[dict, bytes]:
    secs = []
    for part in re.split(r"(?m)^(?=#### \d+\.\d+\.\d+ )", path.read_text()):
        m = re.match(r"#### (\d+\.\d+\.\d+) .*\(([A-Z0-9_]+)\)", part)
        if m and m.group(2) in keep:
            p = tmp_path / f"{m.group(1)}.md"
            p.write_text(part)
            secs.append({"section": m.group(1), "file": f"inputs/sections/RM0486/{m.group(1)}.md", "path": p,
                         "pages": [int(x) for x in re.findall(r"RM0486 p\.(\d+)", part)] or [1]})
    doc = D.from_sections(secs, prefix=prefix, peripheral=prefix, document="RM0486 Rev 4")
    return doc, C.canonical_bytes(doc)


@pytest.mark.skipif(not (RM_IWDG.is_file() and RM_RCC.is_file()), reason="owner RM0486 inputs not in this checkout")
def test_real_rm_facts_adc12en_bit5_and_the_iwdg_keys(tmp_path):
    rcc, _ = _rm_domain(tmp_path, RM_RCC, "RCC", {"RCC_AHB1ENR"})
    f = {x["field_id"]: x for x in rcc["registers"][0]["fields"]}
    assert (f["ADC12EN"]["lsb"], f["ADC12EN"]["access_tokens"]) == (5, ["rw"])
    iw, _ = _rm_domain(tmp_path, RM_IWDG, "IWDG", {"IWDG_KR", "IWDG_SR"})
    kr = {r["register_id"]: r for r in iw["registers"]}["IWDG_KR"]["fields"][0]
    assert [v["value"] for v in kr["values"]] == ["0xaaaa", "0x5555", "0xcccc"] and kr["access_tokens"] == ["w"]


# --- F011-T018: independent reference and contract verification (no engine needed) -------------------------------------

def test_reference_arithmetic_matches_the_rm_rules(synthetic):
    doc, _ = synthetic
    it = {"intent_id": "I", "source_fact_ids": ["F-TST_CR-MODE"], "register": "TST_CR", "field": "MODE",
          "action": "write_field", "logical_value": "5"}
    ref = K.reference_operation(doc, it)
    assert (ref["field_mask"], ref["encoded_value"], ref["preserved_mask"], ref["write_kind"]) == (
        "0x00000070", "0x00000050", "0xffffff8f", "read_modify_write")
    key = K.reference_operation(doc, {"intent_id": "K", "source_fact_ids": ["F-TST_KR-KEY-V-A1B2"],
                                      "register": "TST_KR", "field": "KEY", "action": "write_key_sequence",
                                      "logical_value": "0xA1B2"})
    assert (key["encoded_value"], key["write_kind"], key["preserved_mask"]) == (
        "0x0000a1b2", "full_register_write", "0x00000000")


def _contract(doc: dict, raw: bytes, request: dict, pin: CL.EnginePin, ops: list[dict]) -> dict:
    body = {"schema": "forge-c/register-io-contract/1", "profile": "register-io-0.1", "engine": pin.expected(),
            "binding": request["binding"], "domain_sha256": C.sha256_bytes(raw), "operations": ops, "coverage": [],
            "assumptions": [], "unresolved_obligations": [], "properties_checked": []}
    return {**body, "semantic_digest": C.sha256_bytes(C.canonical_bytes(body))}


def test_contract_verification_catches_tampering_and_engine_disagreement(synthetic):
    doc, raw = synthetic
    pin = CL.EnginePin(Path("/x"), "b" * 64, "c" * 40)
    it = {"intent_id": "I", "source_fact_ids": ["F-TST_CR-EN"], "register": "TST_CR", "field": "EN",
          "action": "set_field"}
    req, _ = C.build_request(request_id="R", operation="validate_intents", engine=pin.expected(),
                             binding={"workorder_id": "W", "workorder_sha256": "1" * 64,
                                      "source_manifest_sha256": C.sha256_bytes(raw), "policy_sha256": "3" * 64},
                             intents=[it])
    good = _contract(doc, raw, req, pin, [K.reference_operation(doc, it)])
    assert K.verify(good, req, raw, pin) == []
    assert K.verify({**good, "semantic_digest": "0" * 64}, req, raw, pin) == ["CONTRACT_DIGEST_MISMATCH"]
    wrong = dict(K.reference_operation(doc, it), field_mask="0x00000002", encoded_value="0x00000002")
    issues = K.verify(_contract(doc, raw, req, pin, [wrong]), req, raw, pin)
    assert any(i.startswith("ENGINES_DISAGREE:I:field_mask") for i in issues)
    other = _contract(doc, raw + b" ", req, pin, [K.reference_operation(doc, it)])
    assert "CONTRACT_DOMAIN_MISMATCH" in K.verify(other, req, raw, pin)
    assert "CONTRACT_INTENTS_MISMATCH" in K.verify(_contract(doc, raw, req, pin, []), req, raw, pin)


def test_client_refuses_a_domain_the_request_is_not_bound_to(synthetic, tmp_path):
    _, raw = synthetic
    pin = CL.EnginePin(tmp_path / "never-run", "b" * 64, "c" * 40)
    req, rraw = C.build_request(request_id="R", operation="validate_intents", engine=pin.expected(),
                                binding={"workorder_id": "W", "workorder_sha256": "1" * 64,
                                         "source_manifest_sha256": "2" * 64, "policy_sha256": "3" * 64},
                                intents=[{"intent_id": "I", "source_fact_ids": ["F"], "register": "R", "field": "F",
                                          "action": "read_field"}])
    out = CL.invoke(pin, req, rraw, tmp_path / "w", domain=raw)
    assert out.status == "STALE" and out.refused and out.issues == ["DOMAIN_NOT_BOUND_TO_REQUEST"]


# --- the real pinned engine --------------------------------------------------------------------------------------------

PIN = os.environ.get("FORGE_SAFEC_ENGINE_PIN")


def _engine() -> CL.EnginePin:
    p = json.loads(Path(PIN).read_text())
    return CL.EnginePin(Path(p["binary"]), p["binary_sha256"], p["source_commit_sha"], p["semantic_profile"])


def _supports_validate(tmp: Path) -> bool:
    """The pinned engine implements validate_intents for the domain version this checkout writes."""
    ident, issues = CL.handshake(_engine(), tmp / "id")
    return not issues and ident["operations"].get("validate_intents") == "SUPPORTED" and \
        ident["protocol"].get("domain") == C.DOMAIN_SCHEMA


def _run(tmp: Path, raw_domain: bytes, intents: list[dict], name: str):
    pin = _engine()
    req, rraw = C.build_request(request_id=f"REQ-{name}", operation="validate_intents", engine=pin.expected(),
                                binding={"workorder_id": "WO-F011-M2", "workorder_sha256": "1" * 64,
                                         "source_manifest_sha256": C.sha256_bytes(raw_domain),
                                         "policy_sha256": "3" * 64}, intents=intents)
    out = CL.invoke(pin, req, rraw, tmp / name, domain=raw_domain)
    return out, req, pin


needs_engine = pytest.mark.skipif(not PIN, reason="FORGE_SAFEC_ENGINE_PIN not set: no pinned private SafeC engine")


@needs_engine
def test_real_engine_validates_synthetic_intents_and_both_engines_agree(synthetic, tmp_path):
    if not _supports_validate(tmp_path):
        pytest.skip("pinned engine predates validate_intents for this domain version")
    doc, raw = synthetic
    intents = [
        {"intent_id": "EN-ON", "source_fact_ids": ["F-TST_CR-EN"], "register": "TST_CR", "field": "EN",
         "action": "set_field"},
        {"intent_id": "MODE-5", "source_fact_ids": ["F-TST_CR-MODE"], "register": "TST_CR", "field": "MODE",
         "action": "write_field", "logical_value": "5"},
        {"intent_id": "START", "source_fact_ids": ["F-TST_KR-KEY-V-A1B2"], "register": "TST_KR", "field": "KEY",
         "action": "write_key_sequence", "logical_value": "0xA1B2"},
        {"intent_id": "ON?", "source_fact_ids": ["F-TST_SR-ON"], "register": "TST_SR", "field": "ON",
         "action": "read_field"},
    ]
    out, req, pin = _run(tmp_path, raw, intents, "pass")
    assert out.status == "PASS" and out.admissible, out.issues
    vc = K.materialize(out, req, raw, tmp_path / "pass", pin)
    assert vc.by_intent()["MODE-5"]["encoded_value"] == "0x00000050"
    assert vc.unresolved_obligations[0].startswith("ERRATA_NOT_BASELINED")


@needs_engine
@pytest.mark.parametrize("intent, status, check", [
    ({"register": "TST_CR", "field": "EN", "action": "write_field", "logical_value": "0x1",
      "source_fact_ids": ["F-TST_CR-EN"]}, "PASS", None),
    ({"register": "TST_CR", "field": "MODE", "action": "write_field", "logical_value": "0x50",
      "source_fact_ids": ["F-TST_CR-MODE"]}, "FAIL", "RIO-MASK-AS-VALUE"),
    ({"register": "TST_CR", "field": "MODE", "action": "write_field", "logical_value": "9",
      "source_fact_ids": ["F-TST_CR-MODE"]}, "FAIL", "RIO-VALUE-OVERFLOW"),
    ({"register": "TST_KR", "field": "KEY", "action": "write_key_sequence", "logical_value": "0xA1B2",
      "source_fact_ids": ["F-TST_KR-KEY-V-F0F"]}, "FAIL", "RIO-KEY-FACT-MISMATCH"),
    ({"register": "TST_SR", "field": "ON", "action": "set_field", "source_fact_ids": ["F-TST_SR-ON"]},
     "FAIL", "RIO-WRITE-READ-ONLY"),
    ({"register": "TST_SR", "field": "CLR", "action": "read_field", "source_fact_ids": ["F-TST_SR-CLR"]},
     "UNSUPPORTED", "RIO-ACCESS-UNSUPPORTED"),
    ({"register": "TST_CR", "field": "NOPE", "action": "read_field", "source_fact_ids": ["F-TST_CR-EN"]},
     "FAIL", "RIO-UNKNOWN-FIELD"),
], ids=["pass", "mask-as-value", "overflow", "inverted-key", "ro-write", "w1c-unsupported", "unknown-field"])
def test_real_engine_statuses_and_checks(synthetic, tmp_path, intent, status, check):
    if not _supports_validate(tmp_path):
        pytest.skip("pinned engine predates validate_intents for this domain version")
    _, raw = synthetic
    out, _, _ = _run(tmp_path, raw, [{"intent_id": "I-1", **intent}], "case")
    assert out.status == status and out.issues == [], (out.status, out.issues)
    if check:
        assert out.result["findings"][0]["check_id"] == check and not out.admissible


@needs_engine
@pytest.mark.skipif(not (RM_IWDG.is_file() and RM_RCC.is_file()), reason="owner RM0486 inputs not in this checkout")
def test_real_engine_on_real_rm_facts(tmp_path):
    if not _supports_validate(tmp_path):
        pytest.skip("pinned engine predates validate_intents for this domain version")
    _, rcc = _rm_domain(tmp_path, RM_RCC, "RCC", {"RCC_AHB1ENR"})
    out, req, pin = _run(tmp_path, rcc, [{"intent_id": "ADC-ON", "source_fact_ids": ["F-RCC_AHB1ENR-ADC12EN"],
                                          "register": "RCC_AHB1ENR", "field": "ADC12EN", "action": "set_field"}], "adc")
    vc = K.materialize(out, req, rcc, tmp_path / "adc", pin)
    assert vc.operations[0]["field_mask"] == "0x00000020" and vc.operations[0]["logical_value"] == "1"
    out, _, _ = _run(tmp_path, rcc, [{"intent_id": "ADC-ON", "source_fact_ids": ["F-RCC_AHB1ENR-ADC12EN"],
                                      "register": "RCC_AHB1ENR", "field": "ADC12EN", "action": "set_field",
                                      "logical_value": "0x20"}], "adc-mask")
    assert out.status == "FAIL" and out.result["findings"][0]["check_id"] == "RIO-MASK-AS-VALUE"
    _, iw = _rm_domain(tmp_path, RM_IWDG, "IWDG", {"IWDG_KR"})
    out, req, pin = _run(tmp_path, iw, [{"intent_id": "START", "source_fact_ids": ["F-IWDG_KR-KEY-V-CCCC"],
                                         "register": "IWDG_KR", "field": "KEY", "action": "write_key_sequence",
                                         "logical_value": "0xCCCC"}], "start")
    assert K.materialize(out, req, iw, tmp_path / "start", pin).operations[0]["encoded_value"] == "0x0000cccc"
    out, _, _ = _run(tmp_path, iw, [{"intent_id": "START", "source_fact_ids": ["F-IWDG_KR-KEY-V-AAAA"],
                                     "register": "IWDG_KR", "field": "KEY", "action": "write_key_sequence",
                                     "logical_value": "0xCCCC"}], "inverted")
    assert out.status == "FAIL" and out.result["findings"][0]["check_id"] == "RIO-KEY-FACT-MISMATCH"
