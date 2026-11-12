"""Real immutable artifacts/crash replay with synthetic probes, never campaign evidence."""

# ruff: noqa: F811
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import operational_campaign as R
from forge_factory.afo import operational_collection as C
from forge_factory.afo import qualification as Q
from forge_factory.afo import soak
from forge_factory.afo.durable import Refused, immutable_json
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_qualification import identity


@pytest.fixture
def collector(setup):
    p = setup
    plan = copy.deepcopy(p.raw)
    plan["collection"] = {**C.source_hashes(), "interval_seconds": 30, "max_samples": 8, "minimum_free_bytes": 64 * 1024 * 1024}
    path = p.tmp / "collection-plan.json"
    immutable_json(path, plan)
    p.ref = C.reference(path)
    p.manifest = Q.freeze("operation-24", p.tmp / "collection-manifest.json", identity=identity(), inputs=[path])
    p.soak_id = "soak-collection-test"
    soak.start(p.soak_id, 24, 30, "synthetic-fixture-no-authority")
    immutable_json(soak.path(p.soak_id).with_suffix(".manifest.json"), p.manifest)
    p.collector = C.Collector(p.manifest, p.soak_id, p.ref)
    return p


def test_configuration_does_not_mutate_and_copies(collector):
    value = collector.collector.config
    before = copy.deepcopy(value)
    out = C.configuration(value)
    assert out == before == value and out is not value


@pytest.mark.parametrize(
    "key,lower,upper",
    [("interval_seconds", 5, 600), ("max_samples", 1, 50000), ("minimum_free_bytes", 64 * 1024 * 1024, 2**63 - 1)],
)
@pytest.mark.parametrize("variant", ["lower", "upper", "below", "above", "bool", "float", "str", "null", "subclass"])
def test_numeric_boundaries(collector, key, lower, upper, variant):
    class IntSubclass(int):
        pass

    values = dict(
        lower=lower,
        upper=upper,
        below=lower - 1,
        above=upper + 1,
        bool=True,
        float=float(lower),
        str=str(lower),
        null=None,
        subclass=IntSubclass(lower),
    )
    config = {**collector.collector.config, key: values[variant]}
    if variant in ("lower", "upper"):
        assert C.configuration(config) == config
    else:
        with pytest.raises(Refused, match="CONFIGURATION_INVALID"):
            C.configuration(config)


@pytest.mark.parametrize("change", ["extra", "missing", "list", "hash", "source", "expected-extra", "expected-type"])
def test_configuration_refuses_invalid_structure(collector, change):
    value = copy.deepcopy(collector.collector.config)
    expected = C.source_hashes()
    if change == "extra":
        value["unexpected"] = 1
    if change == "missing":
        del value["max_samples"]
    if change == "list":
        value = []
    if change == "hash":
        expected["source_sha256"] = value["source_sha256"] = "A" * 64
    if change == "source":
        value["soak_source_sha256"] = "f" * 64
    if change == "expected-extra":
        expected["unexpected"] = 1
    if change == "expected-type":
        expected = None
    with pytest.raises(Refused, match="CONFIGURATION_INVALID"):
        C.validate_configuration(value, expected)


def test_capture_resume_and_report_replay(collector):
    p = collector
    first = p.collector(p.soak_id)
    second = C.Collector(p.manifest, p.soak_id, p.ref)(p.soak_id)
    assert (first["collection_sequence"], second["collection_sequence"]) == (0, 1)
    verdict = p.collector.verify()
    assert verdict["status"] == "SOURCE_REPLAY_PASS" and verdict["samples"] == 2
    assert verdict["unexpected_interventions"] is None
    report = R.report(p.manifest, p.soak_id, observer_plan_ref=p.ref)
    assert report["status"] == "INCOMPLETE" and report["collection"]["samples"] == 2
    assert report["missing_faults"] and report["real_work_exposures"] == 0


def test_crash_after_receipt_before_append_reuses_capture(collector, monkeypatch):
    p = collector
    append = soak._append_locked
    with monkeypatch.context() as m:
        m.setattr(soak, "_append_locked", lambda *a: (_ for _ in ()).throw(OSError("synthetic crash")))
        with pytest.raises(OSError):
            p.collector(p.soak_id)
    ref = C.reference(p.collector.directory(0) / "observation.json")
    monkeypatch.setattr(C.O, "capture", lambda *a: pytest.fail("must replay existing immutable snapshot"))
    row = p.collector(p.soak_id)
    assert row["collection_sequence"] == 0 and p.collector.verify()["samples"] == 1
    assert ref == C.reference(p.collector.directory(0) / "observation.json")
    assert soak._append_locked is append


def test_crash_after_snapshot_before_attempt_replays_snapshot(collector, monkeypatch):
    p = collector
    publish = C.immutable_json

    def crash(path, value):
        if path.name == "observation-attempt.json":
            raise OSError("synthetic crash")
        return publish(path, value)

    with monkeypatch.context() as m:
        m.setattr(C, "immutable_json", crash)
        with pytest.raises(OSError):
            p.collector(p.soak_id)
    monkeypatch.setattr(C.O, "capture", lambda *a: pytest.fail("capture must not repeat"))
    p.collector(p.soak_id)
    assert p.collector.verify()["samples"] == 1


def test_failed_capture_keeps_unknown_and_durable_failure(collector, monkeypatch):
    p = collector
    monkeypatch.setattr(C.O, "capture", lambda *a: (_ for _ in ()).throw(Refused("SYNTHETIC_SOURCE_MISSING")))
    row = p.collector(p.soak_id)
    assert row["probes"] == {} and row["healthy"] is False
    assert p.collector.verify()["observation_refs"] == [None]
    attempt = C.O.read_json(p.collector.directory(0) / "observation-attempt.json")
    assert attempt["error"] == "SYNTHETIC_SOURCE_MISSING"


def test_partial_tail_never_rewritten(collector):
    p = collector
    path = p.collector.log
    with path.open("ab") as f:
        f.write(b'{"kind":')
    raw = path.read_bytes()
    with pytest.raises(Refused, match="PARTIAL_LOG_TAIL"):
        p.collector(p.soak_id)
    assert path.read_bytes() == raw


def test_changed_original_snapshot_cannot_pass_report(collector):
    p = collector
    p.collector(p.soak_id)
    path = p.collector.directory(0) / "observation.json"
    path.chmod(0o600)
    row = json.loads(path.read_bytes())
    row["complete"] = not row["complete"]
    path.write_text(json.dumps(row))
    with pytest.raises(Refused):
        R.report(p.manifest, p.soak_id, observer_plan_ref=p.ref)


def test_mixed_unbound_legacy_samples_refused(collector):
    p = collector
    soak.sample(p.soak_id, {"conductor": lambda: True})
    with pytest.raises(Refused, match="HISTORY_UNBOUND"):
        p.collector(p.soak_id)


def test_writer_lock_serializes_existing_soak_and_collector(collector):
    p = collector
    with soak.locked(p.collector.log):
        with pytest.raises(Refused, match="WRITER_BUSY"):
            p.collector(p.soak_id)
        with pytest.raises(Refused, match="WRITER_BUSY"):
            soak.sample(p.soak_id, {"x": lambda: True})


def test_low_disk_does_not_delete_evidence_or_change_factory(collector, monkeypatch):
    p = collector
    before = p.collector.log.read_bytes()
    monkeypatch.setattr(C.os, "statvfs", lambda *a: SimpleNamespace(f_bavail=0, f_frsize=4096))
    with pytest.raises(Refused, match="DISK_RESERVE"):
        p.collector(p.soak_id)
    assert p.collector.log.read_bytes() == before
    assert not p.collector.directory(0).exists()


def test_finite_invocation_reuses_soak_and_does_not_stop_at_campaign_boundary(collector, monkeypatch):
    p = collector
    seen = {}

    def run(soak_id, **kwargs):
        seen.update(kwargs)
        assert soak_id == p.soak_id
        return 1

    monkeypatch.setattr(soak, "run", run)
    out = R.collect(p.manifest, p.soak_id, p.ref, max_samples=1)
    assert seen["stop_at_target"] is False and seen["max_samples"] == 1
    assert isinstance(seen["sampler"], C.Collector) and out["service_stop_at_end"] is False


def test_allowance_is_cumulative_across_collector_restarts(collector):
    p = collector
    for _ in range(8):
        C.Collector(p.manifest, p.soak_id, p.ref)(p.soak_id)
    with pytest.raises(Refused, match="ALLOWANCE_EXHAUSTED"):
        C.Collector(p.manifest, p.soak_id, p.ref)(p.soak_id)
    assert p.collector.verify()["samples"] == 8


def test_host_cursor_chain_retains_failed_capture_and_resumes(collector, tmp_path, monkeypatch):
    import os
    from contextlib import contextmanager

    from forge_factory.afo import audit_segments as S
    from forge_factory.afo import host_audit as H

    p = collector
    active = p.tmp / "kernel-audit.log"
    active.write_bytes(b"first\n")
    cfg = {"reader_sha256": C.sha256_file(Path(S.__file__)), "paths": [str(active), str(active) + ".1"], "max_bytes": 65536}

    @contextmanager
    def protected(path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            yield fd
        finally:
            os.close(fd)

    monkeypatch.setattr(H, "protected_log", protected)
    monkeypatch.setattr(H.shutil, "which", lambda *a, **k: None)
    host_plan = p.tmp / "host-plan.json"
    immutable_json(
        host_plan,
        {
            "schema": "forge-c/host-audit-plan/1",
            "observer_plan_ref": p.ref,
            "source_sha256": C.sha256_file(Path(H.__file__)),
            "host": H.socket.gethostname(),
            "keys": ["forgec014-files", "forgec014-signals"],
            "kernel_log": str(active),
            "segments": cfg,
        },
    )
    observer_path = p.ref["path"]
    manifest = Q.freeze("operation-24", p.tmp / "with-host-manifest.json", identity=identity(), inputs=[observer_path, host_plan])
    sid = "soak-collection-host"
    soak.start(sid, 24, 30, "synthetic-no-authority")
    immutable_json(soak.path(sid).with_suffix(".manifest.json"), manifest)
    c = C.Collector(manifest, sid, p.ref, C.reference(host_plan))
    c(sid)
    first = C.O.read_json(c.directory(0) / "host.json")
    assert first["kernel_segment"]["cursor"]["end"] == 6
    active.rename(p.tmp / "temporarily-offline")
    c(sid)
    failed = C.O.read_json(c.directory(1) / "host.json")
    assert failed["resume_ref"] == C.reference(c.directory(0) / "host.json")
    assert "kernel_segment" not in failed
    (p.tmp / "temporarily-offline").rename(active)
    with active.open("ab") as f:
        f.write(b"second\n")
    c(sid)
    resumed = C.O.read_json(c.directory(2) / "host.json")
    assert resumed["kernel_segment"]["source"]["offset"] == 6
    assert resumed["previous_capture_ref"] == C.reference(c.directory(1) / "host.json")
    assert resumed["kernel_segment"]["sequence"] == 1
    assert c.verify()["unexpected_interventions"] is None
