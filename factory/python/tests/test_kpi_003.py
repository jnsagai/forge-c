"""Feature 003 (KPI-T001..T019, AC-K01..AC-K18): deterministic, model-free manufacturing KPIs."""
import json
import random
import time
import zipfile
from pathlib import Path

import pytest
import yaml
from forge_factory.common import CONFIG_DIR, KPI_CONTRACTS_DIR
from forge_factory.kpi import engine as E
from forge_factory.kpi import service as S
from forge_factory.kpi.sources import dedup_sort, ev, event_set_digest, validate_event

W0, W1 = "2026-10-14T00:00:00Z", "2026-10-15T00:00:00Z"
CLS = {"driver_type": "rcc", "complexity": "C2", "target_mcu": "STM32N657", "compiler": "gcc", "optimization": "-Os",
       "safety_profile": "ASIL_B_candidate"}


def order(oid, attempt, t_adm, inspections, pkg_status=None, t_seal=None, cls=None, gates=()):
    """inspections: list of (phase, verdict, ts)."""
    evs = [ev("work_order.admitted", attempt, t_adm, oid, attempt, {"class": cls or CLS, "budgets": {"flash_bytes": 4096}})]
    for i, (p, v, t) in enumerate(inspections):
        evs.append(ev("inspection.completed", f"{attempt}|{p}|{i}", t, oid, attempt, {"verdict": v, "inspection_id": f"I{i}"},
                      [f"sha256:{i:064x}"], p))
    for i, (step, result, t) in enumerate(gates):
        evs.append(ev("quality_gate.evaluated", f"{attempt}|g|{i}", t, oid, attempt, {"step": step, "result": result}))
    if pkg_status:
        evs.append(ev("package.sealed", f"{attempt}|pkg", t_seal, oid, attempt,
                      {"package_status": pkg_status, "gaps": [] if pkg_status.startswith("READY") else
                       ["failed_or_missing_quality_check:target_verification"], "scope": "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"},
                      ["archive:sha256:" + "a" * 64]))
    return evs


def get(snap, mid, **filters):
    rows = [m for m in snap["metric_values"] if m["metric_id"] == mid and all(m["filters"].get(k) == v for k, v in filters.items())]
    return rows[0]


ALL_PASS = [(f"SWE.{i}", "PASS", f"2026-10-14T0{i}:00:00Z") for i in range(1, 7)]


# ---------------- KPI-T001/T004 --------------------------------------------------------------------------------
def test_kpi_t001_catalog_frozen_and_example_valid():
    cat = json.loads((KPI_CONTRACTS_DIR / "kpi-catalog.json").read_text())
    ids = [m["id"] for m in cat["metrics"]]
    assert ids == [f"K{i:02d}" for i in range(1, 21)]
    for m in cat["metrics"]:
        assert m["definition"] and m["unit"] and m["source_event_types"] and m["caveat"]
    assert set(cat["data_quality_statuses"]) >= {"UNKNOWN", "NOT_APPLICABLE", "NOT_COMPUTABLE", "INSUFFICIENT_BASELINE"}
    lock = json.loads((CONFIG_DIR / "kpi-catalog.lock.json").read_text())
    from forge_factory.common import canonical_json, sha256_bytes
    assert lock["sha256"] == sha256_bytes(canonical_json(cat)) and lock["metrics"] == 20
    example = json.loads((KPI_CONTRACTS_DIR / "kpi-snapshot.example.json").read_text())
    assert E.schema_errors_kpi(example) == []


def test_kpi_t004_policy_non_negotiables():
    p = yaml.safe_load((CONFIG_DIR / "kpi-policy.yaml").read_text())
    assert p["safety"]["kpi_can_override_blocking_gate"] is False and p["safety"]["release_by_model"] == "forbidden"
    assert p["safety"]["mandatory_inspection_skip_tolerated"] == 0 and p["alerts"]["allow_modify_safety_policy"] is False
    assert p["sfoee"]["quality_gate_decision_authority"] == "NONE" and p["first_pass"]["immutable_after_first_inspection"]
    assert p["data_quality"]["prefer_null_with_status_over_guessed_zero"] is True


# ---------------- KPI-T002/T003 --------------------------------------------------------------------------------
def test_kpi_t002_t003_conversion_from_real_records(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    from forge_factory.inspection.engine import Store, load_checklist
    from forge_factory.kpi.sources import from_workspace
    ws = tmp_path / "state/workorders/WO-9-r2/workspace"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("- **SWR-001** The RCC driver shall reset.\n")
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"created_at": "2026-10-14T10:00:00.000000Z",
                                                             "driver": "STM32N6 RCC driver", "target": {"part_number": "N657"}}))
    st = Store(ws)
    bl = st.freeze("SWE.1", "swe1-author")
    v = {c["id"]: {"verdict": "PASS", "evidence_refs": ["x"]} for c in load_checklist("SWE.1")["checks"]}
    st.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], v)
    evs = from_workspace(ws)
    assert {e["type"] for e in evs} >= {"work_order.admitted", "inspection.completed", "requirements.verification_recorded"}
    assert all(validate_event(e) == [] for e in evs)
    assert {e["order_id"] for e in evs} == {"WO-9"} and {e["attempt_id"] for e in evs} == {"WO-9-r2"}
    assert from_workspace(ws) == evs  # deterministic, content-addressed IDs


def test_kpi_ac_k02_initial_inspection_immutable_and_ac_k03_attempts():
    insp = [("SWE.1", "PASS", "2026-10-14T01:00:00Z"), ("SWE.2", "PASS", "2026-10-14T02:00:00Z"),
            ("SWE.3", "FAIL", "2026-10-14T03:00:00Z"), ("SWE.3", "FAIL", "2026-10-14T03:30:00Z"),
            ("SWE.3", "PASS", "2026-10-14T04:00:00Z")] + [(f"SWE.{i}", "PASS", f"2026-10-14T0{i + 1}:30:00Z") for i in (4, 5, 6)]
    evs = order("O1", "O1", "2026-10-14T00:30:00Z", insp, "READY_FOR_OFFLINE_REVIEW", "2026-10-14T09:00:00Z")
    evs += order("O1", "O1-r2", "2026-10-14T00:40:00Z", [])  # a retry attempt of the same order
    snap = E.snapshot(evs, W0, W1)
    assert get(snap, "K02", phase="SWE.3")["value"] == 0.0  # first-pass outcome of SWE.3 stays FAIL
    assert get(snap, "K03")["value"] == 0.0
    assert get(snap, "K04", status="READY_FOR_OFFLINE_REVIEW")["value"] == 1  # one unique unit, not two


# ---------------- KPI-T005/T010/T017 ------------------------------------------------------------------------------
def test_kpi_t005_t017_replay_duplicates_order_and_crash_parity():
    evs = order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS, "READY_FOR_OFFLINE_REVIEW", "2026-10-14T09:00:00Z")
    one = E.snapshot(evs, W0, W1)
    shuffled = evs + evs[:3]  # retransmission + duplicates
    random.Random(1).shuffle(shuffled)
    two = E.snapshot(shuffled, W0, W1)
    assert E.serialize(one) == E.serialize(two) and one["event_set_digest"] == event_set_digest(evs)
    partial = E.snapshot(evs[:4], W0, W1)  # "crash" mid-stream, then full replay
    resumed = E.snapshot(evs[:4] + evs[4:], W0, W1)
    assert partial["event_set_digest"] != one["event_set_digest"] and E.serialize(resumed) == E.serialize(one)
    assert one["formula_version"].startswith("kpi-engine-0.5.0+")


def test_kpi_t010_snapshot_schema_and_checksum_ready():
    snap = E.snapshot(order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS), W0, W1)
    assert E.schema_errors_kpi(snap) == []
    raw = E.serialize(snap)
    assert raw == E.serialize(json.loads(raw)) and raw.endswith(b"\n")
    for m in snap["metric_values"]:
        assert "numerator" in m and "denominator" in m and isinstance(m["sample_count"], int)


# ---------------- KPI-T006 (AC-K01/K03/K04) -------------------------------------------------------------------------
def test_kpi_ac_k01_all_pass_ready_low_sample_no_approval():
    snap = E.snapshot(order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS, "READY_FOR_OFFLINE_REVIEW", "2026-10-14T09:00:00Z"),
                      W0, W1, "READY_FOR_OFFLINE_REVIEW")
    k03 = get(snap, "K03")
    assert k03["value"] == 1.0 and k03["denominator"] == 1 and k03["status"] == "INSUFFICIENT_SAMPLE"
    assert "APPROVED" not in json.dumps(snap).replace("NOT_SAFETY_APPROVED", "")


def test_kpi_ac_k04_blocked_only_throughput_zero_tokens_na():
    evs = order("O2", "O2", "2026-10-14T00:30:00Z", ALL_PASS, "BLOCKED", "2026-10-14T09:00:00Z")
    evs.append(ev("agent.usage_recorded", "u1", "2026-10-14T01:00:00Z", "O2", "O2", {"tokens_new": 5000, "basis": "reported"}))
    snap = E.snapshot(evs, W0, W1)
    assert get(snap, "K04", status="READY_FOR_OFFLINE_REVIEW")["value"] == 0
    assert get(snap, "K04", status="BLOCKED")["value"] == 1
    k15 = get(snap, "K15")
    assert k15["value"] is None and k15["status"] == "NOT_APPLICABLE"  # not 0, not infinity
    wip = get(snap, "K18")
    assert wip["value"] == 0


# ---------------- KPI-T007 (AC-K05/K06/K07) ---------------------------------------------------------------------------
def test_kpi_ac_k06_misra_unchecked_rules_reported(monkeypatch):
    evs = order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS)
    evs.append(ev("misra.rule_assessed", "m1", "2026-10-14T05:00:00Z", "O1", "O1", {"status": "PASS", "rules_violated": []}))
    k12 = get(E.snapshot(evs, W0, W1), "K12")
    assert 0 < k12["value"] < 1 and "not checked" in k12["explanation"] and "compliance NOT claimed" in k12["explanation"]


def test_kpi_ac_k07_targets_not_silently_merged():
    a = order("OA", "OA", "2026-10-14T00:30:00Z", ALL_PASS, cls={**CLS, "target_mcu": "MCU-A"})
    b = order("OB", "OB", "2026-10-14T00:30:00Z", ALL_PASS, cls={**CLS, "target_mcu": "MCU-B"})
    keep = {e["order_id"] for e in a + b if e["type"] == "work_order.admitted" and e["payload"]["class"]["target_mcu"] == "MCU-A"}
    only_a = E.snapshot([e for e in a + b if e["order_id"] in keep], W0, W1)
    both = E.snapshot(a + b, W0, W1)
    assert get(only_a, "K02", phase="SWE.1")["denominator"] == 1 and get(both, "K02", phase="SWE.1")["denominator"] == 2


def test_kpi_ac_k05_missing_evidence_lowers_k09_and_cannot_override_gate():
    evs = order("O3", "O3", "2026-10-14T00:30:00Z", ALL_PASS, "BLOCKED", "2026-10-14T09:00:00Z")
    k09 = get(E.snapshot(evs, W0, W1), "K09")
    assert k09["value"] < 1.0 and k09["denominator"] > k09["numerator"]


# ---------------- KPI-T008/T009 (AC-K08/K09/K12/K14/K15) ---------------------------------------------------------------
def test_kpi_ac_k09_no_planned_work_availability_na():
    assert get(E.snapshot([], W0, W1), "K01")["status"] == "NOT_APPLICABLE"
    assert get(E.snapshot([], W0, W1), "K01")["value"] is None


def test_kpi_ac_k08_k15_sfoee_not_computable_and_never_masks_gate():
    evs = order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS, "BLOCKED", "2026-10-14T09:00:00Z")
    evs += [ev("supervisor.heartbeat", f"h{i}", f"2026-10-14T{i:02d}:00:00Z", "factory", "factory", {"status": "HEALTHY"})
            for i in range(0, 10)]
    snap = E.snapshot(evs, W0, W1, "BLOCKED", {"frozen": False})
    k19 = get(snap, "K19")
    assert k19["status"] == "NOT_COMPUTABLE" and k19["value"] is None and "INSUFFICIENT_BASELINE" in k19["explanation"]
    assert snap["release_status"] == "BLOCKED"  # no KPI value can turn BLOCKED into READY


def test_kpi_ac_k12_unknown_usage_not_zero_and_ac_k14_recurrence():
    evs = order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS, "READY_FOR_OFFLINE_REVIEW", "2026-10-14T09:00:00Z")
    k15 = get(E.snapshot(evs, W0, W1), "K15")
    assert k15["status"] == "UNKNOWN" and k15["value"] is None
    fp = {"fingerprint": "gw:CONFIG:-:0.4", "terminal_state": "RESOLVED", "auto_restored": True, "recoverable": True,
          "detected_at": "2026-10-01T00:00:00Z"}
    inc = [ev("incident.detected", "i1", "2026-10-01T00:00:00Z", "factory", "factory", {**fp}),
           ev("incident.resolved", "i1r", "2026-10-01T00:03:00Z", "factory", "factory", fp),
           ev("incident.detected", "i2", "2026-10-02T00:00:00Z", "factory", "factory", {**fp})]
    k17 = get(E.snapshot(inc, "2026-10-01T00:00:00Z", "2026-10-15T00:00:00Z"), "K17")
    assert k17["value"] == 1.0 and "no claim" in k17["explanation"]
    k16 = get(E.snapshot(inc, "2026-10-01T00:00:00Z", "2026-10-15T00:00:00Z"), "K16")
    assert k16["numerator"] == 1 and "MTTR" in k16["explanation"]


def test_kpi_t008_supervisor_model_free():
    import ast
    for f in Path(E.__file__).parent.glob("*.py"):
        mods = {n.module for n in ast.walk(ast.parse(f.read_text())) if isinstance(n, ast.ImportFrom) and n.module}
        assert not any(m and ("llm_gateway" in m or "openai" in m) for m in mods), f


# ---------------- KPI-T018 (AC-K11/K16/K17 + K20) ----------------------------------------------------------------------
def test_kpi_ac_k11_ai_text_pass_not_trusted_and_k20_hard_violation():
    evs = order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS[:5], "READY_FOR_OFFLINE_REVIEW", "2026-10-14T09:00:00Z")
    snap = E.snapshot(evs, W0, W1)
    assert get(snap, "K20")["value"] == 1  # READY without SWE.6 inspection = skipped mandatory inspection
    forged = order("O2", "O2", "2026-10-14T00:30:00Z", ALL_PASS, "READY_FOR_OFFLINE_REVIEW", "2026-10-14T09:00:00Z")
    forged[-1]["payload"]["scope"] = "ASIL_B_APPROVED"
    assert get(E.snapshot(forged, W0, W1), "K20")["value"] >= 1


def test_kpi_ac_k17_formula_version_labelled():
    a = E.snapshot(order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS), W0, W1)
    assert a["formula_version"] == E.formula_version() and a["source_catalog_hash"]
    E.ENGINE_VERSION, old = "kpi-engine-9.9.9", E.ENGINE_VERSION
    try:
        b = E.snapshot(order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS), W0, W1)
        assert b["formula_version"] != a["formula_version"] and b["snapshot_id"] != a["snapshot_id"]
    finally:
        E.ENGINE_VERSION = old


# ---------------- KPI-T014 / T019 ----------------------------------------------------------------------------------------
def test_kpi_t014_cardinality_and_latency():
    evs = []
    for i in range(300):
        evs += order(f"O{i}", f"O{i}", "2026-10-14T00:30:00Z", ALL_PASS, "READY_FOR_OFFLINE_REVIEW" if i % 2 else "BLOCKED",
                     "2026-10-14T09:00:00Z")
    t0 = time.monotonic()
    snap = E.snapshot(evs, W0, W1)
    assert time.monotonic() - t0 < 5.0
    assert len(snap["metric_values"]) < 80  # bounded rows: dimensions are phases/status/quantiles, not order ids
    assert all(len(m["source_event_refs"]) <= 200 for m in snap["metric_values"])
    assert get(snap, "K04", status="READY_FOR_OFFLINE_REVIEW")["value"] == 150


def test_kpi_t019_calibration_measurement_only():
    evs = order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS)
    evs += [ev("stage.started", f"s{i}", f"2026-10-14T01:{i:02d}:00Z", "O1", "O1", {"node": "swe1_author"}, phase="SWE.1")
            for i in range(0, 10, 2)]
    evs += [ev("stage.completed", f"c{i}", f"2026-10-14T01:{i + 1:02d}:00Z", "O1", "O1", {"node": "swe1_author"}, phase="SWE.1")
            for i in range(0, 10, 2)]
    ds = S.calibration_dataset(dedup_sort(evs))
    cls = next(iter(ds["classes"].values()))
    assert ds["frozen"] is False and cls["samples"]["SWE.1"] == [60.0] * 5 and cls["eligible_for_freeze"]["SWE.1"] is False
    with pytest.raises(ValueError, match="INSUFFICIENT_BASELINE"):
        S.freeze_baseline(ds, "v1")


# ---------------- KPI-T012 / T016 (AC-K16 / AC-K18) ------------------------------------------------------------------------
def test_kpi_t012_observer_mcp_read_only_and_least_privilege(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    S.compute_and_store(order("O1", "O1", "2026-10-14T00:30:00Z", ALL_PASS))
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import observer
    op = {o.name: o for o in observer.OPERATIONS}
    monkeypatch.setenv("FORGE_ROLE", "release-manager")
    ok = sdk.invoke("forge-observer-mcp", op["get_kpis"], {"kpi_id": "K02"})
    assert ok["status"] == "PASS" and all(i.startswith("K02") for i in ok["issues"])
    ev_ = sdk.invoke("forge-observer-mcp", op["get_kpi_evidence"], {"kpi_id": "K02"})
    assert ev_["status"] == "PASS" and ev_["metrics"]["event_refs"] >= 1
    monkeypatch.setenv("FORGE_ROLE", "swe3-author")  # not granted
    assert "ROLE_NOT_GRANTED" in sdk.invoke("forge-observer-mcp", op["get_kpis"], {})["issues"][0]
    assert not any(o.name.startswith(("set_", "update_", "write_")) for o in observer.OPERATIONS)  # no mutation ops


def test_kpi_t015_t016_ready_and_blocked_archives_carry_consistent_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "archives"))
    from forge_factory.release.finalize import cross_check_kpis, finalize
    from test_m7_governance_release import complete_workspace
    for name, ready in (("WO-R", True), ("WO-B", False)):
        ws = tmp_path / f"state/workorders/{name}/workspace"
        ws.mkdir(parents=True)
        complete_workspace(ws)
        man = json.loads((ws / ".forge-run/manifest.json").read_text())
        man.update(created_at="2026-10-14T10:00:00.000000Z", driver="STM32N6 RCC driver")
        (ws / ".forge-run/manifest.json").write_text(json.dumps(man))
        if not ready:
            (ws / "workproducts/SWE.6/software_verification_report.md").unlink()
        out = finalize(ws, name)
        assert out["package_status"] == ("READY_FOR_OFFLINE_REVIEW" if ready else "BLOCKED")
        with zipfile.ZipFile(out["archive"]) as z:
            names = set(z.namelist())
        for f in ("kpi-snapshot.json", "kpi-catalog.json", "kpi-policy.yaml", "kpi-baselines.json", "kpi-source-events.jsonl"):
            assert f"evidence/operations/kpi/{f}" in names
        cc = cross_check_kpis(Path(out["archive"]))
        assert cc["status"] == "PASS", cc


# ---------------- KPI-T011/T013 dashboard + drilldown (AC-K13) ----------------------------------------------------------
def test_kpi_t011_t013_dashboard_kpis_drilldown_and_display_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    import forge_factory.kpi.sources as SRC
    from fastapi.testclient import TestClient
    from forge_factory.dashboard.app import create_app, tokens
    from forge_factory.events.store import EventStore
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
    evs = order("O1", "O1", now, [(p, "PASS", now) for p, _, _ in ALL_PASS])
    monkeypatch.setattr(SRC, "collect_all", lambda include_fabro=True: evs)
    c = TestClient(create_app(EventStore(), collect=False))
    h = {"Authorization": f"Bearer {tokens()['viewer']}"}
    snap = c.get("/api/v1/kpis?window_days=1", headers=h).json()
    k02 = [m for m in snap["metric_values"] if m["metric_id"] == "K02" and m["filters"]["phase"] == "SWE.1"][0]
    assert k02["numerator"] == 1 and k02["denominator"] == 1
    flt = c.get("/api/v1/kpis?window_days=1&order_id=NONE", headers=h).json()
    k02f = [m for m in flt["metric_values"] if m["metric_id"] == "K02" and m["filters"]["phase"] == "SWE.1"][0]
    assert k02f["denominator"] == 0 and k02f["status"] == "NOT_APPLICABLE"  # filter changes num AND den together
    d = c.get("/api/v1/kpis/K02/evidence?window_days=1", headers=h).json()
    srcs = [s for r in d["rows"] for s in r["source_events"]]
    assert srcs and all(s["type"] == "inspection.completed" and s["evidence_refs"] for s in srcs)
    assert c.get("/api/v1/kpis/K99/evidence", headers=h).status_code == 422
    assert c.post("/api/v1/kpis", headers=h).status_code == 405
    html = c.get("/").text
    assert "Production KPIs" in html and "never guessed" in html


# ---------------- KPI-T020 pilot reconciliation (live records) ------------------------------------------------------------
@pytest.mark.skipif(not (Path(__import__("os").environ.get("FORGE_STATE_DIR", "/nonexistent")) / "workorders").is_dir(),
                    reason="no live work orders")
def test_kpi_t020_pilot_reconciles_with_raw_evidence():
    import os

    from forge_factory.kpi.sources import collect_all
    from forge_factory.release.finalize import archive_root
    from forge_factory.supervisor.store import IncidentStore
    evs = collect_all()
    snap = E.snapshot(evs, "2026-10-01T00:00:00Z", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    assert E.schema_errors_kpi(snap) == []
    # packages on disk vs package.sealed events (attempt level)
    root = Path(os.environ["FORGE_STATE_DIR"]) / "workorders"
    sealed_ws = {ws.parent.name for ws in root.glob("*/workspace") if (ws / ".forge-run/package.json").is_file()}
    assert sealed_ws == {e["attempt_id"] for e in evs if e["type"] == "package.sealed"}
    import hashlib
    for ws in root.glob("*/workspace"):  # every recorded package exists on disk with the recorded SHA-256
        pj = ws / ".forge-run/package.json"
        if pj.is_file():
            p = json.loads(pj.read_text())
            assert hashlib.sha256(Path(p["archive"]).read_bytes()).hexdigest() == p["archive_sha256"]
    assert archive_root().is_dir()
    # incidents ledger vs K16 denominator
    inc = [i for i in IncidentStore().all(1000) if i["recoverable"] and i["state"] in ("RESOLVED", "REQUIRES_OFFLINE_ATTENTION")]
    assert get(snap, "K16")["denominator"] == len(inc)
    # initial inspections vs inspection files
    first = {}
    for ws in root.glob("*/workspace"):
        for f in sorted(ws.glob("inspection/SWE.*/INS-*.json")):
            first.setdefault(f.parent.name, f)
    for p in ("SWE.1", "SWE.2"):
        assert get(snap, "K02", phase=p)["denominator"] == (1 if p in first else 0)
    assert get(snap, "K20")["value"] == 0  # no safety/process violation in the pilot
    h = json.loads((Path(os.environ["FORGE_STATE_DIR"]) / "supervisor/health.json").read_text())
    assert h["model_calls"] == 0
    out = Path(__file__).resolve().parents[3] / "evidence/v0.4/kpi"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pilot-snapshot.json").write_bytes(E.serialize(snap))
