"""Independent observer fixtures exercise real read-only SQLite, artifacts and HTTP.

Synthetic clocks/unit observations below are deterministic tests, never soak proof.
"""

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import fault_observer as O
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file
from test_da014_qualification import identity


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "data/state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    root = tmp_path / "data"
    root.mkdir()
    db = root / "state/conductor/conductor.sqlite3"
    store = Store(db)
    m = MissionLedger(store)
    m.register(
        "fixture-mission",
        "bounded-fixture",
        {
            "max_attempts": 1,
            "max_jobs": 2,
            "max_requests": 2,
            "max_tokens": 1000,
            "max_tools": 0,
            "max_corrections": 0,
            "deadline": 9999999999,
        },
        "fixture-auth",
        authorize=lambda *a: True,
    )
    m.execution("fixture-mission", "fixture-job", "DIAGNOSIS", reserved_tokens=500)
    intent = tmp_path / "intent.json"
    immutable_json(intent, {"mode": "RUNNING", "epoch": 3})
    raw = {
        "schema": "forge-c/operational-observer-plan/1",
        "database": str(db),
        "intent": str(intent),
        "data_root": str(root),
        "evidence_root": str(tmp_path),
        "heartbeat": str(root / "state/afo/conductor.heartbeat"),
        "mount_uuid": "12345678-abcd",
        "health_urls": {"fabro": "http://127.0.0.1:32291/health", "gateway": "http://127.0.0.1:11456/health"},
        "unit": "forge-conductor.service",
        "max_rows": 100,
        "observer_source_sha256": sha256_file(Path(O.__file__)),
    }
    path = tmp_path / "plan.json"
    immutable_json(path, raw)
    ref = {"path": str(path), "sha256": sha256_file(path)}
    manifest = Q.freeze("operation-24", tmp_path / "manifest.json", identity=identity(), inputs=[path])
    monkeypatch.setattr(
        O,
        "unit_status",
        lambda _: {
            "MainPID": "12345",
            "ControlGroup": "/observer-fixture-separate.service",
            "ActiveState": "active",
            "NRestarts": "0",
            "Result": "success",
            "SubState": "running",
        },
    )
    monkeypatch.setattr(O, "health", lambda *a: dict.fromkeys(("conductor", "fabro", "gateway", "data_volume"), True))
    return SimpleNamespace(root=root, db=db, store=store, mission=m, manifest=manifest, ref=ref, path=path, raw=raw, tmp=tmp_path)


def sample(p, name, wall, pid):
    row = O.capture(p.manifest, p.ref, p.tmp / (name + ".json"))
    # Deliberately synthetic timing/unit facts for the pure evaluation checker.
    row.update(wall=wall, mono=wall, boot_id="fixture-boot", host="fixture-host")
    row["unit"]["MainPID"] = pid
    path = p.tmp / (name + "-synthetic.json")
    immutable_json(path, row)
    return {"path": str(path), "sha256": sha256_file(path)}


def fixture_evaluation(p):
    before = sample(p, "before", 100, "1000")
    after = sample(p, "after", 120, "2000")
    fault = {
        "schema": "forge-c/operational-fault/1",
        "manifest_sha256": digest(p.manifest),
        "fault": "crash",
        "host": "fixture-host",
        "unit": "forge-conductor.service",
        "at": 110,
        "returncode": 0,
        "command": ["systemctl", "--user", "kill", "--kill-who=main", "--signal=KILL", "forge-conductor.service"],
    }
    path = p.tmp / "fault.json"
    immutable_json(path, fault)
    return {"path": str(path), "sha256": sha256_file(path)}, [before, after]


def test_capture_preserves_database_and_does_not_create_missing_storage(setup):
    p = setup
    before = sha256_file(p.db)
    row = O.capture(p.manifest, p.ref, p.tmp / "capture.json")
    assert row["complete"] is True and row["independent_process"] is True
    assert sha256_file(p.db) == before
    assert row["ledger"]["afo_mission_executions"][0]["charge"] == 500
    missing = p.tmp / "never-create" / "missing.sqlite3"
    with pytest.raises(Refused, match="DATABASE_UNAVAILABLE"):
        O.ledger(missing, 100)
    assert not missing.parent.exists()


def test_read_only_row_bound_is_unknown_instead_of_truncated_success(setup):
    p = setup
    p.mission.execution("fixture-mission", "fixture-job-two", "DIAGNOSIS", reserved_tokens=500)
    with pytest.raises(Refused, match="ROW_BOUND_EXCEEDED"):
        O.ledger(p.db, 1)
    assert O.invariants([{"complete": False}])["ledger_reset"] is None


def test_collector_cannot_run_inside_controller_cgroup(setup, monkeypatch):
    p = setup
    own = Path("/proc/self/cgroup").read_text().splitlines()[0].split(":", 2)[-1]
    monkeypatch.setattr(O, "unit_status", lambda _: {"MainPID": "12345", "ControlGroup": own, "ActiveState": "active"})
    row = O.capture(p.manifest, p.ref, p.tmp / "inside-unit.json")
    assert not row["complete"] and not row["independent_process"]


def test_missing_corrupt_or_changed_state_cannot_produce_clean_observation(setup):
    p = setup
    p.db.write_bytes(b"not SQLite")
    row = O.capture(p.manifest, p.ref, p.tmp / "corrupt.json")
    assert row["ledger"] is None and "ledger" in row["errors"] and not row["complete"]
    assert O.invariants([row])["duplicate_effects"] is None


def test_fifo_and_symlink_inputs_are_refused_without_blocking(tmp_path):
    pipe = tmp_path / "pipe"
    os.mkfifo(pipe)
    with pytest.raises(Refused):
        O.read_json(pipe)
    target = tmp_path / "normal"
    target.write_text("{}")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        O.read_json(link)


def test_frozen_plan_hash_and_source_code_identity_cannot_change(setup):
    p = setup
    p.path.chmod(0o600)
    p.path.write_text(json.dumps({**p.raw, "max_rows": 1000}))
    with pytest.raises(Refused):
        O.capture(p.manifest, p.ref, p.tmp / "changed-plan.json")


def test_local_health_client_does_not_follow_redirect_or_environment_proxy(monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            self.send_response(302)
            self.send_header("Location", "http://192.0.2.1:1/forbidden")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    monkeypatch.setenv("http_proxy", "http://192.0.2.1:1")
    try:
        assert not O._healthy(f"http://127.0.0.1:{server.server_port}/health")
        assert seen == ["/health"]
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=2)


def test_signal_restoration_is_measured_but_missing_host_audit_stays_unknown(setup):
    p = setup
    fault, refs = fixture_evaluation(p)
    result = O.evaluate(p.manifest, p.ref, fault, refs, p.tmp / "result.json")
    assert result["fault_exposed"] and result["independently_restored"]
    assert result["restoration_seconds"] == 10
    assert result["ledger_reset"] is False and result["duplicate_effects"] == 0 and result["false_ready"] is False
    assert result["unexpected_interventions"] is None
    assert result["status"] == "OBSERVED_REQUIRES_HOST_AUDIT"
    assert O.verify(p.manifest, result) == result
    result["unexpected_interventions"] = 0
    with pytest.raises(Refused, match="VERDICT_CHANGED"):
        O.verify(p.manifest, result)


@pytest.mark.parametrize("mutation", ["reset", "duplicate", "ready"])
def test_accounting_and_product_unknowns_are_not_success(setup, mutation):
    p = setup
    a = O.capture(p.manifest, p.ref, p.tmp / "accounting.json")
    b = copy.deepcopy(a)
    if mutation == "reset":
        b["ledger"]["afo_mission_executions"][0]["charge"] = 0
    elif mutation == "duplicate":
        b["ledger"]["afo_execution_liveness"] = [{"native_run_ids": ["native-A", "native-B"]}]
    else:
        b["ledger"]["orders"] = [{"state": "READY_FOR_OFFLINE_REVIEW"}]
    report = O.invariants([a, b])
    assert (
        report[{"reset": "ledger_reset", "duplicate": "duplicate_effects", "ready": "false_ready"}[mutation]]
        == {"reset": True, "duplicate": 1, "ready": None}[mutation]
    )


@pytest.mark.parametrize("mutation", ["changed", "duplicate-time", "reverse", "foreign-unit", "unobserved-ack"])
def test_uncertain_or_rebound_sources_cannot_prove_recovery(setup, mutation):
    p = setup
    fault, refs = fixture_evaluation(p)
    if mutation == "changed":
        Path(refs[0]["path"]).chmod(0o600)
        Path(refs[0]["path"]).write_text("{}")
        with pytest.raises(Refused):
            O.evaluate(p.manifest, p.ref, fault, refs, None)
        return
    if mutation in ("reverse", "duplicate-time"):
        refs = refs[::-1] if mutation == "reverse" else [refs[0], refs[0]]
        with pytest.raises(Refused, match="ORDER_INVALID"):
            O.evaluate(p.manifest, p.ref, fault, refs, None)
        return
    row = json.loads(Path(fault["path"]).read_text())
    row["unit" if mutation == "foreign-unit" else "returncode"] = "other.service" if mutation == "foreign-unit" else 1
    path = p.tmp / "bad-receipt.json"
    immutable_json(path, row)
    result = O.evaluate(p.manifest, p.ref, {"path": str(path), "sha256": sha256_file(path)}, refs, None)
    assert not result["independently_restored"]


def test_operational_report_rejects_legacy_claims_even_with_all_fault_names(setup):
    from forge_factory.afo import operational_campaign as C
    from forge_factory.afo import soak

    p = setup
    soak.start("soak-observer-fixture", 24, 30, "fixture")
    head = json.loads(soak.path("soak-observer-fixture").read_text().splitlines()[0])
    for t in (0, 86400):
        soak._append(
            soak.path("soak-observer-fixture"),
            {
                "kind": "sample",
                "wall": head["wall"] + t,
                "mono": head["mono"] + t,
                "boot_id": head["boot_id"],
                "healthy": True,
                "probes": dict.fromkeys(("conductor", "gateway", "fabro"), True),
            },
        )
    refs = []
    for name in p.manifest["faults"]:
        path = p.tmp / (name + "-legacy.json")
        immutable_json(
            path,
            {
                "manifest_sha256": digest(p.manifest),
                "fault": name,
                "independently_restored": True,
                "restoration_seconds": None,
                "unexpected_interventions": 0,
                "ledger_reset": False,
                "duplicate_effects": 0,
                "false_ready": False,
            },
        )
        refs.append({"path": str(path), "sha256": sha256_file(path)})
    report = C.report(p.manifest, "soak-observer-fixture", fault_refs=refs)
    assert report["status"] == "FAIL" and not report["missing_faults"]
    assert set(report["failed_faults"]) == set(p.manifest["faults"])
    assert report["service_intent_unchanged"] is None


@pytest.mark.parametrize("change", ["gap", "clock-jump", "missing-health", "operator-stop", "source"])
def test_observer_preserves_observation_and_operator_uncertainty(setup, change):
    p = setup
    fault, refs = fixture_evaluation(p)
    row = json.loads(Path(refs[1]["path"]).read_text())
    if change == "gap":
        row.update(wall=1000, mono=1000)
    elif change == "clock-jump":
        row["mono"] += 40
    elif change == "missing-health":
        row["health"] = {}
    elif change == "operator-stop":
        row["intent"] = {"mode": "STOPPED", "epoch": 4}
    else:
        row["observer_source_sha256"] = "0" * 64
    path = p.tmp / "changed-observation.json"
    immutable_json(path, row)
    refs[1] = {"path": str(path), "sha256": sha256_file(path)}
    if change == "source":
        with pytest.raises(Refused, match="SOURCE_CHANGED"):
            O.evaluate(p.manifest, p.ref, fault, refs, None)
    else:
        result = O.evaluate(p.manifest, p.ref, fault, refs, None)
        assert not result["independently_restored"]


@pytest.mark.parametrize("change", ["external-url", "credential-url", "code", "state-evidence", "foreign-database"])
def test_observer_plan_rejects_unapproved_boundaries(setup, change):
    p = setup
    raw = copy.deepcopy(p.raw)
    if change == "external-url":
        raw["health_urls"]["gateway"] = "https://example.com/health"
    elif change == "credential-url":
        raw["health_urls"]["gateway"] = "http://user:password@127.0.0.1:11456/health"
    elif change == "code":
        raw["observer_source_sha256"] = "0" * 64
    elif change == "state-evidence":
        raw["evidence_root"] = str(p.root / "state/workorders")
    else:
        raw["database"] = str(p.tmp / "foreign.sqlite3")
    path = p.tmp / "invalid-plan.json"
    immutable_json(path, raw)
    ref = {"path": str(path), "sha256": sha256_file(path)}
    m = {**p.manifest, "inputs": [ref]}
    with pytest.raises(Refused):
        O.capture(m, ref, p.tmp / "not-written.json")
    assert not (p.tmp / "not-written.json").exists()


def test_observation_output_cannot_be_written_into_unapproved_workspace(setup):
    p = setup
    target = p.tmp.parent / "outside-observer-root.json"
    with pytest.raises(Refused, match="OUTSIDE_APPROVED_ROOT"):
        O.capture(p.manifest, p.ref, target)
    assert not target.exists()
