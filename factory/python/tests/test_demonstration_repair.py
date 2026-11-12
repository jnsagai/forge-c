"""Bounded, durable author loopbacks and honest provisional LL imports; no model calls."""
import json

import pytest
from forge_factory import development_demonstration as demo
from forge_factory import development_execution as D
from forge_factory import workorder as W
from forge_factory.common import pretty_json
from forge_factory.inspection import gate
from forge_factory.inspection.engine import PHASES, Store
from forge_factory.lrtx import profile
from forge_factory.workflow.builder import build
from test_pipeline_demonstration import EXAMPLE, failed_requirements


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    for name in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + name + "_DIR", str(tmp_path / name))
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    return W.prepare(EXAMPLE, "WO-DEMO-REPAIR", purpose="QM", execution_policy=D.DEMO_REPAIR)


@pytest.mark.parametrize("kind", ["LL", "HAL"])
@pytest.mark.parametrize("peripheral", ["rcc", "iwdg"])
def test_graph_has_real_bounded_author_return_paths_for_every_phase(kind, peripheral, prepared):
    import os
    import re
    import subprocess
    from pathlib import Path

    policy = D.binding(D.DEMO_REPAIR, "QM")
    prof = profile.load("local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp")
    manifest = {**prepared[1], "layer": kind, "peripheral": peripheral, "development_execution": policy}
    from forge_factory.inspection import assessment_context

    manifest[assessment_context.FIELD] = assessment_context.binding(manifest)
    settings = W.local_profile_structured(prof, manifest, prof["models"]["default"])
    graph, nodes = build("WO-DEMO-GRAPH", layer=kind, peripheral=peripheral,
                         execution_policy=policy, structured=settings, assessment_manifest=manifest)
    edges = re.findall(r'^  (\w+) -> (\w+)(?: \[condition="([^"]+)"\])?$', graph, re.M)
    for n in range(1, 7):
        route = f"swe{n}_demo_repair"
        branches = [(dst, cond) for src, dst, cond in edges if src == route]
        assert len(branches) == 2
        author = next(dst for dst, cond in branches if cond == "outcome=succeeded")
        assert nodes[author] == {"role": f"swe{n}-author", "phase": f"SWE.{n}"}
        assert author == ({4: "swe4_test_author", 5: "swe5_target_author", 6: "swe6_test_author"}.get(n, author))
        assert (f"swe{n}_inspect_gate", route, "") in edges
        assert any(src == f"swe{n}_author_gate" for src, _, _ in edges)
        assert f'{route} [shape=parallelogram' in graph and 'max_visits=3' in graph
    assert "at most two phase correction cycles" in graph
    assert policy["max_phase_repair_passes"] == 2 and policy["max_task_calls"] == 9
    with pytest.raises(ValueError, match="POLICY_INVALID"):
        D.binding(D.DEMO_REPAIR, "ASPICE_ONLY")
    fabro = Path(os.environ.get("FORGE_FABRO_BIN", str(Path.home() / ".fabro/bin/fabro")))
    if not fabro.is_file():
        pytest.skip("Fabro graph parser unavailable; structural assertions above passed")
    graph_path = prepared[0] / "bounded-demo.fabro"
    graph_path.write_text(graph)
    result = subprocess.run([str(fabro), "validate", str(graph_path)], capture_output=True, text=True,
                            env={**os.environ, "HOME": str(prepared[0]), "FABRO_NO_UPGRADE_CHECK": "1"}, timeout=120)
    assert "Validation: OK" in result.stdout + result.stderr, (result.stdout + result.stderr)[-1000:]


def test_failed_review_gets_two_repairs_then_advances_with_original_failure_preserved(prepared, monkeypatch):
    ws, _ = prepared
    _, failed = failed_requirements(ws, monkeypatch)
    before = Store(ws).inspections("SWE.1")
    decisions = []
    for _ in range(3):
        gate._state(ws, "SWE.1", {"step": "inspect", "gate": Store(ws).gate("SWE.1")})
        decisions.append(demo.repair_route(Store(ws), "SWE.1"))
    assert decisions == [0, 0, 1]
    assert Store(ws).inspections("SWE.1") == before and before[-1] == failed
    assert demo.repair_route(Store(ws), "SWE.1") == 1  # Restart does not refill.
    state = json.loads((ws / ".forge-run/lrtx/SWE.1/development-execution.json").read_text())
    assert state["phase_reworks"] == 2
    gaps = [json.loads(line) for line in (ws / ".forge-run/advisory/SWE.1.jsonl").read_text().splitlines()]
    assert gaps[-1]["gate"]["decision"] == "ADVISORY_CONTINUE"
    assert gaps[-1]["unresolved_findings"] and Store(ws).gate("SWE.1")["decision"] != "PASS"


def test_missing_outputs_still_exhaust_two_repairs_and_advance(prepared):
    ws, _ = prepared
    store = Store(ws)
    assert store.latest_baseline("SWE.6") is None
    decisions = []
    for _ in range(3):
        gate._state(ws, "SWE.6", {"step": "inspect", "gate": store.gate("SWE.6")})
        decisions.append(demo.repair_route(store, "SWE.6"))
    assert decisions == [0, 0, 1]
    assert store.latest_baseline("SWE.6") is None
    assert json.loads((ws / ".forge-run/advisory/SWE.6.jsonl").read_text())["baseline_id"] is None


def test_pass_does_not_spend_repairs_but_failed_author_or_tool_requires_correction(prepared, monkeypatch):
    ws, _ = prepared
    store = Store(ws)
    monkeypatch.setattr(Store, "gate", lambda self, phase: {"decision": "PASS", "reason": "fixture",
                                                            "failed_inspections": 0, "max_rework_cycles": 3})
    gate._state(ws, "SWE.3", {"step": "author", "result": "FROZEN"})
    gate._state(ws, "SWE.3", {"step": "verify", "check": "delivery", "verdict": "PASS"})
    assert demo.repair_route(store, "SWE.3") == 1
    gate._state(ws, "SWE.3", {"step": "verify", "check": "hal_guideline", "verdict": "FAIL"})
    assert demo.repair_route(store, "SWE.3") == 0
    gate._state(ws, "SWE.3", {"step": "verify", "check": "hal_guideline", "verdict": "PASS"})
    assert demo.repair_route(store, "SWE.3") == 1
    gate._state(ws, "SWE.3", {"step": "author", "result": "REJECTED", "issues": ["actual fixture tool failure"]})
    assert demo.repair_route(store, "SWE.3") == 0


def test_route_replay_does_not_spend_a_second_correction_cycle(prepared):
    ws, _ = prepared
    store = Store(ws)
    gate._state(ws, "SWE.6", {"step": "inspect", "gate": store.gate("SWE.6")})
    assert demo.repair_route(store, "SWE.6") == 0
    assert demo.repair_route(Store(ws), "SWE.6") == 0
    state = json.loads((ws / ".forge-run/lrtx/SWE.6/development-execution.json").read_text())
    assert state["phase_reworks"] == 1


def test_task_call_accounting_is_durable_and_legacy_bindings_remain_exact(prepared):
    ws, _ = prepared
    packet = {"phase": "SWE.1", "role": "swe1-author", "task": "requirements:one"}
    assert all(D.reserve_call(ws, packet) for _ in range(9))
    assert not D.reserve_call(ws, packet)
    assert not D.reserve_call(ws, {**packet, "findings": ["changed"]})
    path = ws / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    legacy = {**D.binding(D.DEMO, "QM"), "validator_sha256": D.LEGACY_VALIDATOR}
    manifest["development_execution"] = legacy
    path.write_text(pretty_json(manifest))
    assert D.selected(ws) == legacy
    legacy["max_task_calls"] = 2
    path.write_text(pretty_json(manifest))
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        D.selected(ws)
    manifest["development_execution"] = {**D.binding(D.DEMO_REPAIR, "QM"), "validator_sha256": D.LEGACY_VALIDATOR}
    path.write_text(pretty_json(manifest))
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        D.selected(ws)


def test_provisional_ll_import_is_sealed_read_only_and_never_a_formal_acceptance(prepared, monkeypatch):
    from forge_factory.brownfield.inject import inject

    ws, _ = prepared
    anchor, failed = failed_requirements(ws, monkeypatch)
    assert inject(ws)["status"] == "INJECTED"
    anchor.architecture()
    anchor.implementation()
    store = Store(ws)
    for phase in PHASES:
        demo.snapshot(store, phase)
    data, record = demo.provided_ll(ws.parent.name, "crc")
    assert data and record["qualification"] == "PROVISIONAL_QM_DEMONSTRATION_ONLY"
    assert record["quality_accepted"] is False and record["source_phase_gates"]["SWE.1"] != "PASS"
    assert Store(ws).inspections("SWE.1")[-1] == failed
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_VERIFIED"):
        W.provided_ll(ws.parent.name, "crc")
    header = ws / record["path"]
    header.chmod(0o644)
    header.write_bytes(data + b"\n/* unsealed change */\n")
    with pytest.raises(ValueError, match="IMPLEMENTATION_UNSEALED"):
        demo.provided_ll(ws.parent.name, "crc")


def test_actual_hal_intake_limits_provisional_component_to_qm_demonstrations(tmp_path, monkeypatch):
    from forge_factory.common import REPO_ROOT
    from forge_factory.layer import ll_header

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    source, _ = W.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-PROVISIONAL-SOURCE",
                          purpose="QM", execution_policy=D.DEMO_REPAIR)
    # Synthetic engineering artifacts exercise intake/immutability, never driver correctness.
    for relative, text in {
        "workproducts/SWE.1/software_requirements.md": "# Synthetic requirement fixture\n",
        "workproducts/SWE.2/architecture.md": "# Synthetic architecture fixture\n",
        ll_header(source): "/* Synthetic provisional driver fixture; not verified. */\n",
    }.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    store = Store(source)
    for phase in PHASES:
        demo.snapshot(store, phase)
    example = REPO_ROOT / "examples/0002b-arm_55_rcc_hal"
    destination, manifest = W.prepare(example, "WO-PROVISIONAL-HAL", source.parent.name,
                                      purpose="QM", execution_policy=D.DEMO_REPAIR)
    provided = manifest["provided"][0]
    assert provided["qualification"] == "PROVISIONAL_QM_DEMONSTRATION_ONLY" and not provided["quality_accepted"]
    assert (destination / provided["path"]).read_bytes() == (source / provided["path"]).read_bytes()
    assert (destination / provided["path"]).stat().st_mode & 0o222 == 0
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_VERIFIED"):
        W.prepare(example, "WO-STRICT-HAL", source.parent.name, purpose="QM")
    with pytest.raises(ValueError, match="SOURCE_SCOPE_MISMATCH"):
        demo.provided_ll(source.parent.name, "iwdg")
    with pytest.raises(ValueError, match="SOURCE_INVALID"):
        demo.provided_ll("../WO-PROVISIONAL-SOURCE", "rcc")
