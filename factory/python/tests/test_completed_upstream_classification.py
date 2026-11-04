"""Completed internal loops retain independently proved upstream product findings."""
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_conductor as L
from forge_factory.afo import line_orders as O
from forge_factory.common import pretty_json, utc_now
from forge_factory.inspection import defects as D
from forge_factory.inspection.engine import Store


def records(root: Path):
    wo, rid = "WO-F014-CMP-SWE4-WWDGHAL-20261104-T1G", "RUN-COMPLETED-UPSTREAM"
    ws = root / "workorders" / wo / "workspace"
    files = {
        ".forge-run/manifest.json": json.dumps({"work_order": wo, "created_at": utc_now(),
            "driver": "Fixture WWDG HAL", "phase_scope": {"stop_after": "SWE.4"}}),
        "workproducts/SWE.1/software_requirements.md": "- **SWR-001** The driver shall preserve register state.\n",
        "workproducts/SWE.2/software_architecture.md": "# Architecture\nRegister state must be preserved.\n",
        "software/hal/driver.c": "int driver_state(void) { return 0; }\n",
    }
    for rel, value in files.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    store = Store(ws)
    for phase in ("SWE.1", "SWE.2", "SWE.3"):
        baseline = store.freeze(phase, f"swe{phase[-1]}-author")
    checklist = store.applicable(store.checklist("SWE.3"))
    inspection = store.record_inspection("SWE.3", "swe3-inspector", baseline["baseline_id"],
        {row["id"]: {"verdict": "FAIL", "findings": ["State preservation is not established."],
                     "evidence_refs": ["workproducts/SWE.2/software_architecture.md:1"]}
         for row in checklist["checks"]})
    defect = D.report(ws, detected_phase="SWE.3", reported_by="swe3-inspector", kind="ARCHITECTURE",
        summary="Architecture does not establish state preservation.", requirement_ids=["SWR-001"],
        test_files=[], evidence_refs=["workproducts/SWE.2/software_architecture.md:1"],
        requirement_quote="The driver shall preserve register state.")
    gate = store.gate("SWE.3")
    assert gate["decision"] == "REWORK" and gate["reason"] == inspection["inspection_id"]
    rows = [{"phase": "SWE.3", "step": "author", "result": "FROZEN"},
            {"phase": "SWE.3", "step": "inspect", "gate": gate},
            {"phase": "SWE.3", "step": "route", "gate": {"decision": "UPSTREAM", "phase": "SWE.3"}},
            {"phase": "SWE.2", "step": "upstream", "result": "NONE"}]
    path = ws / ".forge-run/gates/gate-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"ts": utc_now(), **row}) + "\n" for row in rows))
    (ws / ".forge-run/package.json").write_text(json.dumps({"package_status": "BLOCKED"}))
    (ws / ".forge-run/fabro_run_id").write_text(rid)
    run = {"id": rid, "source_directory": str(ws), "lifecycle": {"status": {"kind": "succeeded", "reason": "completed"}}}
    return ws, wo, rid, run, inspection, defect


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    root = tmp_path / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(root))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    return records(root)


def observe(value):
    ws, wo, rid, run, _, _ = value
    observer = L.Observer("cloud", fabro=L.FabroView(snapshot={rid: run}), lookback_s=86400)
    issues, _ = observer.issues(time.time(), frozenset({wo}))
    return next(row for row in issues if row["wo"] == wo)


def test_actual_store_failed_review_and_normal_defect_own_upstream_route(upstream):
    before = {p: p.read_bytes() for p in upstream[0].rglob("*") if p.is_file()}
    core = observe(upstream)
    assert core["class"] == "PRODUCT"
    assert core["proposals"][0]["strategy"] == "RETURN_TO_OWNING_UPSTREAM_PHASE"
    assert core["proposals"][0]["args"]["phase"] == "SWE.2"
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("mutation", ["failed", "cancelled", "running", "unknown", "foreign", "stale", "closed", "wrong_target", "latest_pass"])
def test_no_infra_or_unproved_review_is_promoted(upstream, mutation):
    ws, _, _, run, inspection, defect = upstream
    if mutation in ("failed", "cancelled", "running"):
        run["lifecycle"]["status"] = {"kind": mutation, "reason": "workflow_error"}
    elif mutation == "unknown":
        run.clear()
    elif mutation == "foreign":
        run["source_directory"] = str(ws.parent / "other")
    elif mutation == "stale":
        (ws / "software/hal/driver.c").write_text("int changed(void) { return 1; }\n")
    elif mutation in ("closed", "wrong_target"):
        path = ws / D.DIR / (defect["id"] + ".json")
        record = json.loads(path.read_text())
        record["status" if mutation == "closed" else "target_phase"] = "REJECTED" if mutation == "closed" else "SWE.1"
        path.write_text(pretty_json(record))
    else:
        path = ws / "inspection/SWE.3" / inspection["inspection_id"].replace("001", "002")
        doc = {**inspection, "inspection_id": inspection["inspection_id"].replace("001", "002"), "verdict": "PASS"}
        path.with_suffix(".json").write_text(pretty_json(doc))
    assert observe(upstream)["class"] == "INFRA"


@pytest.mark.parametrize("mutation", ["wrong_id", "workflow_error", "malformed_lifecycle", "malformed_status", "legacy_snapshot"])
def test_native_completion_requires_exact_source_and_terminal_metadata(upstream, mutation):
    ws, _, rid, run, _, _ = upstream
    if mutation == "wrong_id":
        run["id"] = "OTHER"
    elif mutation == "workflow_error":
        run["lifecycle"]["status"]["reason"] = "workflow_error"
    elif mutation == "malformed_lifecycle":
        run["lifecycle"] = "completed"
    elif mutation == "malformed_status":
        run["lifecycle"]["status"] = "succeeded"
    else:
        assert not L.FabroView(snapshot={rid: "succeeded:completed"}).completed(rid, ws)
        return
    assert observe(upstream)["class"] == "INFRA"


def test_unknown_native_identity_is_not_cached_as_a_permanent_refusal(upstream):
    ws, wo, rid, run, _, _ = upstream
    native = L.FabroView(snapshot={rid: {}})
    observer = L.Observer("cloud", fabro=native, lookback_s=86400)
    first, _ = observer.issues(time.time(), frozenset({wo}))
    assert next(x for x in first if x["wo"] == wo)["class"] == "INFRA"
    native.snapshot[rid] = run
    second, _ = observer.issues(time.time(), frozenset({wo}))
    assert next(x for x in second if x["wo"] == wo)["class"] == "PRODUCT"


@pytest.mark.parametrize("field", ["author_role", "inspector_role"])
def test_the_failed_review_must_retain_distinct_normal_author_and_inspector_identities(upstream, field):
    ws, _, _, _, inspection, _ = upstream
    path = ws / "inspection/SWE.3" / (inspection["inspection_id"] + ".json")
    changed = json.loads(path.read_text())
    changed[field] = "swe3-inspector" if field == "author_role" else "swe3-author"
    path.write_text(pretty_json(changed))
    assert observe(upstream)["class"] == "INFRA"


def test_queue_records_use_the_same_real_identity_bound_completion_fence(upstream):
    ws, wo, rid, run, _, _ = upstream
    real = O.RealLine.__new__(O.RealLine)
    real.host = SimpleNamespace(fabro_run=lambda requested: run)
    real.LL = SimpleNamespace(FabroUnavailable=ConnectionError)
    line = SimpleNamespace(workspace=lambda _: ws, launch_dir=lambda: None, transcripts=lambda _: [],
        verdict=lambda *args: {"verdict": "NO"}, completed_run=real.completed_run)
    records = O.Records(line, ws.parent.parent.parent / "supervisor/line-queue.sqlite3", time.time(), {})
    attempt = records.attempt(wo, "SWE.4", 7)
    assert attempt.life is None and attempt.core["class"] == "PRODUCT"
    assert attempt.core["upstream"] == ["SWE.2"]
    run["source_directory"] = str(ws / "foreign")
    assert not real.completed_run(rid, ws)


@pytest.mark.parametrize("failure_class,error_code", [
    ("TRANSIENT_DEPENDENCY", "AGENT_BACKEND_UNAVAILABLE"),
    ("SECURITY", "DENIED"), ("FACTORY_CODE_DEFECT", "HOOK_ERROR"),
    ("INFRASTRUCTURE", "SOCKET_TIMEOUT"),
])
def test_other_bundle_causes_never_use_a_current_product_finding_to_replace_their_class(upstream, monkeypatch,
                                                                                     failure_class, error_code):
    from forge_factory.afo import bundle

    ws, _, _, _, _, _ = upstream
    monkeypatch.setattr(bundle, "build", lambda *args, **kwargs: {
        "phase": "SWE.3", "failure_class": failure_class, "error_code": error_code,
        "fingerprint": "cfp1-kept-original", "evidence_refs": [], "artifact_refs": [],
    })
    monkeypatch.setattr(L.FabroView, "completed", lambda *args: (_ for _ in ()).throw(AssertionError("queried")))
    core = observe(upstream)
    assert core["class"] in ("INFRA", "UNKNOWN", "FACTORY_DEFECT")
    assert core["fingerprint"] == "cfp1-kept-original"
    assert not any(p["strategy"] == "RETURN_TO_OWNING_UPSTREAM_PHASE" for p in core["proposals"])
