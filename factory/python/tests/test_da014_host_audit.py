"""Linux audit fixtures are synthetic sources, never a host-coverage claim."""
# ruff: noqa: F811

import copy
import json
import sys
from pathlib import Path

import pytest
from forge_factory.afo import host_audit as H
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.common import sha256_file
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_qualification import identity

KEYS = ["forgec014-files", "forgec014-signals"]
STATUS = {"enabled": 2, "pid": 456, "rate_limit": 0, "backlog_limit": 8192, "lost": 7, "backlog": 0}


def raw_event(*, serial=1, at="100.001", items=1, key="forgec014-files", host="", secret="DO-NOT-EXPORT"):
    head = ("node=" + host + " ") if host else ""
    rows = [
        f'{head}type=SYSCALL msg=audit({at}:{serial}): arch=c000003e syscall=257 success=yes exit=3 items={items} ppid=12 pid=13 uid=1000 auid=1000 comm="{secret}" key="{key}"'
    ]
    rows += [f'{head}type=PATH msg=audit({at}:{serial}): item={i} name="/private/{secret}"' for i in range(items)]
    rows += [
        f'{head}type=EXECVE msg=audit({at}:{serial}): argc=2 a0="{secret}"',
        f"{head}type=PROCTITLE msg=audit({at}:{serial}): proctitle={secret.encode().hex()}",
    ]
    return ("\n".join(rows) + "\n").encode()


@pytest.mark.parametrize("legacy", [False, True])
def test_native_status_variants_preserve_nonzero_historical_loss(legacy):
    text = (
        "AUDIT_STATUS: " + " ".join(f"{k}={v}" for k, v in STATUS.items())
        if legacy
        else "\n".join(f"{k} {v}" for k, v in STATUS.items())
    )
    assert H.kernel_status(text) == STATUS


@pytest.mark.parametrize(
    "text", ["enabled 2\n", "enabled 2 enabled 1\n", "enabled nan\n", "enabled -1\n", "enabled 2\nenabled 1\n"]
)
def test_unknown_or_ambiguous_status_never_defaults_to_zero(text):
    with pytest.raises(Refused):
        H.kernel_status(text)


def test_compound_event_identity_metadata_and_privacy():
    raw = raw_event() + raw_event(serial=2, items=0, key=KEYS[1])
    out = H.events(raw, host="omniverse2", keys=KEYS)
    assert len(out["events"]) == 2 and out["events"][0]["path_records"] == 1
    assert out["events"][0]["pid"] == 13 and out["events"][0]["auid"] == 1000
    assert out["events"][0]["syscall"] == 257
    blob = json.dumps(out)
    assert "DO-NOT-EXPORT" not in blob and "444f2d4e4f542d4558504f5254" not in blob
    assert "argv" not in blob and "/private/" not in blob


def test_same_serial_at_a_different_time_is_not_collapsed():
    out = H.events(raw_event(at="100.001") + raw_event(at="200.001"), host="omniverse2", keys=KEYS)
    assert len(out["events"]) == 2 and out["source_events"] == 2


def test_duplicate_rotation_records_are_retained_as_duplicate_counts():
    raw = raw_event()
    out = H.events(raw + raw, host="omniverse2", keys=KEYS)
    assert out["source_records"] == 4 and out["duplicate_records"] == 4 and len(out["events"]) == 1


def test_empty_or_unselected_events_do_not_establish_a_global_zero():
    assert H.events(b"", host="omniverse2", keys=KEYS)["events"] == []
    assert H.events(raw_event(key="other-project"), host="omniverse2", keys=KEYS)["events"] == []


@pytest.mark.parametrize(
    "change",
    ["host", "header", "truncated", "missing-path", "duplicate-item", "duplicate-pid", "missing-success", "unbounded-serial"],
)
def test_malformed_or_incomplete_raw_sources_are_refused(change):
    raw = raw_event()
    if change == "host":
        raw = raw_event(host="other-host")
    if change == "header":
        raw = b"UNKNOWN PRIVATE BODY\n"
    if change == "truncated":
        raw = raw[:-1]
    if change == "missing-path":
        raw = b"\n".join(line for line in raw.splitlines() if b"type=PATH" not in line) + b"\n"
    if change == "duplicate-item":
        raw = raw_event(items=2).replace(b"item=1", b"item=0")
    if change == "duplicate-pid":
        raw = raw.replace(b"pid=13", b"pid=13 pid=14")
    if change == "missing-success":
        raw = raw.replace(b"success=yes", b"success=unknown")
    if change == "unbounded-serial":
        raw = raw.replace(b":1)", b":" + b"1" * 100 + b")")
    with pytest.raises(Refused):
        H.events(raw, host="omniverse2", keys=KEYS)


def test_event_and_record_bounds_are_enforced(monkeypatch):
    monkeypatch.setattr(H, "MAX_EVENTS", 1)
    with pytest.raises(Refused, match="EVENT_COUNT_BOUND"):
        H.events(raw_event() + raw_event(serial=2), host="omniverse2", keys=KEYS)
    monkeypatch.setattr(H, "MAX_EVENTS", 100)
    monkeypatch.setattr(H, "MAX_RECORDS", 1)
    with pytest.raises(Refused, match="RECORD_COUNT_BOUND"):
        H.events(raw_event(), host="omniverse2", keys=KEYS)


def kernel_samples():
    before = {
        "host": "omniverse2",
        "boot_id": "boot-fixture",
        "source_sha256": "source",
        "host_plan_ref": {"sha256": "plan"},
        "at": 100,
        "mono": 10,
        "rules_sha256": "rules",
        "kernel_status": STATUS,
        "kernel_log_ref": {"device": 1, "inode": 2},
        "kernel_facts": {"integrity_events": []},
    }
    return before, {**copy.deepcopy(before), "at": 130, "mono": 40}


def test_loss_delta_preserves_history_without_reset_or_global_intervention_claim():
    a, b = kernel_samples()
    result = H.kernel_window(a, b)
    assert result["kernel_loss_delta"] == 0 and result["status"] == "KERNEL_CHANNEL_FACTS_ONLY"
    assert result["unexpected_interventions"] is None and result["missing_channels"]
    assert a["kernel_status"]["lost"] == 7


@pytest.mark.parametrize(
    "change,expected",
    [
        ("loss", "RECORDS_LOST"),
        ("reset", "COUNTER_RESET"),
        ("pid", "NOT_STABLE"),
        ("backlog", "NOT_STABLE"),
        ("boot", "BOOT_CHANGED"),
        ("rules", "SOURCE_OR_BOOT_CHANGED"),
        ("clock", "CLOCK_GAP"),
        ("rotation", "ROTATION"),
        ("daemon", "DAEMON_OR_CONFIG_EVENT"),
        ("missing", "STATUS_UNKNOWN"),
    ],
)
def test_loss_reset_restart_rotation_policy_and_clock_changes_stay_incomplete(change, expected):
    a, b = kernel_samples()
    if change == "loss":
        b["kernel_status"]["lost"] += 1
    if change == "reset":
        b["kernel_status"]["lost"] = 0
    if change == "pid":
        b["kernel_status"]["pid"] += 1
    if change == "backlog":
        b["kernel_status"]["backlog"] = 1
    if change == "boot":
        b["boot_id"] = "another-boot"
    if change == "rules":
        b["rules_sha256"] = "changed"
    if change == "clock":
        b["mono"] += 20
    if change == "rotation":
        b["kernel_log_ref"]["inode"] += 1
    if change == "daemon":
        b["kernel_facts"]["integrity_events"] = [{"at": 120, "types": ["DAEMON_START"]}]
    if change == "missing":
        b["kernel_status"] = None
    result = H.kernel_window(a, b)
    assert result["status"] == "INCOMPLETE" and any(expected in reason for reason in result["blockers"])
    assert result["unexpected_interventions"] is None


def test_preflight_cannot_qualify_a_kernel_only_host(monkeypatch):
    monkeypatch.setattr(H.shutil, "which", lambda *a, **k: "/usr/sbin/auditctl")
    monkeypatch.setattr(H, "_command", lambda _: {"returncode": 0, "stdout": "\n".join(f"{k} {v}" for k, v in STATUS.items())})
    result = H.preflight()
    assert result["kernel_status"]["lost"] == 7
    assert result["status"] == "BLOCKED" and result["unexpected_interventions"] is None
    assert set(result["blockers"]) == {"SYSTEMD_BUS_AUDIT_COVERAGE_REQUIRED", "AUTHENTICATED_CONTROL_CORRELATION_REQUIRED"}


def test_missing_utility_or_permission_is_a_block_not_zero(monkeypatch):
    monkeypatch.setattr(H.shutil, "which", lambda *a, **k: None)
    result = H.preflight()
    assert result["kernel_status"] is None and "KERNEL_AUDIT_STATUS_UNAVAILABLE" in result["blockers"]
    monkeypatch.setattr(H.shutil, "which", lambda *a, **k: "/usr/sbin/auditctl")
    monkeypatch.setattr(H, "_command", lambda _: {"returncode": 1, "stdout": "PRIVATE ERROR"})
    assert H.preflight()["kernel_status"] is None
    assert "PRIVATE ERROR" not in json.dumps(H.preflight())


def test_capture_is_bound_and_durable_without_activating_audit_or_claiming_coverage(setup, monkeypatch):
    p = setup
    host_plan = p.tmp / "host-plan.json"
    immutable_json(
        host_plan,
        {
            "schema": "forge-c/host-audit-plan/1",
            "observer_plan_ref": p.ref,
            "source_sha256": sha256_file(Path(H.__file__)),
            "host": H.socket.gethostname(),
            "keys": KEYS,
            "kernel_log": str(p.tmp / "missing-root-audit.log"),
        },
    )
    host_ref = {"path": str(host_plan), "sha256": sha256_file(host_plan)}
    manifest = Q.freeze("operation-24", p.tmp / "audit-manifest.json", identity=identity(), inputs=[p.path, host_plan])
    monkeypatch.setattr(H.shutil, "which", lambda *a, **k: None)
    out = p.tmp / "host-capture.json"
    result = H.capture(manifest, p.ref, host_ref, out)
    assert out.is_file() and result["unexpected_interventions"] is None
    assert result["status"] == "INCOMPLETE_SOURCE_COVERAGE" and result["blockers"]
    assert result["host_plan_ref"] == host_ref
    assert not (p.tmp / "missing-root-audit.log").exists()


def test_unfrozen_host_plan_is_refused_before_any_command(setup, monkeypatch):
    monkeypatch.setattr(H, "preflight", lambda: pytest.fail("must refuse before probing"))
    with pytest.raises(Refused, match="PLAN_NOT_FROZEN"):
        H.capture(setup.manifest, setup.ref, {"path": "/unfrozen", "sha256": "x"}, setup.tmp / "out.json")


def test_user_owned_or_symlink_sources_are_not_trusted(setup):
    p = setup
    source = p.tmp / "audit.log"
    source.write_bytes(raw_event())
    with pytest.raises(Refused, match="NOT_PROTECTED"):
        H.read_protected_log(source)


def test_fixed_probe_stdout_is_bounded_and_stderr_is_not_retained(monkeypatch):
    monkeypatch.setattr(H.observer, "MAX_BYTES", 4096)
    result = H._command([sys.executable, "-c", "import os; os.write(2,b'PRIVATE-ERROR'); os.write(1,b'x'*8192)"])
    assert result["error"] == "OUTPUT_BOUND_EXCEEDED"
    assert "PRIVATE-ERROR" not in json.dumps(result)


def test_fixed_probe_transport_and_output_encoding_failures_are_facts():
    assert H._command(["/must-not-exist-forge-c-auditctl"])["returncode"] is None
    result = H._command([sys.executable, "-c", "import os; os.write(1,b'\\xff')"])
    assert result["error"] == "OUTPUT_ENCODING"
