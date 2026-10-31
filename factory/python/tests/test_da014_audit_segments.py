"""Synthetic root protection plus actual files/fds; no live audit coverage claim."""
# ruff: noqa: F811

import copy
import json
import os
import selectors
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from forge_factory.afo import audit_segments as S
from forge_factory.afo import host_audit as H
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.common import sha256_file
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_qualification import identity


@pytest.fixture
def logs(tmp_path, monkeypatch):
    active = tmp_path / "audit.log"
    active.write_bytes(b"PRIVATE-COMMAND\nsecond-record\n")
    cfg = {"reader_sha256": sha256_file(Path(S.__file__)),
           "paths": [str(active), str(active) + ".1", str(active) + ".2"], "max_bytes": 7}

    @contextmanager
    def synthetic_protection(path):
        # Only owner/ancestry is synthetic. Normal fd identity, byte I/O,
        # append/truncate/rename and descriptor checks remain real.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            yield fd
        finally:
            os.close(fd)

    monkeypatch.setattr(H, "protected_log", synthetic_protection)
    return active, cfg


def drain(cfg, cursor=None):
    chunks, segments = [], []
    while True:
        raw, seg = S.read(cfg, cursor)
        S.validate(seg, cfg)
        assert S.replay(cfg, seg) == raw
        chunks.append(raw)
        segments.append(seg)
        cursor = seg["cursor"]
        if cursor["end"] == seg["source"]["size_at_close"]:
            return b"".join(chunks), cursor, segments


def test_restart_cursor_covers_exact_ranges_even_across_record_boundaries(logs):
    active, cfg = logs
    raw, cursor, segments = drain(cfg)
    assert raw == active.read_bytes() and len(segments) > 1
    assert cursor["end"] == len(raw)
    assert "PRIVATE-COMMAND" not in json.dumps(segments)
    for before, after in zip(segments, segments[1:], strict=False):
        assert after["previous_cursor_sha256"] == digest(before["cursor"])
        assert after["source"]["offset"] == before["cursor"]["end"]
    with active.open("ab") as f:
        f.write(b"new-tail\n")
    tail, _, _ = drain(cfg, cursor)
    assert tail == b"new-tail\n"


def test_file_larger_than_per_capture_bound_is_read_incrementally(logs):
    active, cfg = logs
    active.write_bytes(b"a" * (3 * 65536 + 17))
    cfg["max_bytes"] = 65536
    raw, cursor, segments = drain(cfg)
    assert raw == active.read_bytes() and len(segments) == 4
    assert all(seg["source"]["length"] <= 65536 for seg in segments)
    assert cursor["anchor"]["length"] == S.ANCHOR_BYTES
    assert S.verify_chain(cfg, segments)["bytes"] == len(raw)


@pytest.mark.parametrize("change", ["truncate", "rewrite-anchor", "replace-file", "delete"])
def test_truncation_replacement_and_missing_history_do_not_reset_cursor(logs, change):
    active, cfg = logs
    _, cursor, _ = drain(cfg)
    original = copy.deepcopy(cursor)
    if change == "truncate":
        active.write_bytes(b"x")
    elif change == "rewrite-anchor":
        active.write_bytes(b"x" * active.stat().st_size)
    elif change == "replace-file":
        replacement = active.with_name("different")
        replacement.write_bytes(active.read_bytes())
        replacement.replace(active)
    else:
        active.unlink()
    with pytest.raises((Refused, FileNotFoundError)):
        S.read(cfg, cursor)
    assert cursor == original


def root_observation(old, new, *, old_open=False, append=True):
    # The native census is tested separately below. Root UID is explicitly
    # synthetic here: the test account cannot impersonate a real audit daemon.
    rows = [{"fd": 3, "device": new[0], "inode": new[1], "regular": True,
             "flags": os.O_WRONLY | (os.O_APPEND if append else 0)}]
    if old_open:
        rows.append({"fd": 4, "device": old[0], "inode": old[1], "regular": True, "flags": os.O_WRONLY | os.O_APPEND})
    return {"pid": 123, "identity": {"uid": 0}, "descriptors": rows,
            "scope": "NATIVE_PROCESS_DESCRIPTOR_OBSERVATION_ONLY"}


def rotate(active):
    old_key = S._key(active.stat())
    active.rename(str(active) + ".1")
    active.write_bytes(b"fresh-generation\n")
    return old_key, S._key(active.stat())


def test_old_tail_is_drained_before_rotation_and_handoff_requires_actual_facts(logs, monkeypatch):
    active, cfg = logs
    first, initial = S.read(cfg)
    old, new = rotate(active)
    cursor = initial["cursor"]
    chunks = [first]
    while cursor["end"] < Path(str(active) + ".1").stat().st_size:
        raw, segment = S.read(cfg, cursor)
        assert segment["rotation"] is None and S._key(segment["source"]) == old
        chunks.append(raw)
        cursor = segment["cursor"]
    assert b"".join(chunks) == Path(str(active) + ".1").read_bytes()
    monkeypatch.setattr(S, "descriptor_observation", lambda _: root_observation(old, new, old_open=True))
    with pytest.raises(Refused, match="OLD_SOURCE_STILL_OPEN"):
        S.read(cfg, cursor, daemon_pid=123)
    monkeypatch.setattr(S, "descriptor_observation", lambda _: root_observation(old, new))
    raw, segment = S.read(cfg, cursor, daemon_pid=123)
    assert raw == b"fresh-g" and segment["source"]["offset"] == 0
    assert segment["rotation"]["from"] == cursor["source"] and len(segment["cursor"]["sealed_sources"]) == 1
    assert S.replay(cfg, segment) == raw
    # A late append to the retired inode cannot disappear behind the new cursor.
    with Path(str(active) + ".1").open("ab") as f:
        f.write(b"late-old-bytes")
    with pytest.raises(Refused, match="RETIRED_SOURCE_CHANGED"):
        S.read(cfg, segment["cursor"], daemon_pid=123)


def test_multiple_unobserved_rotations_are_blocked_instead_of_skipping_a_generation(logs):
    active, cfg = logs
    _, cursor, _ = drain(cfg)
    active.rename(str(active) + ".2")
    Path(str(active) + ".1").write_bytes(b"unobserved-intermediate\n")
    active.write_bytes(b"current\n")
    with pytest.raises(Refused, match="MULTIPLE_ROTATIONS"):
        S.read(cfg, cursor, daemon_pid=123)


@pytest.mark.parametrize("kind", ["wrong-pid", "nonroot", "old-open", "no-append", "duplicate-fd", "bool-uid"])
def test_rotation_cannot_be_certified_by_a_closed_flag_or_ambiguous_descriptors(kind):
    old, new = (1, 10), (1, 11)
    observation = root_observation(old, new)
    if kind == "wrong-pid":
        observation["pid"] = 999
    elif kind == "nonroot":
        observation["identity"]["uid"] = 1000
    elif kind == "old-open":
        observation = root_observation(old, new, old_open=True)
    elif kind == "no-append":
        observation = root_observation(old, new, append=False)
    elif kind == "duplicate-fd":
        observation["descriptors"] *= 2
    else:
        observation["identity"]["uid"] = False
    with pytest.raises(Refused):
        S.rotation_facts(observation, old, new, 123)


@pytest.mark.parametrize("change", ["reader", "zero", "large", "aliases", "duplicates", "relative"])
def test_source_paths_and_bounds_are_frozen(logs, change):
    active, cfg = logs
    if change == "reader":
        cfg["reader_sha256"] = "0" * 64
    elif change == "zero":
        cfg["max_bytes"] = 0
    elif change == "large":
        cfg["max_bytes"] = H.observer.MAX_BYTES + 1
    elif change == "aliases":
        cfg["paths"][1] = str(active) + ".2"
    elif change == "duplicates":
        cfg["paths"][1] = str(active)
    else:
        cfg["paths"][1] = "relative"
    with pytest.raises(Refused, match="CONFIGURATION"):
        S.configuration(cfg, str(active))


@pytest.mark.parametrize("change", ["cursor-end", "source-length", "source-sha", "duplicate-generation"])
def test_hashes_and_cursor_bindings_are_independently_replayed(logs, change):
    _, cfg = logs
    _, segment = S.read(cfg)
    if change == "cursor-end":
        segment["cursor"]["end"] += 1
    elif change == "source-length":
        segment["source"]["length"] += 1
    elif change == "source-sha":
        segment["source"]["sha256"] = "0" * 64
    else:
        segment["cursor"]["sealed_sources"].append({k: segment["cursor"][k] for k in ["source", "end", "anchor"]})
    with pytest.raises(Refused):
        S.replay(cfg, segment)


def test_native_descriptor_census_observes_real_open_and_closed_files(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    code = """import os,sys
fds=[os.open(p,os.O_CREAT|os.O_WRONLY|os.O_APPEND,0o600) for p in sys.argv[1:]]
print('READY',flush=True)
sys.stdin.readline();os.close(fds[0]);print('CLOSED',flush=True)
sys.stdin.readline()
"""
    child = subprocess.Popen([sys.executable, "-c", code, str(old), str(new)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with selectors.DefaultSelector() as poller:
            poller.register(child.stdout, selectors.EVENT_READ)
            assert poller.select(3) and child.stdout.readline() == b"READY\n"
            before = S.descriptor_observation(child.pid)
            assert S._key(old.stat()) in {S._key(r) for r in before["descriptors"]}
            child.stdin.write(b"close\n")
            child.stdin.flush()
            assert poller.select(3) and child.stdout.readline() == b"CLOSED\n"
            after = S.descriptor_observation(child.pid)
            assert S._key(old.stat()) not in {S._key(r) for r in after["descriptors"]}
            assert any(S._key(r) == S._key(new.stat()) and r["flags"] & os.O_APPEND for r in after["descriptors"])
    finally:
        child.terminate()
        child.wait(timeout=3)
        child.stdin.close()
        child.stdout.close()


def test_capture_and_restart_preserve_parent_reference_without_raw_audit_text(setup, logs, monkeypatch):
    p = setup
    active, cfg = logs
    plan_path = p.tmp / "segmented-host-plan.json"
    immutable_json(plan_path, {"schema": "forge-c/host-audit-plan/1", "observer_plan_ref": p.ref,
        "source_sha256": sha256_file(Path(H.__file__)), "host": H.socket.gethostname(),
        "keys": ["forgec014-files", "forgec014-signals"], "kernel_log": str(active), "segments": cfg})
    host_ref = {"path": str(plan_path), "sha256": sha256_file(plan_path)}
    manifest = Q.freeze("operation-24", p.tmp / "segmented-manifest.json", identity=identity(), inputs=[p.path, plan_path])
    monkeypatch.setattr(H.shutil, "which", lambda *a, **k: None)
    first_path = p.tmp / "segment-0.json"
    first = H.capture(manifest, p.ref, host_ref, first_path)
    previous = {"path": str(first_path), "sha256": sha256_file(first_path)}
    second = H.capture(manifest, p.ref, host_ref, p.tmp / "segment-1.json", previous_ref=previous)
    assert second["kernel_segment"]["source"]["offset"] == first["kernel_segment"]["cursor"]["end"]
    assert second["kernel_segment"]["previous_segment_ref"] == previous
    assert second["kernel_segment"]["sequence"] == 1 and second["unexpected_interventions"] is None
    assert "PRIVATE-COMMAND" not in json.dumps(second)
    assert "KERNEL_SEGMENT_COMPOUND_EVENT_REPLAY_REQUIRED" in second["blockers"]
    # A failed capture retains the last successful cursor, rather than resetting.
    active.unlink()
    failed_path = p.tmp / "missing.json"
    failed = H.capture(manifest, p.ref, host_ref, failed_path, previous_ref=previous)
    assert "kernel_segment" not in failed and failed["resume_ref"] == previous


def test_byte_chain_replays_only_the_captured_prefix_with_bounded_memory(logs):
    active, cfg = logs
    _, first = S.read(cfg)
    prefix = S.verify_chain(cfg, [first])
    assert prefix["status"] == "CAPTURED_BYTE_PREFIX_REPLAYED"
    assert prefix["uncaptured_final_source_bytes"] == active.stat().st_size - cfg["max_bytes"]
    raw, _, segments = drain(cfg)
    result = S.verify_chain(cfg, segments)
    assert result["bytes"] == len(raw) and result["uncaptured_final_source_bytes"] == 0
    assert "PRIVATE-COMMAND" not in json.dumps(result)


@pytest.mark.parametrize("change", ["gap", "repeat", "reorder", "start-mid-file", "parent", "sealed", "anchor"])
def test_chain_rejects_missing_reordered_or_fabricated_continuity(logs, change):
    _, cfg = logs
    _, _, segments = drain(cfg)
    if change == "gap":
        segments.pop(1)
    elif change == "repeat":
        segments.insert(1, copy.deepcopy(segments[0]))
    elif change == "reorder":
        segments[0], segments[1] = segments[1], segments[0]
    elif change == "start-mid-file":
        segments = segments[1:]
        segments[0]["previous_cursor_sha256"] = None
    elif change == "parent":
        segments[1]["previous_cursor_sha256"] = "0" * 64
    elif change == "sealed":
        fake = copy.deepcopy(segments[0]["cursor"])
        fake.pop("sealed_sources")
        fake["source"]["inode"] += 123
        segments[1]["cursor"]["sealed_sources"] = [fake]
    else:
        segments[0]["cursor"]["anchor"]["sha256"] = "0" * 64
    with pytest.raises(Refused):
        S.verify_chain(cfg, segments)


@pytest.mark.parametrize("change", ["old-growth", "old-deleted", "open", "seal", "from"])
def test_chain_rotation_checks_retained_eof_and_derives_handoff(logs, monkeypatch, change):
    active, cfg = logs
    _, cursor, segments = drain(cfg)
    old, new = rotate(active)
    monkeypatch.setattr(S, "descriptor_observation", lambda _: root_observation(old, new))
    _, rotation = S.read(cfg, cursor, daemon_pid=123)
    segments.append(rotation)
    assert S.verify_chain(cfg, segments)["generations"] == 2
    if change == "old-growth":
        with Path(str(active) + ".1").open("ab") as f:
            f.write(b"late bytes")
    elif change == "old-deleted":
        Path(str(active) + ".1").unlink()
    elif change == "open":
        rotation["rotation"]["observation"] = root_observation(old, new, old_open=True)
    elif change == "seal":
        rotation["cursor"]["sealed_sources"] = []
    else:
        rotation["rotation"]["from"]["inode"] += 1
    with pytest.raises(Refused):
        S.verify_chain(cfg, segments)


def test_chain_budget_counts_terminal_anchor_reads_and_refuses_before_source_io(logs, monkeypatch):
    _, cfg = logs
    _, _, segments = drain(cfg)
    monkeypatch.setattr(S.observer, "MAX_TRACE_BYTES", 1)
    monkeypatch.setattr(S, "replay", lambda *a, **k: pytest.fail("budget must be checked before IO"))
    with pytest.raises(Refused, match="CHAIN_BYTE_BOUND"):
        S.verify_chain(cfg, segments)


@pytest.fixture
def segmented_plan(setup, logs, monkeypatch, request):
    p = setup
    active, cfg = logs
    cfg["max_bytes"] = getattr(request, "param", cfg["max_bytes"])
    host_path = p.tmp / "host-plan.json"
    immutable_json(host_path, {"schema": "forge-c/host-audit-plan/1", "observer_plan_ref": p.ref,
        "source_sha256": sha256_file(Path(H.__file__)), "host": H.socket.gethostname(),
        "keys": ["forgec014-files", "forgec014-signals"], "kernel_log": str(active), "segments": cfg})
    host_ref = {"path": str(host_path), "sha256": sha256_file(host_path)}
    manifest = Q.freeze("operation-24", p.tmp / "segmented-manifest.json", identity=identity(), inputs=[p.path, host_path])
    monkeypatch.setattr(H.shutil, "which", lambda *a, **k: None)
    return p, active, cfg, host_ref, manifest


def capture_refs(plan, count=2, *, previous=None):
    p, _, _, host_ref, manifest = plan
    refs = []
    for i in range(count):
        path = p.tmp / ("capture-" + str(i) + ".json")
        H.capture(manifest, p.ref, host_ref, path, previous_ref=previous)
        previous = {"path": str(path), "sha256": sha256_file(path)}
        refs.append(previous)
    return refs


def test_executable_verifier_binds_captures_but_never_claims_host_coverage(segmented_plan, capsys):
    p, _, _, host_ref, manifest = segmented_plan
    refs = capture_refs(segmented_plan)
    paths = {}
    for name, value in (("manifest", manifest), ("observer-plan-ref", p.ref),
                        ("host-plan-ref", host_ref), ("segment-refs", refs)):
        paths[name] = p.tmp / ("cli-" + name + ".json")
        immutable_json(paths[name], value)
    out = p.tmp / "replay.json"
    code = H.main(["verify-segments", *[v for k, path in paths.items() for v in ("--" + k, str(path))], "--out", str(out)])
    result = json.loads(out.read_text())
    assert code == 2 and result["status"] == "INCOMPLETE_SOURCE_COVERAGE"
    assert result["byte_chain"]["segments"] == 2 and result["unexpected_interventions"] is None
    assert result["capture_refs_sha256"] == digest(refs)
    assert "PRIVATE-COMMAND" not in out.read_text() + capsys.readouterr().out


@pytest.mark.parametrize("change", ["skip-first", "duplicate", "hash", "plan", "sequence", "parent", "outside", "not-ref"])
def test_verifier_rejects_wrong_capture_references_before_publishing(segmented_plan, change):
    p, _, _, host_ref, manifest = segmented_plan
    refs = capture_refs(segmented_plan)
    if change == "skip-first":
        refs.pop(0)
    elif change == "duplicate":
        refs[1] = refs[0]
    elif change == "hash":
        refs[1]["sha256"] = "0" * 64
    elif change == "outside":
        refs[1]["path"] = str(p.tmp.parent / "outside.json")
    elif change == "not-ref":
        refs[1] = "arbitrary path"
    else:
        d = json.loads(Path(refs[1]["path"]).read_text())
        if change == "plan":
            d["host_plan_ref"] = p.ref
        elif change == "sequence":
            d["kernel_segment"]["sequence"] = True
        else:
            d["kernel_segment"]["previous_segment_ref"] = None
        path = p.tmp / "altered.json"
        immutable_json(path, d)
        refs[1] = {"path": str(path), "sha256": sha256_file(path)}
    out = p.tmp / "refused.json"
    with pytest.raises(Refused):
        H.verify_segments(manifest, p.ref, host_ref, refs, out)
    assert not out.exists()


def test_failed_capture_can_resume_without_deleting_failure_or_resetting_cursor(segmented_plan):
    p, active, _, host_ref, manifest = segmented_plan
    first = capture_refs(segmented_plan, 1)[0]
    saved = active.with_name("temporarily-unavailable")
    active.rename(saved)
    failure = p.tmp / "failed.json"
    H.capture(manifest, p.ref, host_ref, failure, previous_ref=first)
    failed_ref = {"path": str(failure), "sha256": sha256_file(failure)}
    saved.rename(active)
    path = p.tmp / "resumed.json"
    result = H.capture(manifest, p.ref, host_ref, path, previous_ref=failed_ref)
    assert result["previous_capture_ref"] == failed_ref and result["resume_ref"] == first
    assert result["kernel_segment"]["sequence"] == 1 and failure.is_file()
    refs = [first, {"path": str(path), "sha256": sha256_file(path)}]
    replay = H.verify_segments(manifest, p.ref, host_ref, refs, p.tmp / "replay.json")
    assert replay["unexpected_interventions"] is None
    # Successful byte coverage does not erase the failed observation window.
    assert replay["status"] == "INCOMPLETE_SOURCE_COVERAGE"


@pytest.mark.parametrize("bad", ["not-a-reference", {}, {"path": "relative", "sha256": "bad"}])
def test_corrupt_failure_resume_reference_is_a_typed_refusal(segmented_plan, bad):
    p, _, _, host_ref, manifest = segmented_plan
    first = capture_refs(segmented_plan, 1)[0]
    failed = json.loads(Path(first["path"]).read_text())
    failed.pop("kernel_segment")
    failed["resume_ref"] = bad
    path = p.tmp / "bad-resume.json"
    immutable_json(path, failed)
    ref = {"path": str(path), "sha256": sha256_file(path)}
    with pytest.raises(Refused, match="CAPTURE_REFERENCE_INVALID"):
        H.capture(manifest, p.ref, host_ref, p.tmp / "refused.json", previous_ref=ref)


def test_rotation_capture_requires_matching_native_status_pid(segmented_plan, monkeypatch):
    p, active, _, host_ref, manifest = segmented_plan
    refs = capture_refs(segmented_plan, 1)
    old, new = rotate(active)
    first = json.loads(Path(refs[0]["path"]).read_text())
    cursor = first["kernel_segment"]["cursor"]
    sequence = 1
    while cursor["end"] < Path(str(active) + ".1").stat().st_size:
        path = p.tmp / ("old-tail-" + str(sequence) + ".json")
        record = H.capture(manifest, p.ref, host_ref, path, previous_ref=refs[-1])
        cursor = record["kernel_segment"]["cursor"]
        refs.append({"path": str(path), "sha256": sha256_file(path)})
        sequence += 1
    monkeypatch.setattr(S, "descriptor_observation", lambda _: root_observation(old, new))
    original = H.preflight
    def synthetic_status():
        result = original()
        result["kernel_status"] = {"pid": 123}
        return result
    monkeypatch.setattr(H, "preflight", synthetic_status)
    path = p.tmp / "rotated.json"
    record = H.capture(manifest, p.ref, host_ref, path, previous_ref=refs[-1])
    refs.append({"path": str(path), "sha256": sha256_file(path)})
    assert H.verify_segments(manifest, p.ref, host_ref, refs, p.tmp / "good.json")["byte_chain"]["generations"] == 2
    record["kernel_status"]["pid"] = 999
    altered = p.tmp / "wrong-daemon.json"
    immutable_json(altered, record)
    refs[-1] = {"path": str(altered), "sha256": sha256_file(altered)}
    with pytest.raises(Refused, match="DAEMON_BINDING_UNKNOWN"):
        H.verify_segments(manifest, p.ref, host_ref, refs, p.tmp / "refused.json")
