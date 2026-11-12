"""Synthetic native-format records; actual retained byte/descriptor IO, no host qualification."""
# ruff: noqa: F811

import hashlib
import json
import math
from pathlib import Path

import pytest
from forge_factory.afo import audit_segments as S
from forge_factory.afo import host_audit as H
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.common import sha256_file
from test_da014_audit_segments import capture_refs, logs, root_observation, segmented_plan  # noqa: F401
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_host_audit import KEYS, raw_event


def replay(chunks):
    parser = H.EventReplay(host="omniverse2", keys=KEYS)
    for chunk in chunks:
        parser.feed(chunk)
    return parser.finish()


def test_every_byte_split_including_utf8_preserves_independently_expected_event_facts():
    raw = raw_event(secret="PRIVATE-é-雪")
    expected = sorted(hashlib.sha256(line).hexdigest() for line in raw.split(b"\n")[:-1])
    for offset in range(len(raw) + 1):
        out = replay([raw[:offset], b"", raw[offset:]])
        assert out["status"] == "SELECTED_EVENT_FACTS_REPLAYED" and out["blockers"] == []
        event = out["facts"]["events"][0]
        assert event["serial"] == 1 and event["pid"] == 13 and event["path_records"] == 1
        assert event["source_record_hashes"] == expected and event["syscall"] == 257
        assert out["input_bytes"] == len(raw) and out["input_sha256"] == hashlib.sha256(raw).hexdigest()
        assert out["pending_line"]["length"] == 0 and out["unexpected_interventions"] is None
        assert "PRIVATE" not in json.dumps(out) and "雪" not in json.dumps(out)
        assert "PRIVATE-é-雪".encode().hex() not in json.dumps(out) and "/private/" not in json.dumps(out)


@pytest.mark.parametrize("size", [1, 2, 7, 37, 65536])
def test_interleaved_events_and_duplicate_records_keep_exact_group_identity(size):
    a, b = raw_event(), raw_event(serial=2)
    rows = [line for pair in zip(a.splitlines(keepends=True), b.splitlines(keepends=True), strict=True) for line in pair]
    raw = b"".join(rows) + a
    out = replay([raw[i:i + size] for i in range(0, len(raw), size)])
    assert [e["serial"] for e in out["facts"]["events"]] == [1, 2]
    assert out["facts"]["source_events"] == 2 and out["facts"]["source_records"] == 8
    assert out["facts"]["duplicate_records"] == 4 and out["pending_events"] == []


def test_native_enrichment_separator_stays_inside_its_record_and_is_not_exported():
    raw = raw_event().replace(b"\n", b"\x1dUID=PRIVATE-ACCOUNT\n")
    out = replay([raw])
    assert len(out["facts"]["events"]) == 1 and out["facts"]["source_records"] == 4
    assert "PRIVATE-ACCOUNT" not in json.dumps(out)
    # Regression for the legacy parser: str.splitlines() treated 0x1d as a
    # newline, even though auditd uses it for record-local enrichment.
    assert H.events(raw, host="omniverse2", keys=KEYS)["source_records"] == 4


@pytest.mark.parametrize("change", ["missing-path", "wrong-path-item", "no-boundary", "partial-line"])
def test_prefix_end_never_flushes_unfinished_selected_events(change):
    raw = raw_event()
    if change == "missing-path":
        raw = b"\n".join(line for line in raw.splitlines() if b"type=PATH" not in line) + b"\n"
    elif change == "wrong-path-item":
        raw = raw.replace(b"item=0", b"item=1")
    elif change == "no-boundary":
        raw = b"\n".join(line for line in raw.splitlines() if b"type=PROCTITLE" not in line) + b"\n"
    else:
        raw = raw[:-5]
    out = replay([raw])
    assert out["status"] == "INCOMPLETE_EVENT_PREFIX" and out["facts"]["events"] == []
    assert len(out["pending_events"]) == 1 and out["unexpected_interventions"] is None
    if change == "wrong-path-item":
        assert out["pending_events"][0]["path_records"] == out["pending_events"][0]["expected_path_records"] == 1
        assert not out["pending_events"][0]["path_item_coverage"]
    if change == "partial-line":
        assert "KERNEL_EVENT_PARTIAL_LINE" in out["blockers"]


def test_explicit_eoe_is_an_observed_boundary_without_fabricating_timeout_or_wall_clock():
    raw = b"\n".join(line for line in raw_event().splitlines() if b"type=PROCTITLE" not in line) + b"\n"
    raw += b"type=EOE msg=audit(100.001:1):\n"
    out = replay([raw])
    assert len(out["facts"]["events"]) == 1 and out["pending_events"] == []
    assert "EOE" in out["facts"]["events"][0]["record_types"]


def test_orphan_records_and_empty_input_do_not_prove_zero_interventions():
    out = replay([b'type=PATH msg=audit(100.001:1): item=0 name="PRIVATE"\n'])
    assert out["orphan_compound_groups"] == 1 and "KERNEL_EVENT_ORPHAN_COMPOUND_GROUPS" in out["blockers"]
    assert out["unexpected_interventions"] is None and replay([b""])["unexpected_interventions"] is None


def test_integrity_records_are_retained_without_exporting_raw_configuration_text():
    out = replay([b"type=CONFIG_CHANGE msg=audit(100.001:3): op=PRIVATE-RULE\n"])
    assert out["facts"]["integrity_events"] == [{"host": "omniverse2", "at": 100.001, "serial": 3,
                                               "types": ["CONFIG_CHANGE"]}]
    assert "PRIVATE" not in json.dumps(out) and out["unexpected_interventions"] is None


@pytest.mark.parametrize("maximum", [False, 0, H.observer.MAX_TRACE_BYTES + 1])
def test_invalid_resource_allowances_cannot_enlarge_or_disable_parser_bounds(maximum):
    with pytest.raises(Refused, match="BOUND_INVALID"):
        H.EventReplay(host="omniverse2", keys=KEYS, maximum=maximum)


def test_settled_prefix_cannot_be_extended_as_if_it_were_the_same_verification():
    parser = H.EventReplay(host="omniverse2", keys=KEYS)
    parser.feed(raw_event())
    parser.finish()
    with pytest.raises(Refused, match="ALREADY_SETTLED"):
        parser.feed(raw_event(serial=2))


@pytest.mark.parametrize("change", ["host", "bad-utf8", "ambiguous-syscall", "ambiguous-path", "invalid-line"])
def test_malformed_stream_poisoning_cannot_be_followed_by_a_successful_finish(change):
    raw = raw_event()
    if change == "host":
        raw = raw_event(host="another-host")
    elif change == "bad-utf8":
        raw = b"\xff\n"
    elif change == "ambiguous-syscall":
        raw += raw.splitlines(keepends=True)[0].replace(b"pid=13", b"pid=14")
    elif change == "ambiguous-path":
        raw += b'type=PATH msg=audit(100.001:1): item=0 name="DIFFERENT"\n'
    else:
        raw = b"PRIVATE-COMMAND\n"
    parser = H.EventReplay(host="omniverse2", keys=KEYS)
    with pytest.raises(Refused):
        parser.feed(raw)
    with pytest.raises(Refused, match="ALREADY_SETTLED"):
        parser.finish()
    with pytest.raises(Refused, match="ALREADY_SETTLED"):
        parser.feed(raw_event())


@pytest.mark.parametrize("bound", ["bytes", "events", "records", "line"])
def test_parser_bounds_are_cumulative_and_never_silently_drop_earlier_events(monkeypatch, bound):
    raw = raw_event()
    parser = H.EventReplay(host="omniverse2", keys=KEYS, maximum=len(raw))
    if bound == "bytes":
        parser.feed(raw)
        raw = b"\n"
    elif bound == "events":
        monkeypatch.setattr(H, "MAX_EVENTS", 1)
        raw += raw_event(serial=2)
        parser = H.EventReplay(host="omniverse2", keys=KEYS)
    elif bound == "records":
        monkeypatch.setattr(H, "MAX_RECORDS", 1)
    else:
        monkeypatch.setattr(H, "MAX_LINE", 10)
        raw = b"x" * 11  # No newline: the pending buffer is bounded too.
    with pytest.raises(Refused):
        parser.feed(raw)


@pytest.mark.parametrize("segmented_plan", [97], indirect=True)
def test_executable_segment_replay_feeds_each_verified_range_once(segmented_plan, monkeypatch):
    p, active, cfg, host_ref, manifest = segmented_plan
    raw = raw_event(host=H.socket.gethostname()) + raw_event(serial=2, host=H.socket.gethostname())
    active.write_bytes(raw)
    refs = capture_refs(segmented_plan, math.ceil(len(raw) / cfg["max_bytes"]))
    original, lengths = S.replay, []
    def record_replay(*args, **kwargs):
        data = original(*args, **kwargs)
        lengths.append(len(data))
        return data
    monkeypatch.setattr(S, "replay", record_replay)
    out = H.verify_segments(manifest, p.ref, host_ref, refs, p.tmp / "event-replay.json")
    assert len(lengths) == len(refs) and sum(lengths) == len(raw)
    events = out["kernel_event_replay"]
    assert [e["serial"] for e in events["facts"]["events"]] == [1, 2]
    assert events["input_sha256"] == hashlib.sha256(raw).hexdigest()
    assert out["unexpected_interventions"] is None and out["status"] == "INCOMPLETE_SOURCE_COVERAGE"
    assert "KERNEL_AUDIT_FULL_RECORD_AND_WINDOW_QUALIFICATION_REQUIRED" in out["blockers"]


@pytest.mark.parametrize("segmented_plan", [128], indirect=True)
def test_boot_change_blocks_event_identity_merging_without_destroying_byte_proof(segmented_plan):
    p, active, _, host_ref, manifest = segmented_plan
    active.write_bytes(raw_event(host=H.socket.gethostname()))
    refs = capture_refs(segmented_plan)
    row = json.loads(Path(refs[1]["path"]).read_text())
    row["boot_id"] = "00000000-0000-0000-0000-000000000000"
    changed = p.tmp / "other-boot.json"
    immutable_json(changed, row)
    refs[1] = {"path": str(changed), "sha256": sha256_file(changed)}
    out = H.verify_segments(manifest, p.ref, host_ref, refs, p.tmp / "boot-replay.json")
    assert out["byte_chain"]["status"] == "CAPTURED_BYTE_PREFIX_REPLAYED"
    assert out["kernel_event_replay"]["facts"] is None
    assert "KERNEL_EVENT_REPLAY_BOOT_CONTINUITY_UNKNOWN" in out["blockers"]


@pytest.mark.parametrize("segmented_plan", [1024], indirect=True)
def test_same_compound_event_survives_a_retained_rotation_inside_a_utf8_record(segmented_plan, monkeypatch):
    p, active, _, host_ref, manifest = segmented_plan
    raw = raw_event(host=H.socket.gethostname(), secret="PRIVATE-é")
    split = raw.index("é".encode()) + 1
    active.write_bytes(raw[:split])
    first = capture_refs(segmented_plan, 1)[0]
    old = S._key(active.stat())
    active.rename(str(active) + ".1")
    active.write_bytes(raw[split:])
    new = S._key(active.stat())
    monkeypatch.setattr(S, "descriptor_observation", lambda _: root_observation(old, new))
    original = H.preflight
    def synthetic_status():
        result = original()
        result["kernel_status"] = {"pid": 123}
        return result
    monkeypatch.setattr(H, "preflight", synthetic_status)
    second = p.tmp / "rotated-event.json"
    H.capture(manifest, p.ref, host_ref, second, previous_ref=first)
    refs = [first, {"path": str(second), "sha256": sha256_file(second)}]
    out = H.verify_segments(manifest, p.ref, host_ref, refs, p.tmp / "rotation-event-replay.json")
    assert out["byte_chain"]["generations"] == 2
    report = out["kernel_event_replay"]
    assert len(report["facts"]["events"]) == 1 and report["facts"]["source_records"] == 4
    assert report["input_sha256"] == hashlib.sha256(raw).hexdigest() and report["pending_events"] == []


def test_invalid_record_bytes_remain_a_byte_proof_but_never_an_empty_valid_event_log(segmented_plan):
    p, _, _, host_ref, manifest = segmented_plan
    refs = capture_refs(segmented_plan, 3)
    out = H.verify_segments(manifest, p.ref, host_ref, refs, p.tmp / "invalid-events.json")
    assert out["byte_chain"]["status"] == "CAPTURED_BYTE_PREFIX_REPLAYED"
    assert out["kernel_event_replay"]["facts"] is None and out["kernel_event_replay"]["status"] == "BLOCKED"
    assert "HOST_AUDIT_RECORD_HEADER_INVALID" in out["blockers"]
