"""Synthetic audit sources and real retained IO; never live host qualification."""
# ruff: noqa: F811
import copy
import hashlib
import json
import os
import selectors
import signal
import subprocess
import sys
from pathlib import Path

import pytest
from forge_factory.afo import audit_segments as S
from forge_factory.afo import host_audit as H
from forge_factory.afo import kernel_replay as K
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, canonical, digest, immutable_json
from forge_factory.common import sha256_file
from test_da014_audit_segments import capture_refs, logs, segmented_plan  # noqa: F401
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_host_audit import KEYS, raw_event
from test_da014_qualification import identity


def config(**changes):
    return {"source_sha256": sha256_file(Path(K.__file__)), "max_source_bytes": 256 * 1024**2,
            "max_records": 50000, "max_scratch_bytes": 16 * 1024**2, "max_output_bytes": 16 * 1024**2,
            "max_seconds": 120, "max_cpu_seconds": 60, **changes}


def no_sort_files(parent):
    controls = {parent / ".kernel-replay-init-owner.json", parent / ".kernel-replay-init.lock"}
    assert set(parent.glob(".kernel-replay-*")) <= controls
    assert not list(parent.glob("#* (deleted)"))


def invoke(tmp_path, chunks, **changes):
    pages = []
    with K.Replay(config(**changes), host="omniverse2", keys=KEYS, scratch_parent=tmp_path) as replay:
        for raw in chunks:
            replay.feed(raw)

        def publish(index, page):
            pages.append(page)
            return {"path": str(tmp_path / (str(index) + ".json")), "sha256": digest(page)}

        result = replay.finish(publish, {"fixture": True})
    no_sort_files(tmp_path)
    return result, pages


@pytest.mark.parametrize("size", [1, 7, 113, 65536])
def test_cross_batch_utf8_interleaving_duplicates_and_private_fields(size, tmp_path):
    a, b = raw_event(secret="PRIVATE-é-雪"), raw_event(serial=2)
    rows = [line for pair in zip(a.splitlines(keepends=True), b.splitlines(keepends=True), strict=True) for line in pair]
    raw = b"".join(rows) + a
    legacy = H.EventReplay(host="omniverse2", keys=KEYS)
    legacy.feed(raw)
    expected = legacy.finish()
    result, pages = invoke(tmp_path, [raw[i:i+size] for i in range(0, len(raw), size)])
    events = [e for p in pages for g in p["groups"] for e in g["facts"]["events"]]
    assert events == expected["facts"]["events"]
    assert result["totals"]["source_records"] == 8 and result["totals"]["duplicate_records"] == 4
    assert result["input_sha256"] == hashlib.sha256(raw).hexdigest() and result["input_bytes"] == len(raw)
    text = json.dumps([result, pages])
    assert "PRIVATE" not in text and "/private/" not in text and "雪" not in text
    assert result["unexpected_interventions"] is None and result["facts"] is None


@pytest.mark.parametrize("change", ["missing-path", "wrong-path", "no-boundary", "partial-line", "orphan", "integrity"])
def test_partial_and_integrity_facts_match_existing_parser(tmp_path, change):
    raw = raw_event()
    if change == "missing-path":
        raw = b"\n".join(x for x in raw.splitlines() if b"type=PATH" not in x) + b"\n"
    elif change == "wrong-path":
        raw = raw.replace(b"item=0", b"item=1")
    elif change == "no-boundary":
        raw = b"\n".join(x for x in raw.splitlines() if b"type=PROCTITLE" not in x) + b"\n"
    elif change == "partial-line":
        raw = raw[:-7]
    elif change == "orphan":
        raw = b'type=PATH msg=audit(100.001:1): item=0 name="PRIVATE"\n'
    else:
        raw = b'type=CONFIG_CHANGE msg=audit(100.001:1): op=PRIVATE\n'
    legacy = H.EventReplay(host="omniverse2", keys=KEYS)
    legacy.feed(raw)
    expected = legacy.finish()
    result, pages = invoke(tmp_path, [raw[:11], raw[11:]])
    assert result["blockers"] == expected["blockers"]
    assert result["pending_line"] == expected["pending_line"]
    assert result["totals"]["orphan_compound_groups"] == expected["orphan_compound_groups"]
    assert [e for p in pages for g in p["groups"] for e in g["facts"]["integrity_events"]] == expected["facts"]["integrity_events"]


@pytest.mark.parametrize("change", ["data", "copies", "delete", "tag", "null-tag", "schema"])
def test_scratch_tampering_cannot_publish_final_success(tmp_path, change):
    with K.Replay(config(), host="omniverse2", keys=KEYS, scratch_parent=tmp_path) as replay:
        replay.feed(raw_event())
        assert b"DO-NOT-EXPORT" not in replay.database.read_bytes()
        assert b"/private/" not in replay.database.read_bytes()
        assert b"DO-NOT-EXPORT" not in b"".join(row[0] for row in replay.connection.execute("SELECT data FROM records"))
        assert os.stat(replay.database).st_nlink == 0
        if change == "data":
            replay.connection.execute("UPDATE records SET data=?", (b'{}',))
        elif change == "copies":
            replay.connection.execute("UPDATE records SET copies=copies+1")
        elif change == "delete":
            replay.connection.execute("DELETE FROM records")
        elif change == "tag":
            replay.connection.execute("UPDATE records SET tag=?", (b"x" * 32,))
        elif change == "null-tag":
            replay.connection.execute("UPDATE records SET tag=NULL")
        else:
            replay.connection.execute("DROP TABLE records")
        with pytest.raises(Refused):
            replay.finish(lambda *a: {"path": "unused", "sha256": "f" * 64}, {})
        with pytest.raises(Refused, match="ALREADY_SETTLED"):
            replay.feed(raw_event())
    no_sort_files(tmp_path)


@pytest.mark.parametrize("bound", ["source", "records", "scratch", "output", "wall", "cpu"])
def test_finite_allowances_never_become_partial_success(tmp_path, monkeypatch, bound):
    changes = {"source": {"max_source_bytes": 1}, "records": {"max_records": 1},
               "scratch": {"max_scratch_bytes": 65536}, "output": {"max_output_bytes": 16384},
               "wall": {}, "cpu": {}}[bound]
    with K.Replay(config(**changes), host="omniverse2", keys=KEYS, scratch_parent=tmp_path) as replay:
        if bound in ("wall", "cpu"):
            clock = "monotonic" if bound == "wall" else "process_time"
            monkeypatch.setattr(K.time, clock, lambda: float("inf"))
        raw = raw_event()
        if bound in ("scratch", "output"):
            raw = b"".join(raw_event(serial=i) for i in range(1, 300))
        with pytest.raises(Refused):
            replay.feed(raw)
            replay.finish(lambda i, p: {"path": str(i), "sha256": digest(p)}, {})
    no_sort_files(tmp_path)


@pytest.mark.parametrize("key", ["max_source_bytes", "max_records", "max_scratch_bytes", "max_output_bytes", "max_seconds", "max_cpu_seconds"])
@pytest.mark.parametrize("value", [True, 0, 1.5, "1", None, 2**50])
def test_frozen_allowances_are_strict_and_bounded(key, value):
    with pytest.raises(Refused, match="CONFIGURATION_INVALID"):
        K.configuration(config(**{key: value}))


def test_many_distinct_events_do_not_reset_or_overflow_in_memory_group_limit(tmp_path):
    raw = b"".join(f'type=USER_NOTE msg=audit(100.001:{i}): PRIVATE\n'.encode() for i in range(11000))
    result, pages = invoke(tmp_path, [raw])
    assert result["totals"]["source_events"] == 11000 and result["totals"]["source_records"] == 11000
    assert sum(g["facts"]["source_events"] for p in pages for g in p["groups"]) == 11000


@pytest.mark.parametrize("conflict", [False, True])
def test_late_records_are_joined_with_the_original_event_not_a_new_window(tmp_path, conflict):
    lines = raw_event().splitlines(keepends=True)
    middle = b"".join(f'type=USER_NOTE msg=audit(100.001:{i}): PRIVATE\n'.encode() for i in range(2, 10003))
    first = b"".join(lines if conflict else [lines[0], *lines[2:]])
    late = lines[1].replace(b"DO-NOT-EXPORT", b"CHANGED") if conflict else lines[1]
    if conflict:
        with pytest.raises(Refused, match="PATH_RECORD_AMBIGUOUS"):
            invoke(tmp_path, [first, middle, late])
    else:
        result, _ = invoke(tmp_path, [first, middle, late])
        assert result["totals"]["events"] == 1 and result["totals"]["pending_events"] == 0
        assert result["totals"]["source_events"] == 10002


def test_pages_are_chained_and_do_not_export_unknown_rule_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "PAGE_BYTES", 1000)
    result, pages = invoke(tmp_path, [b"".join(raw_event(serial=i) for i in range(1, 8))])
    assert len(pages) > 1 and pages[0]["previous_page_ref"] is None
    for index, page in enumerate(pages):
        assert page["index"] == index and page["binding"] == {"fixture": True}
        if index:
            assert page["previous_page_ref"] == result["fact_pages"][index - 1]
        assert digest(page) == result["fact_pages"][index]["sha256"]
    with K.Replay(config(), host="omniverse2", keys=KEYS, scratch_parent=tmp_path) as replay:
        replay.feed(raw_event(key="PRIVATE-UNSELECTED-RULE"))
        assert b"PRIVATE" not in replay.database.read_bytes()


def test_invalid_integer_subclass_and_changed_source_refuse():
    class Integer(int):
        pass

    with pytest.raises(Refused):
        K.configuration(config(max_records=Integer(1)))
    with pytest.raises(Refused):
        K.configuration(config(source_sha256="f" * 64))


@pytest.mark.parametrize("phase", ["active", "initialization"])
def test_hard_crash_reaps_anonymous_sort_storage_without_external_cleanup(tmp_path, phase):
    script = '''import json,os,sys,time
from forge_factory.afo import kernel_replay as K
if sys.argv[3]=="initialization":
    original=K.sqlite3.connect
    def pause(*a,**k):
        c=original(*a,**k)
        print("INIT",flush=True)
        time.sleep(30)
        return c
    K.sqlite3.connect=pause
with K.Replay(json.loads(sys.argv[1]),host="omniverse2",keys=[],scratch_parent=sys.argv[2]) as r:
    for i in range(12000):r.feed(f"type=USER_NOTE msg=audit(100.001:{i}): PRIVATE\\n".encode())
    assert os.stat(r.database).st_size>4096
    print(os.stat(r.database).st_nlink,flush=True)
    time.sleep(30)
'''
    before = set(tmp_path.iterdir())
    child = subprocess.Popen([sys.executable, "-c", script, json.dumps(config()), str(tmp_path), phase],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with selectors.DefaultSelector() as poll:
            poll.register(child.stdout, selectors.EVENT_READ)
            assert poll.select(10), "owned scratch child did not become ready"
        assert child.stdout.readline() == (b"0\n" if phase == "active" else b"INIT\n")
        owned = {tmp_path / ".kernel-replay-init-owner.json", tmp_path / ".kernel-replay-init.lock"}
        slot = tmp_path / ".kernel-replay-init.sqlite3"
        assert set(tmp_path.iterdir()) == before | owned | ({slot} if phase == "initialization" else set())
        child.kill()
        assert child.wait(timeout=10) == -signal.SIGKILL
        with K.Replay(config(), host="omniverse2", keys=KEYS, scratch_parent=tmp_path) as replay:
            assert replay.input_bytes == replay.lines == 0
            assert os.stat(replay.database).st_nlink == 0
        assert set(tmp_path.iterdir()) == before | owned
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        child.stdout.close()


@pytest.mark.parametrize("change", ["no-owner", "wrong-owner", "hardlink", "symlink", "public-mode", "live-initializer"])
def test_unowned_or_live_scratch_is_never_truncated(tmp_path, change):
    from forge_factory.afo import soak

    slot = tmp_path / ".kernel-replay-init.sqlite3"
    if change == "no-owner":
        slot.write_bytes(b"OWNER-DATA")
    elif change == "wrong-owner":
        immutable_json(tmp_path / ".kernel-replay-init-owner.json", {"other": True})
    else:
        with K.Replay(config(), host="omniverse2", keys=KEYS, scratch_parent=tmp_path):
            pass
        original = tmp_path / "preserved"
        original.write_bytes(b"OWNER-DATA")
        original.chmod(0o600)
        if change == "hardlink":
            os.link(original, slot)
        elif change == "symlink":
            slot.symlink_to(original)
        else:
            slot.write_bytes(b"OWNER-DATA")
            slot.chmod(0o644 if change == "public-mode" else 0o600)
    before = slot.read_bytes() if slot.exists() else None

    def attempt():
        with pytest.raises(Refused):
            K.Replay(config(), host="omniverse2", keys=KEYS, scratch_parent=tmp_path)

    if change == "live-initializer":
        with soak.locked(slot):
            attempt()
    else:
        attempt()
    assert (slot.read_bytes() if slot.exists() else None) == before


def test_legacy_chain_wrapper_never_returns_a_partial_result(logs, monkeypatch):
    _, cfg = logs
    monkeypatch.setattr(S, "verify_chain_batches", lambda *a, **k: iter([{"status": "CAPTURED_BYTE_PREFIX_PARTIAL"}]))
    with pytest.raises(Refused, match="REPLAY_INCOMPLETE"):
        S.verify_chain(cfg, [])


@pytest.fixture
def continuous_plan(segmented_plan):
    p, active, cfg, old_host, _ = segmented_plan
    plan = copy.deepcopy(json.loads(Path(old_host["path"]).read_bytes()))
    cfg["max_bytes"] = plan["segments"]["max_bytes"] = 113
    plan["continuous_replay"] = config()
    path = p.tmp / "continuous-host-plan.json"
    immutable_json(path, plan)
    host_ref = {"path": str(path), "sha256": sha256_file(path)}
    manifest = Q.freeze("operation-24", p.tmp / "continuous-manifest.json", identity=identity(), inputs=[p.path, path])
    return p, active, cfg, host_ref, manifest


def test_existing_command_routes_frozen_opt_in_and_publishes_bound_pages(continuous_plan):
    p, active, cfg, host, manifest = continuous_plan
    active.write_bytes(raw_event(host=H.socket.gethostname()))
    refs = capture_refs(continuous_plan, (active.stat().st_size + cfg["max_bytes"] - 1) // cfg["max_bytes"])
    result = H.verify_segments(manifest, p.ref, host, refs, p.tmp / "result.json")
    assert result["schema"] == "forge-c/host-audit-segment-replay/2"
    assert result["status"] == "INCOMPLETE_SOURCE_COVERAGE" and result["unexpected_interventions"] is None
    events = result["kernel_event_replay"]
    assert events["totals"]["events"] == 1 and events["status"] == "SELECTED_EVENT_FACTS_REPLAYED"
    page = H.observer.bound_json(events["fact_pages"][0])
    assert page["binding"]["capture_refs_sha256"] == digest(refs)
    assert page["binding"]["host_plan_ref"] == host and page["previous_page_ref"] is None
    assert H.verify_segments(manifest, p.ref, host, refs, p.tmp / "result.json") == result


def test_metadata_allowance_counts_original_serialized_whitespace(continuous_plan, monkeypatch):
    p, _, _, host, manifest = continuous_plan
    ref = capture_refs(continuous_plan, 1)[0]
    path = p.tmp / "padded-capture.json"
    raw = canonical(json.loads(Path(ref["path"]).read_bytes())) + b" " * 8192
    path.write_bytes(raw)
    padded = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    monkeypatch.setattr(H.observer, "MAX_TRACE_BYTES", 4096)
    with pytest.raises(Refused, match="NOT_BOUNDED_REGULAR_FILE"):
        H.verify_segments(manifest, p.ref, host, [padded], p.tmp / "refused.json")
    assert not (p.tmp / "refused.json").exists()


@pytest.mark.parametrize("change", ["first", "duplicate", "hash", "sequence", "parent", "boot"])
def test_original_capture_history_and_boots_are_not_replaced_by_cursor(continuous_plan, change):
    p, active, _, host, manifest = continuous_plan
    active.write_bytes(raw_event(host=H.socket.gethostname()))
    refs = capture_refs(continuous_plan, 2)
    if change == "first":
        refs = refs[1:]
    elif change == "duplicate":
        refs[1] = refs[0]
    elif change == "hash":
        refs[0]["sha256"] = "0" * 64
    else:
        d = json.loads(Path(refs[1]["path"]).read_bytes())
        if change == "sequence":
            d["kernel_segment"]["sequence"] = True
        elif change == "parent":
            d["kernel_segment"]["previous_segment_ref"] = None
        else:
            d["boot_id"] = "00000000-0000-0000-0000-000000000000"
        path = p.tmp / "changed.json"
        immutable_json(path, d)
        refs[1] = {"path": str(path), "sha256": sha256_file(path)}
    if change == "boot":
        result = H.verify_segments(manifest, p.ref, host, refs, p.tmp / "result.json")
        assert result["kernel_event_replay"]["status"] == "BLOCKED"
        assert result["kernel_event_replay"]["fact_pages"] == []
    else:
        with pytest.raises(Refused):
            H.verify_segments(manifest, p.ref, host, refs, p.tmp / "result.json")


def test_actual_128_mib_boundary_with_compound_event_spanning_all_ranges(continuous_plan):
    p, active, _, old_host, _ = continuous_plan
    plan = json.loads(Path(old_host["path"]).read_bytes())
    plan["segments"]["max_bytes"] = 8 * 1024**2
    path = p.tmp / "large-host-plan.json"
    immutable_json(path, plan)
    host = {"path": str(path), "sha256": sha256_file(path)}
    manifest = Q.freeze("operation-24", p.tmp / "large-manifest.json", identity=identity(), inputs=[p.path, path])
    lines = raw_event(host=H.socket.gethostname()).splitlines(keepends=True)
    filler = b'type=USER_NOTE msg=audit(100.001:2): ' + b'PRIVATE-' * 8000 + b'\n'
    repeats = (128 * 1024**2) // len(filler) + 1
    with active.open("wb") as stream:
        stream.write(b"".join(lines[:2]))
        for _ in range(repeats):
            stream.write(filler)
        stream.write(b"".join(lines[2:]))
    size = active.stat().st_size
    assert size > 128 * 1024**2
    count = (size + plan["segments"]["max_bytes"] - 1) // plan["segments"]["max_bytes"]
    refs = capture_refs((p, active, plan["segments"], host, manifest), count)
    segments = [json.loads(Path(ref["path"]).read_bytes())["kernel_segment"] for ref in refs]
    with pytest.raises(Refused, match="CHAIN_BYTE_BOUND_EXCEEDED"):
        S.verify_chain(plan["segments"], segments)
    result = H.verify_segments(manifest, p.ref, host, refs, p.tmp / "large-result.json")
    events = result["kernel_event_replay"]
    assert result["byte_chain"]["bytes"] == size and result["byte_chain"]["uncaptured_final_source_bytes"] == 0
    assert events["input_bytes"] == size and events["totals"]["events"] == 1
    assert events["totals"]["source_records"] == 5 and events["totals"]["duplicate_records"] == repeats - 1
    assert events["totals"]["pending_events"] == 0 and events["pending_line"]["length"] == 0
    assert events["status"] == "SELECTED_EVENT_FACTS_REPLAYED" and result["unexpected_interventions"] is None
    assert "PRIVATE" not in json.dumps(result) + ''.join(Path(r["path"]).read_text() for r in events["fact_pages"])
    no_sort_files(p.tmp)
