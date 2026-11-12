"""Feature 020 T009 (US1, FR-001, FR-004..FR-006): the governance package - model step + deterministic coverage.

The packet carries the inventory and the input section index only (no delivered code, no chapter text). The model's
answer (scripted here, never a real model) is validated; coverage is computed deterministically: every in-scope
delivered function and in-scope RM feature must be in a use case or an open point, else COVERAGE_FAIL names it and
SWE.1 stops before the author (`check` != 0). Owner use cases are merged with origin `owner`. The package is written as
JSON (contract-valid) and Markdown; `package_version` is the sha256 of the canonical package and is recorded in the
run."""
from __future__ import annotations

import copy
import hashlib
import json

import jsonschema
import pytest
from f020_fixtures import SER_HAL, SER_LL, SER_OUT, example, ser_spec
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT, canonical_json, sha256_file
from forge_factory.lrtx import structured as S

SCHEMA = json.loads((REPO_ROOT / "specs/020-usart-benchmark-pilot/contracts/governance-package.schema.json")
                    .read_text())
MODEL = "fake-model:q8"
IN_SCOPE = [f for f in SER_HAL + SER_LL if f not in SER_OUT]
OUT_JSON = "workproducts/SWE.1/governance/governance-package.json"
OUT_MD = "workproducts/SWE.1/governance/governance-package.md"


def answer(drop: tuple[str, ...] = (), features=("42.1", "42.3.1", "42.3.2")) -> dict:
    """A valid generated answer: two actors, three use cases covering every in-scope function and feature."""
    hal = [f for f in IN_SCOPE if f.startswith("HAL_") and f not in drop]
    ll = [f for f in IN_SCOPE if f.startswith("LL_") and f not in drop]
    return {
        "actors": [{"actor_id": "ACT-APP", "name": "Application", "description": "software using the HAL services"},
                   {"actor_id": "ACT-LLUSER", "name": "LL user", "description": "software using the LL services"}],
        "use_cases": [
            {"use_case_id": "UC-01", "title": "Bring up the interface", "actor_id": "ACT-APP",
             "goal": "initialise and release the interface", "functions": hal[:3], "rm_features": list(features[:1])},
            {"use_case_id": "UC-02", "title": "Exchange data", "actor_id": "ACT-APP", "goal": "send and receive data",
             "functions": hal[3:], "rm_features": list(features[1:])},
            {"use_case_id": "UC-03", "title": "Drive the interface directly", "actor_id": "ACT-LLUSER",
             "goal": "configure and move data with the LL services", "functions": ll, "rm_features": []}],
        "assumptions": [{"assumption_id": "AS-01", "text": "one interface instance is used at a time"}],
        "open_points": [{"open_point_id": "OP-01", "text": "timeout unit is not stated by the inputs",
                         "concerns": ["HAL_SER_Transmit"]}]}


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return prepared(tmp_path, ser_spec())


def prepared(tmp_path, spec, wo="WO-F020-G1"):
    from forge_factory.workflow.builder import binding_for, build

    w, _m = WO.prepare(example(tmp_path, spec, name=wo), wo)
    _g, nodes = build(wo, layer="LL+HAL", trace=True, brownfield="FROZEN", stop_after="SWE.1")
    nodes = {**nodes, "swe1_governance": dict(nodes["swe1_author"])}  # the governance node runs as swe1-author
    binding_for(wo, str(w), nodes).dump(w / ".forge-run/binding.json")
    return w


def scripted(answers: list, calls: list):
    def call(p, **_k):
        calls.append(p)
        doc = copy.deepcopy(answers[min(len(calls), len(answers)) - 1])
        return {"doc": doc, "errors": S.validate(doc, p["output_schema"]), "usage": {"prompt_tokens": 900,
                "completion_tokens": 300}, "wall_ms": 1.0, "finish_reason": "stop"}
    return call


def run(ws, monkeypatch, answers):
    from forge_factory.governance import package as P

    calls: list = []
    monkeypatch.setattr(S, "call", scripted(answers, calls))
    return P.visit(ws, MODEL), calls


def test_the_packet_carries_the_inventory_and_the_section_index_only(ws):
    from forge_factory.governance import package as P

    p = P.packet(ws, MODEL)
    assert p["phase"] == "SWE.1" and p["task"] == "governance" and p["role"] == "swe1-author"
    assert [s["path"] for s in p["sources"]] == ["inputs/governance-inventory.json", "inputs/index.md",
                                              ".fabro/skills/swe1-author/references/functional-level.md"]
    text = "\n".join(m["content"] for m in p["_messages"])
    assert "SERx->CR" not in text and "static inline" not in text and "Bit 5 LOOP" not in text  # no code, no chapter
    assert p["output_schema"] == P.ANSWER_SCHEMA and p["accounting"]["fits"]


def test_a_covering_answer_is_written_versioned_and_passes_the_coverage_check(ws, monkeypatch):
    from forge_factory.governance import package as P

    rep, calls = run(ws, monkeypatch, [answer()])
    assert rep["status"] == "PASS" and len(calls) == 1
    pkg = json.loads((ws / OUT_JSON).read_text())
    jsonschema.Draft202012Validator(SCHEMA).validate(pkg)
    assert pkg["coverage"] == {"uncovered_functions": [], "uncovered_features": [], "unused_use_cases": []}
    assert pkg["inventory_sha256"] == sha256_file(ws / "inputs/governance-inventory.json")
    body = {k: v for k, v in pkg.items() if k != "package_version"}
    assert pkg["package_version"] == hashlib.sha256(canonical_json(body)).hexdigest()
    assert {u["origin"] for u in pkg["use_cases"]} == {"generated"}
    st = json.loads((ws / ".forge-run/lrtx/SWE.1/governance/status.json").read_text())
    assert st == {"state": "COVERAGE_PASS", "package_version": pkg["package_version"],
                  "inventory_sha256": pkg["inventory_sha256"], "uncovered": []}
    assert P.check(ws) == 0
    md = (ws / OUT_MD).read_text()
    for item in ("## Actors", "## Use cases", "## Assumptions", "## Open points", "## Scope", "ACT-APP", "UC-03",
                 "AS-01", "OP-01", "COVERAGE_PASS", pkg["package_version"]):
        assert item in md
    calls.clear()  # unchanged inputs: the validated task is reused, no model call
    rep2, calls2 = run(ws, monkeypatch, [answer()])
    assert rep2["status"] == "PASS" and calls2 == []


def test_an_uncovered_in_scope_function_fails_coverage_and_names_it(ws, monkeypatch):
    from forge_factory.governance import package as P

    bad = answer(drop=("HAL_SER_GetState",))
    rep, calls = run(ws, monkeypatch, [bad])
    assert rep["status"] == "FAILED"
    assert any("COVERAGE_FAIL" in i and "HAL_SER_GetState" in i for i in rep["issues"])
    pkg = json.loads((ws / OUT_JSON).read_text())
    assert pkg["coverage"]["uncovered_functions"] == ["HAL_SER_GetState"]
    st = json.loads((ws / ".forge-run/lrtx/SWE.1/governance/status.json").read_text())
    assert st["state"] == "COVERAGE_FAIL" and st["uncovered"] == ["function:HAL_SER_GetState"]
    assert P.check(ws) == 1  # the run stops before the SWE.1 author
    assert "COVERAGE_FAIL" in (ws / OUT_MD).read_text()
    assert len(calls) > 1  # the uncovered function was sent back for a localized repair first


def test_the_repair_loop_fixes_coverage_from_the_named_items(ws, monkeypatch):
    rep, calls = run(ws, monkeypatch, [answer(drop=("HAL_SER_GetState",)), answer()])
    assert rep["status"] == "PASS" and len(calls) == 2
    assert any("HAL_SER_GetState" in f for f in calls[1]["findings"])


def test_an_open_point_covers_a_function(ws, monkeypatch):
    a = answer(drop=("HAL_SER_GetState",))
    a["open_points"].append({"open_point_id": "OP-02", "text": "state query semantics not in the inputs",
                             "concerns": ["HAL_SER_GetState"]})
    rep, _ = run(ws, monkeypatch, [a])
    assert rep["status"] == "PASS"


def test_an_uncovered_feature_fails_and_an_unused_use_case_is_reported(ws, monkeypatch):
    a = answer(features=("42.1", "42.3.1"))
    rep, _ = run(ws, monkeypatch, [a])
    assert rep["status"] == "FAILED" and any("42.3.2" in i for i in rep["issues"])
    b = answer()
    b["use_cases"].append({"use_case_id": "UC-09", "title": "Idle", "actor_id": "ACT-APP", "goal": "nothing",
                           "functions": [], "rm_features": []})
    rep, _ = run(ws, monkeypatch, [b])
    pkg = json.loads((ws / OUT_JSON).read_text())
    assert rep["status"] == "PASS" and pkg["coverage"]["unused_use_cases"] == ["UC-09"]


@pytest.mark.parametrize("mutate, finding", [
    (lambda a: a["use_cases"][0]["functions"].append("HAL_SER_EnableLoop"), "not an in-scope delivered function"),
    (lambda a: a["use_cases"][0]["functions"].append("HAL_SER_Frob"), "not an in-scope delivered function"),
    (lambda a: a["use_cases"][0].update(actor_id="ACT-NOBODY"), "unknown actor"),
    (lambda a: a["use_cases"][1].update(use_case_id="UC-01"), "duplicate id"),
    (lambda a: a["use_cases"][0]["rm_features"].append("42.3.5"), "not an in-scope RM feature"),
])
def test_an_invalid_answer_is_rejected_with_the_rule(ws, monkeypatch, mutate, finding):
    from forge_factory.governance import package as P

    a = answer()
    mutate(a)
    errs = P.validate_answer(ws, a)
    assert any(finding in e for e in errs), errs


def test_owner_use_cases_are_merged_and_marked(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    spec = ser_spec()
    spec["use_cases_owner"] = [{"use_case_id": "UC-OWN-1", "title": "Poll the driver state", "actor_id": "ACT-APP",
                                "goal": "the product polls the state before a transfer",
                                "functions": ["HAL_SER_GetState"], "origin": "owner"}]
    w = prepared(tmp_path, spec, wo="WO-F020-G2")
    rep, calls = run(w, monkeypatch, [answer(drop=("HAL_SER_GetState",))])
    assert rep["status"] == "PASS" and len(calls) == 1
    pkg = json.loads((w / OUT_JSON).read_text())
    own = [u for u in pkg["use_cases"] if u["origin"] == "owner"]
    assert [u["use_case_id"] for u in own] == ["UC-OWN-1"]
    assert "UC-OWN-1" in "\n".join(m["content"] for m in calls[0]["_messages"])  # the model sees them too
