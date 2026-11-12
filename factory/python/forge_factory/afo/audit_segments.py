"""Bounded, restartable byte-range capture of retained protected OS audit files.

Cursors and source hashes live in existing qualification artifacts. No new log,
database, service, rule or retention authority is created. Byte continuity and
descriptor observations do not establish complete audit/event/host coverage.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

from ..lrtx.provider_process import identity
from . import fault_observer as observer
from . import host_audit as host
from .durable import Refused, digest

ANCHOR_BYTES = 65536
MAX_PATHS = 64
MAX_FDS = 1024
MAX_SEGMENTS = 10000
SCHEMA = "forge-c/kernel-audit-segment/1"


def configuration(value, active):
    if (
        not isinstance(value, dict) or set(value) != {"reader_sha256", "paths", "max_bytes"}
        or value["reader_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or type(value["max_bytes"]) is not int or not 1 <= value["max_bytes"] <= observer.MAX_BYTES
        or not isinstance(value["paths"], list) or not 1 <= len(value["paths"]) <= MAX_PATHS
        or any(not isinstance(p, str) or len(p) > 4096 or not Path(p).is_absolute() for p in value["paths"])
        or len(set(value["paths"])) != len(value["paths"]) or value["paths"][0] != active
        or any(p != active + "." + str(i) for i, p in enumerate(value["paths"][1:], 1))
    ):
        raise Refused("AUDIT_SEGMENT_CONFIGURATION_INVALID")
    return value


def _key(s):
    return (s.st_dev, s.st_ino) if hasattr(s, "st_dev") else (s["device"], s["inode"])


def _read(fd, offset, length):
    if (
        type(offset) is not int or not 0 <= offset <= 2**63 - 1
        or type(length) is not int or not 0 <= length <= observer.MAX_BYTES or offset + length > 2**63 - 1
    ):
        raise Refused("AUDIT_SEGMENT_RANGE_INVALID")
    parts, count = [], 0
    while count < length:
        data = os.pread(fd, min(65536, length - count), offset + count)
        if not data:
            raise Refused("AUDIT_SEGMENT_SOURCE_TRUNCATED")
        parts.append(data)
        count += len(data)
    return b"".join(parts)


def _anchor(fd, end):
    offset = max(0, end - ANCHOR_BYTES)
    data = _read(fd, offset, end - offset)
    return {"offset": offset, "length": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _check_anchor(fd, value, end):
    if not isinstance(value, dict) or value != _anchor(fd, end):
        raise Refused("AUDIT_SEGMENT_ANCHOR_CHANGED")


def _find(paths, key):
    # Check every successful candidate through the same protected open, never
    # infer identity from a pathname that can refer to a different rotated file.
    for path in paths:
        try:
            with host.protected_log(path) as fd:
                if _key(os.fstat(fd)) == key:
                    return path
        except FileNotFoundError:
            continue
    raise Refused("AUDIT_SEGMENT_RETAINED_SOURCE_UNAVAILABLE")


def _fds(pid):
    base = Path("/proc") / str(pid)
    with os.scandir(base / "fd") as entries:
        names = []
        for entry in entries:
            if len(names) >= MAX_FDS or not entry.name.isdecimal():
                raise Refused("AUDIT_SEGMENT_DESCRIPTOR_BOUND_EXCEEDED")
            names.append(entry.name)
    rows = []
    for name in sorted(names, key=int):
        s = (base / "fd" / name).stat()
        raw = observer.read_bytes(base / "fdinfo" / name, 4096)
        matches = re.findall(rb"^flags:\s+([0-7]{1,20})$", raw, re.M)
        if len(matches) != 1:
            raise Refused("AUDIT_SEGMENT_DESCRIPTOR_FLAGS_UNKNOWN")
        rows.append({"fd": int(name), "device": s.st_dev, "inode": s.st_ino,
                     "regular": stat.S_ISREG(s.st_mode), "flags": int(matches[0], 8)})
    return rows


def descriptor_observation(pid):
    """Two native censuses with stable process identity; no command/path export."""
    if type(pid) is not int or not 1 <= pid <= 2**31 - 1:
        raise Refused("AUDIT_SEGMENT_DAEMON_PID_UNKNOWN")
    before = identity(pid)
    if not before or before.get("state") in ("Z", "X", "x"):
        raise Refused("AUDIT_SEGMENT_DAEMON_IDENTITY_UNKNOWN")
    first, second = _fds(pid), _fds(pid)
    after = identity(pid)
    def stable(p):
        return {k: v for k, v in p.items() if k != "state"} if p else None
    if stable(before) != stable(after) or first != second or not after or after.get("state") in ("Z", "X", "x"):
        raise Refused("AUDIT_SEGMENT_DESCRIPTOR_CENSUS_UNSTABLE")
    return {"pid": pid, "identity": stable(after), "descriptors": second,
            "scope": "NATIVE_PROCESS_DESCRIPTOR_OBSERVATION_ONLY"}


def rotation_facts(observation, old_key, new_key, pid):
    """Derive a handoff from measured descriptors, never an input closed=True flag."""
    if (
        type(pid) is not int or not 1 <= pid <= 2**31 - 1
        or not isinstance(observation, dict) or type(observation.get("pid")) is not int or observation["pid"] != pid
        or observation.get("scope") != "NATIVE_PROCESS_DESCRIPTOR_OBSERVATION_ONLY"
        or not isinstance(observation.get("identity"), dict) or type(observation["identity"].get("uid")) is not int
        or observation["identity"]["uid"] != 0
        or not isinstance(observation.get("descriptors"), list)
        or not 1 <= len(observation["descriptors"]) <= MAX_FDS
    ):
        raise Refused("AUDIT_SEGMENT_DAEMON_HANDOFF_UNPROVEN")
    rows = observation["descriptors"]
    if any(
        not isinstance(r, dict) or set(r) != {"fd", "device", "inode", "regular", "flags"}
        or any(type(r.get(k)) is not int or r[k] < 0 for k in ("fd", "device", "inode", "flags"))
        or type(r.get("regular")) is not bool for r in rows
    ) or len({r["fd"] for r in rows}) != len(rows):
        raise Refused("AUDIT_SEGMENT_DESCRIPTOR_FACTS_INVALID")
    if any(_key(r) == old_key for r in rows):
        raise Refused("AUDIT_SEGMENT_OLD_SOURCE_STILL_OPEN")
    if not any(_key(r) == new_key and r["regular"] and r["flags"] & os.O_APPEND
               and r["flags"] & os.O_ACCMODE in (os.O_WRONLY, os.O_RDWR) for r in rows):
        raise Refused("AUDIT_SEGMENT_NEW_SOURCE_WRITER_UNPROVEN")


def _cursor(value):
    if (
        not isinstance(value, dict) or set(value) != {"source", "end", "anchor", "sealed_sources"}
        or not isinstance(value["source"], dict) or set(value["source"]) != {"device", "inode"}
        or any(type(v) is not int or v < 0 for v in value["source"].values())
        or type(value["end"]) is not int or not 0 <= value["end"] <= 2**63 - 1
        or not isinstance(value["sealed_sources"], list) or len(value["sealed_sources"]) > MAX_PATHS
    ):
        raise Refused("AUDIT_SEGMENT_CURSOR_INVALID")
    for entry in [value, *value["sealed_sources"]]:
        if (
            not isinstance(entry, dict) or not {"source", "end", "anchor"} <= set(entry)
            or (entry is not value and set(entry) != {"source", "end", "anchor"})
            or not isinstance(entry["source"], dict) or set(entry["source"]) != {"device", "inode"}
            or any(type(v) is not int or v < 0 for v in entry["source"].values())
            or type(entry["end"]) is not int or not 0 <= entry["end"] <= 2**63 - 1
            or not isinstance(entry["anchor"], dict) or set(entry["anchor"]) != {"offset", "length", "sha256"}
            or type(entry["anchor"].get("offset")) is not int
            or entry["anchor"]["offset"] != max(0, entry["end"] - ANCHOR_BYTES)
            or type(entry["anchor"].get("length")) is not int
            or entry["anchor"]["length"] != min(entry["end"], ANCHOR_BYTES)
            or not isinstance(entry["anchor"].get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["anchor"]["sha256"])
        ):
            raise Refused("AUDIT_SEGMENT_CURSOR_INVALID")
    keys = [_key(entry["source"]) for entry in [value, *value["sealed_sources"]]]
    if len(set(keys)) != len(keys):
        raise Refused("AUDIT_SEGMENT_CURSOR_GENERATION_DUPLICATE")
    return value


def validate(segment, config):
    if (
        not isinstance(segment, dict) or segment.get("schema") != SCHEMA
        or not isinstance(segment.get("source"), dict)
        or segment.get("scope") != "PROTECTED_BYTE_SEGMENTS_NOT_EVENT_COMPLETENESS_OR_HOST_AUDIT"
    ):
        raise Refused("AUDIT_SEGMENT_SCHEMA_INVALID")
    cursor = _cursor(segment.get("cursor"))
    source = segment["source"]
    if (
        set(source) != {"path", "device", "inode", "offset", "length", "sha256", "size_at_open", "size_at_close"}
        or source["path"] not in config["paths"]
        or any(type(source.get(k)) is not int or not 0 <= source[k] <= 2**63 - 1
               for k in ("device", "inode", "offset", "length", "size_at_open", "size_at_close"))
        or not 0 <= source["length"] <= config["max_bytes"]
        or source["offset"] + source["length"] != cursor["end"]
        or cursor["end"] > source["size_at_open"] or source["size_at_open"] > source["size_at_close"]
        or _key(source) != _key(cursor["source"])
        or not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
    ):
        raise Refused("AUDIT_SEGMENT_SOURCE_INVALID")
    return segment


def read(config, previous=None, *, daemon_pid=None):
    """Read at most max_bytes, retaining earlier generations and an overlap anchor.

    Raw bytes are returned to a caller only for immediate bounded verification;
    the persisted segment contains references/hashes, never audit bodies/argv.
    """
    previous = _cursor(previous) if previous is not None else None
    if not isinstance(config, dict) or not isinstance(config.get("paths"), list) or not config["paths"]:
        raise Refused("AUDIT_SEGMENT_CONFIGURATION_INVALID")
    configuration(config, config["paths"][0])
    paths, maximum = config["paths"], config["max_bytes"]
    sealed = list(previous["sealed_sources"]) if previous else []
    for retired in sealed:
        path = _find(paths, _key(retired["source"]))
        with host.protected_log(path) as fd:
            if os.fstat(fd).st_size != retired["end"]:
                raise Refused("AUDIT_SEGMENT_RETIRED_SOURCE_CHANGED")
            _check_anchor(fd, retired["anchor"], retired["end"])
    with host.protected_log(paths[0]) as fd:
        active = _key(os.fstat(fd))
    key = _key(previous["source"]) if previous else active
    path = _find(paths, key)
    if key != active and paths.index(path) != 1:
        raise Refused("AUDIT_SEGMENT_MULTIPLE_ROTATIONS_REQUIRE_HANDOFF_EVIDENCE")
    offset = previous["end"] if previous else 0
    rotation = None
    with host.protected_log(path) as fd:
        before = os.fstat(fd)
        if _key(before) != key or before.st_size < offset:
            raise Refused("AUDIT_SEGMENT_SOURCE_CHANGED_OR_TRUNCATED")
        if previous:
            _check_anchor(fd, previous["anchor"], offset)
        if key != active and before.st_size == offset:
            observation = descriptor_observation(daemon_pid)
            rotation_facts(observation, key, active, daemon_pid)
            if os.fstat(fd).st_size != offset:
                raise Refused("AUDIT_SEGMENT_OLD_SOURCE_GREW_DURING_HANDOFF")
            sealed.append({"source": previous["source"], "end": offset, "anchor": previous["anchor"]})
            if len(sealed) >= MAX_PATHS:
                raise Refused("AUDIT_SEGMENT_ROTATION_COUNT_BOUND_EXCEEDED")
            rotation = {"from": previous["source"], "to": {"device": active[0], "inode": active[1]},
                        "observation": observation}
    if rotation:
        path, key, offset = paths[0], active, 0
    with host.protected_log(path) as fd:
        before = os.fstat(fd)
        if _key(before) != key or before.st_size < offset:
            raise Refused("AUDIT_SEGMENT_SOURCE_CHANGED_OR_TRUNCATED")
        if previous and not rotation:
            _check_anchor(fd, previous["anchor"], offset)
        length = min(maximum, before.st_size - offset)
        raw = _read(fd, offset, length)
        end = offset + length
        anchor = _anchor(fd, end)
        after = os.fstat(fd)
        if after.st_size < before.st_size or _key(after) != key:
            raise Refused("AUDIT_SEGMENT_SOURCE_CHANGED_DURING_READ")
        # Re-read this bounded range to detect an in-place change during capture.
        if _read(fd, offset, length) != raw:
            raise Refused("AUDIT_SEGMENT_SOURCE_REWRITTEN_DURING_READ")
    source = {"path": str(path), "device": key[0], "inode": key[1], "offset": offset, "length": length,
              "sha256": hashlib.sha256(raw).hexdigest(), "size_at_open": before.st_size, "size_at_close": after.st_size}
    cursor = {"source": {"device": key[0], "inode": key[1]}, "end": end, "anchor": anchor, "sealed_sources": sealed}
    return raw, {"schema": SCHEMA, "source": source, "cursor": cursor, "rotation": rotation,
                 "previous_cursor_sha256": digest(previous) if previous else None,
                 "scope": "PROTECTED_BYTE_SEGMENTS_NOT_EVENT_COMPLETENESS_OR_HOST_AUDIT"}


def replay(config, segment, *, check_anchor=True):
    """Re-read the retained protected range; aliases may move during rotation."""
    validate(segment, config)
    source = segment["source"]
    if type(source.get("length")) is not int or not 0 <= source["length"] <= config["max_bytes"]:
        raise Refused("AUDIT_SEGMENT_RANGE_INVALID")
    path = _find(config["paths"], _key(source))
    with host.protected_log(path) as fd:
        if _key(os.fstat(fd)) != _key(source):
            raise Refused("AUDIT_SEGMENT_REPLAY_IDENTITY_CHANGED")
        raw = _read(fd, source["offset"], source["length"])
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise Refused("AUDIT_SEGMENT_REPLAY_HASH_CHANGED")
        if check_anchor:
            _check_anchor(fd, segment["cursor"]["anchor"], source["offset"] + source["length"])
    return raw


def verify_chain(config, segments, *, consume=None):
    result = None
    for batch in verify_chain_batches(config, segments, consume=consume):
        result = batch
    if result is None or result.get("status") != "CAPTURED_BYTE_PREFIX_REPLAYED":
        raise Refused("AUDIT_SEGMENT_CHAIN_REPLAY_INCOMPLETE")
    return result


def verify_chain_batches(config, segments, *, consume=None, maximum=None, max_segments=MAX_SEGMENTS):
    """Reconstruct a captured prefix with bounded I/O and rolling anchor memory.

    Historical descriptor facts are checked structurally, not authenticated by
    this replay. A byte-chain result is neither event completeness nor proof of
    a complete time window, boot continuity or zero host interventions.
    """
    if not isinstance(config, dict) or not isinstance(config.get("paths"), list) or not config["paths"]:
        raise Refused("AUDIT_SEGMENT_CONFIGURATION_INVALID")
    configuration(config, config["paths"][0])
    maximum = observer.MAX_TRACE_BYTES if maximum is None else maximum
    if (type(maximum) is not int or not 1 <= maximum <= 2**40
            or type(max_segments) is not int or not 1 <= max_segments <= 50000):
        raise Refused("AUDIT_SEGMENT_REPLAY_ALLOWANCE_INVALID")
    if not isinstance(segments, list) or not 1 <= len(segments) <= max_segments:
        raise Refused("AUDIT_SEGMENT_CHAIN_COUNT_INVALID")
    for segment in segments:
        validate(segment, config)
    # Include final protected-anchor checks in the byte-I/O allowance. Rolling
    # anchors avoid re-reading 64 KiB for every small, adjacent range.
    final = segments[-1]["cursor"]
    terminal = [*final["sealed_sources"], final]
    total = sum(s["source"]["length"] for s in segments)
    if total + sum(s["anchor"]["length"] for s in terminal) > maximum:
        raise Refused("AUDIT_SEGMENT_CHAIN_BYTE_BOUND_EXCEEDED")
    previous, tail = None, b""
    for segment in segments:
        cursor, source, rotation = segment["cursor"], segment["source"], segment.get("rotation")
        if segment.get("previous_cursor_sha256") != (digest(previous) if previous else None):
            raise Refused("AUDIT_SEGMENT_CHAIN_PARENT_CHANGED")
        if previous is None:
            if source["offset"] or cursor["sealed_sources"] or rotation is not None:
                raise Refused("AUDIT_SEGMENT_CHAIN_INITIAL_PREFIX_REQUIRED")
        elif _key(previous["source"]) == _key(source):
            if (source["offset"] != previous["end"] or rotation is not None
                    or cursor["sealed_sources"] != previous["sealed_sources"]):
                raise Refused("AUDIT_SEGMENT_CHAIN_RANGE_DISCONTINUITY")
        else:
            if (
                source["offset"] or not isinstance(rotation, dict)
                or set(rotation) != {"from", "to", "observation"}
                or rotation["from"] != previous["source"] or rotation["to"] != cursor["source"]
                or cursor["sealed_sources"] != [*previous["sealed_sources"],
                    {k: previous[k] for k in ("source", "end", "anchor")}]
            ):
                raise Refused("AUDIT_SEGMENT_CHAIN_ROTATION_DISCONTINUITY")
            observation = rotation["observation"]
            rotation_facts(observation, _key(previous["source"]), _key(source),
                           observation.get("pid") if isinstance(observation, dict) else None)
            tail = b""
        raw = replay(config, segment, check_anchor=False)
        tail = (tail + raw)[-ANCHOR_BYTES:]
        expected = {"offset": max(0, cursor["end"] - ANCHOR_BYTES), "length": len(tail),
                    "sha256": hashlib.sha256(tail).hexdigest()}
        if cursor["anchor"] != expected:
            raise Refused("AUDIT_SEGMENT_CHAIN_ANCHOR_CHANGED")
        if consume is not None:
            consume(raw)
        previous = cursor
        yield {"status": "CAPTURED_BYTE_PREFIX_PARTIAL", "cursor_sha256": digest(cursor)}
    # Retired files must still be exactly at their sealed EOF, even if the late
    # append happened after all old ranges were captured. No history is dropped.
    remaining = None
    for entry in terminal:
        path = _find(config["paths"], _key(entry["source"]))
        with host.protected_log(path) as fd:
            s = os.fstat(fd)
            if _key(s) != _key(entry["source"]) or s.st_size < entry["end"]:
                raise Refused("AUDIT_SEGMENT_REPLAY_IDENTITY_CHANGED")
            if entry is not final and s.st_size != entry["end"]:
                raise Refused("AUDIT_SEGMENT_RETIRED_SOURCE_CHANGED")
            _check_anchor(fd, entry["anchor"], entry["end"])
            if entry is final:
                remaining = s.st_size - entry["end"]
    yield {"status": "CAPTURED_BYTE_PREFIX_REPLAYED", "segments": len(segments),
            "bytes": total, "generations": len(terminal), "segments_sha256": digest(segments),
            "last_cursor_sha256": digest(final), "uncaptured_final_source_bytes": remaining,
            "scope": "RETAINED_BYTE_PREFIX_NOT_EVENT_COMPLETENESS_OR_HOST_AUDIT"}
