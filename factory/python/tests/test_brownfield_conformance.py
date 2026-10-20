"""Feature 008 US2 - requirements written without the code (FR-007) and conformance of the delivered code to them
(FR-008, SC-002): the five seeded mismatch kinds each give the right finding; an unmodified delivery gives none."""
import json

import pytest
from brownfield_fixtures import HEADER, MUTANTS, add_contract, example_copy, pass_swe1, scope_for
from forge_factory import workorder as WO
from forge_factory.brownfield import conformance as C
from forge_factory.brownfield.inject import inject
from forge_factory.policy.authz import Authorizer, Binding


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


def _prepared(tmp_path, wo, header=HEADER, scope=None):
    mutate = (lambda s: s["delivery"]["scope"].update(functions=scope)) if scope else None
    return WO.prepare(example_copy(tmp_path, header=header, mutate=mutate, name=wo), wo)


def test_inject_refuses_before_swe1_passes(tmp_path):
    ws, _ = _prepared(tmp_path, "WO-I-1")
    r = inject(ws)
    assert r["status"] == "REFUSED" and any(i.startswith("SWE1_NOT_PASSED") for i in r["issues"])
    assert not (ws / "software/ll/stm32n6xx_ll_rcc.h").exists()


def test_inject_after_swe1_records_the_frozen_baseline(tmp_path, monkeypatch):
    ws, man = _prepared(tmp_path, "WO-I-2")
    pass_swe1(monkeypatch)
    r = inject(ws)
    assert r["status"] == "INJECTED" and r["swe1_baseline_id"] == "BL-SWE.1-001"
    h = ws / "software/ll/stm32n6xx_ll_rcc.h"
    assert h.read_text() == HEADER and h.stat().st_mode & 0o222 == 0
    rec = json.loads((ws / ".forge-run/delivery/injection.json").read_text())
    assert rec["swe1_baseline_hash"] == "h" * 64 and {f["path"] for f in rec["files"]} == {d["path"] for d in man["delivered"]}
    assert (ws / ".forge-run/delivery/scope.json").is_file()
    assert inject(ws)["status"] == "ALREADY_INJECTED"


def test_inject_refuses_a_tampered_store(tmp_path, monkeypatch):
    from forge_factory.brownfield import delivery as D

    ws, _ = _prepared(tmp_path, "WO-I-3")
    f = D.store_dir("WO-I-3") / "files/software/ll/stm32n6xx_ll_rcc.h"
    f.chmod(0o644)
    f.write_text(HEADER + "/* tampered */\n")
    pass_swe1(monkeypatch)
    assert "DELIVERY_STORE_MISMATCH:software/ll/stm32n6xx_ll_rcc.h" in inject(ws)["issues"]


def _auth(ws, node, role, phase):
    return Authorizer(Binding("WO", str(ws), {node: {"role": role, "phase": phase}}))


def test_requirement_authors_cannot_read_delivered_code(tmp_path, monkeypatch):
    ws, _ = _prepared(tmp_path, "WO-I-4")
    pass_swe1(monkeypatch)
    inject(ws)
    swe1 = _auth(ws, "swe1_author", "swe1-author", "SWE.1")
    d = swe1.decide("swe1_author", "read_file", {"path": "software/ll/stm32n6xx_ll_rcc.h"})
    assert not d.allow and d.code == "DELIVERED_CODE_HIDDEN_FROM_REQUIREMENTS"
    for tool, root in (("grep", "."), ("glob", "software"), ("list_dir", "software/ll")):
        assert not swe1.decide("swe1_author", tool, {"path": root}).allow, (tool, root)
    assert not swe1.decide("swe1_author", "read_file", {"path": ".forge-run/delivery/scope.json"}).allow
    assert swe1.decide("swe1_author", "read_file", {"path": "inputs/index.md"}).allow
    assert swe1.decide("swe1_author", "glob", {"path": "inputs/sections"}).allow
    swe2 = _auth(ws, "swe2_author", "swe2-author", "SWE.2")
    assert swe2.decide("swe2_author", "read_file", {"path": "software/ll/stm32n6xx_ll_rcc.h"}).allow


def _conformance(tmp_path, wo, header, scope):
    ws, _ = _prepared(tmp_path, wo, header, scope)
    add_contract(ws)
    from forge_factory.inspection import engine

    real = engine.Store.gate, engine.Store.latest_baseline
    engine.Store.gate = lambda self, ph: {"decision": "PASS"}
    engine.Store.latest_baseline = lambda self, ph: {"baseline_id": "BL-SWE.1-001", "baseline_hash": "h" * 64}
    try:
        assert inject(ws)["status"] == "INJECTED"
    finally:
        engine.Store.gate, engine.Store.latest_baseline = real
    return C.check(ws, "SWE.3")


def test_unmodified_delivery_is_conformant(tmp_path):
    r = _conformance(tmp_path, "WO-C-0", HEADER, None)
    assert r["status"] == "CONFORMANT" and r["findings"] == []


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_each_seeded_mismatch_gives_its_finding_kind(tmp_path, name):
    mutate, change, kind, fn = MUTANTS[name]
    r = _conformance(tmp_path, f"WO-C-{name}", mutate(HEADER), scope_for(change) if change else None)
    assert r["status"] == "FINDINGS"
    kinds = {(f["kind"], f["function"]) for f in r["findings"]}
    assert (kind, fn) in kinds, kinds
    assert {k for k, _ in kinds} == {kind}  # exactly the expected kind of finding (SC-002)
    rec = json.loads((tmp_path / "state/workorders" / f"WO-C-{name}" / "workspace/.forge-run/delivery/"
                      "conformance.json").read_text())
    assert rec["schema"] == "forge-c/conformance/0.1" and all(f["status"] == "OPEN" for f in rec["findings"])


def test_api_call_none_is_no_code_and_not_a_contract_error(tmp_path):
    from forge_factory.assurance import register_contract as RC

    ws, _ = _prepared(tmp_path, "WO-C-N")
    add_contract(ws)
    calls = json.loads((ws / "workproducts/SWE.2/api_calls.json").read_text())
    calls["calls"]["HSE_READY_QUERY"] = {"function": "NONE", "args": []}
    (ws / "workproducts/SWE.2/api_calls.json").write_text(json.dumps(calls))
    assert not any("HSE_READY_QUERY" in x for x in RC.check_calls(ws))
    assert all(c["case"] != "HSE_READY_QUERY" for c in RC.cases(ws)[0])
