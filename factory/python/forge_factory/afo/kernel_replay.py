"""Ephemeral external grouping for retained audit evidence, never a runtime store.

Original protected sources remain authoritative. The scratch SQLite B-tree only
sorts selected facts; its processing inode is unlinked. A single owned, locked
initialization slot is discarded and rebuilt from zero after an initializer crash.
No raw audit bodies, argv, commands or paths are persisted. Integrity tags are
process-local scratch checks, not authorization or durable completion receipts.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import stat
import time
from pathlib import Path

from . import fault_observer as O
from . import host_audit as H
from . import soak
from .durable import Refused, canonical, digest, immutable_json

MODULUS = 2**256
PAGE_BYTES = 8 * 1024 * 1024


def configuration(value):
    bounds = {"max_source_bytes": (1, 2**40), "max_records": (1, 10000000),
              "max_scratch_bytes": (65536, 8 * 1024**3), "max_output_bytes": (16384, 1024**3),
              "max_seconds": (1, 3600), "max_cpu_seconds": (1, 3600)}
    if (not isinstance(value, dict) or set(value) != {*bounds, "source_sha256"}
            or value["source_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            or any(type(value[k]) is not int or not lo <= value[k] <= hi for k, (lo, hi) in bounds.items())):
        raise Refused("KERNEL_REPLAY_CONFIGURATION_INVALID")
    return dict(value)


class Replay:
    """A finite verifier invocation with bounded disk, memory, time and output."""

    def __init__(self, config, *, host, keys, scratch_parent):
        self.config = configuration(config)
        self.parser = H.EventReplay(host=host, keys=keys)
        self.secret = secrets.token_bytes(32)
        self.expected = self.lines = self.input_bytes = 0
        self.input_hash = hashlib.sha256()
        self.partial = b""
        self.failed = self.closed = False
        self.started, self.cpu_started = time.monotonic(), time.process_time()
        try:
            self._open(scratch_parent)
        except BaseException as exc:
            if hasattr(self, "connection"):
                self.connection.close()
            if hasattr(self, "temporary"):
                self.temporary.close()
            if isinstance(exc, (OSError, sqlite3.Error)):
                raise Refused("KERNEL_REPLAY_SCRATCH_UNAVAILABLE", type(exc).__name__) from exc
            raise

    def _open(self, parent):
        parent = Path(parent)
        slot = parent / ".kernel-replay-init.sqlite3"
        marker = parent / ".kernel-replay-init-owner.json"
        owner = {"schema": "forge-c/ephemeral-kernel-sort-slot/1", "slot": slot.name,
                 "scope": "DISCARDABLE_SORT_INITIALIZATION_NOT_EVIDENCE_OR_RESUME_STATE"}
        # Existing qualification locking fences a live initializer, including
        # one stuck in native I/O. A crash leaves at most this single owned slot.
        with soak.locked(slot):
            if not marker.exists():
                if slot.exists() or slot.is_symlink():
                    raise Refused("KERNEL_REPLAY_SCRATCH_SLOT_NOT_OWNED")
                immutable_json(marker, owner)
            if O.read_json(marker, 4096) != owner:
                raise Refused("KERNEL_REPLAY_SCRATCH_SLOT_NOT_OWNED")
            fd = os.open(slot, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            self.temporary = os.fdopen(fd, "r+b")
            metadata = os.fstat(fd)
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                    or metadata.st_nlink != 1 or metadata.st_mode & 0o077):
                raise Refused("KERNEL_REPLAY_SCRATCH_SLOT_NOT_PROTECTED")
            os.ftruncate(fd, 0)  # Never consume stale scratch as a verified prefix.
            self.database = Path("/proc/self/fd") / str(fd)
            self.connection = sqlite3.connect(slot, isolation_level=None, timeout=0)
            c = self.connection
            c.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
            c.execute("PRAGMA page_size=4096")
            c.execute("PRAGMA journal_mode=OFF")
            c.execute("PRAGMA synchronous=OFF")
            c.execute("PRAGMA cache_size=-2048")
            c.execute("PRAGMA mmap_size=0")
            c.execute("PRAGMA max_page_count=" + str(self.config["max_scratch_bytes"] // 4096))
            c.execute("BEGIN EXCLUSIVE")
            c.execute("CREATE TABLE records (event TEXT, sha TEXT, data BLOB, copies INTEGER, tag BLOB, "
                      "PRIMARY KEY(event,sha)) WITHOUT ROWID")
            # SQLite must open its real filename before unlinking: giving its
            # VFS /proc/self/fd directly can create a different named database.
            slot.unlink()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()
        self.temporary.close()

    def _budget(self):
        if self.closed or self.failed:
            raise Refused("KERNEL_REPLAY_ALREADY_SETTLED")
        if (time.monotonic() - self.started > self.config["max_seconds"]
                or time.process_time() - self.cpu_started > self.config["max_cpu_seconds"]):
            raise Refused("KERNEL_REPLAY_TIME_ALLOWANCE_EXHAUSTED")

    def _tag(self, event, sha, data, copies):
        return hmac.digest(self.secret, canonical([event, sha, data.decode(), copies]), "sha256")

    def _check(self, event, sha, data, copies, tag):
        if (not isinstance(event, str) or not isinstance(sha, str) or not isinstance(data, bytes)
                or type(copies) is not int or not 1 <= copies <= self.config["max_records"]
                or not isinstance(tag, bytes) or len(tag) != 32):
            raise Refused("KERNEL_REPLAY_SCRATCH_INTEGRITY_CHANGED")
        try:
            expected = self._tag(event, sha, data, copies)
        except (ValueError, UnicodeError) as exc:
            raise Refused("KERNEL_REPLAY_SCRATCH_INTEGRITY_CHANGED") from exc
        if not hmac.compare_digest(tag, expected):
            raise Refused("KERNEL_REPLAY_SCRATCH_INTEGRITY_CHANGED")

    def _insert(self, record):
        self._budget()
        self.lines += 1
        if self.lines > self.config["max_records"]:
            raise Refused("KERNEL_REPLAY_RECORD_ALLOWANCE_EXHAUSTED")
        event, sha, data = canonical(record["identity"]).decode(), record["sha256"], canonical(record)
        if len(data) > 4096:
            raise Refused("KERNEL_REPLAY_SELECTED_RECORD_BOUND_EXCEEDED")
        row = self.connection.execute("SELECT data,copies,tag FROM records WHERE event=? AND sha=?", (event, sha)).fetchone()
        copies = 1
        if row is not None:
            prior, copies, tag = row
            self._check(event, sha, prior, copies, tag)
            if prior != data:
                raise Refused("KERNEL_REPLAY_SCRATCH_INTEGRITY_CHANGED")
            copies += 1
        self.connection.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)",
                                (event, sha, data, copies, self._tag(event, sha, data, copies)))
        self.expected = (self.expected + int.from_bytes(hmac.digest(self.secret, data, "sha256"))) % MODULUS

    def feed(self, raw):
        try:
            self._budget()
            if (not isinstance(raw, bytes) or len(raw) > O.MAX_BYTES
                    or self.input_bytes + len(raw) > self.config["max_source_bytes"]):
                raise Refused("KERNEL_REPLAY_SOURCE_ALLOWANCE_EXHAUSTED")
            self.input_bytes += len(raw)
            self.input_hash.update(raw)
            data, start = self.partial + raw, 0
            while True:
                end = data.find(b"\n", start)
                if end < 0:
                    break
                if end - start > H.MAX_LINE:
                    raise Refused("HOST_AUDIT_RECORD_BOUND_EXCEEDED")
                try:
                    line = data[start:end].removesuffix(b"\r").decode("utf-8")
                except UnicodeError as exc:
                    raise Refused("HOST_AUDIT_LOG_ENCODING") from exc
                self._insert(self.parser.selected_record(line))
                start = end + 1
            self.partial = data[start:]
            if len(self.partial) > H.MAX_LINE:
                raise Refused("HOST_AUDIT_RECORD_BOUND_EXCEEDED")
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.failed = True
            if isinstance(exc, sqlite3.Error):
                raise Refused("KERNEL_REPLAY_SCRATCH_UNAVAILABLE", type(exc).__name__) from exc
            raise

    def finish(self, publish, binding):
        """Publish bounded factual pages; never an intervention or campaign PASS."""
        try:
            return self._finish(publish, binding)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.failed = True
            if isinstance(exc, sqlite3.Error):
                raise Refused("KERNEL_REPLAY_SCRATCH_UNAVAILABLE", type(exc).__name__) from exc
            raise

    def _finish(self, publish, binding):
        self._budget()
        totals = dict(source_events=0, source_records=0, duplicate_records=0, events=0,
                      integrity_events=0, pending_events=0, orphan_compound_groups=0)
        pages, pending, page_size, output_bytes = [], [], 0, 0

        def flush():
            nonlocal page_size, output_bytes
            if not pending:
                return
            page = {"schema": "forge-c/kernel-event-facts-page/1", "binding": binding,
                    "index": len(pages), "previous_page_ref": pages[-1] if pages else None,
                    "groups": list(pending), "unexpected_interventions": None}
            raw = canonical(page)
            output_bytes += len(raw)
            if len(raw) > O.MAX_BYTES or output_bytes > self.config["max_output_bytes"]:
                raise Refused("KERNEL_REPLAY_OUTPUT_ALLOWANCE_EXHAUSTED")
            pages.append(publish(len(pages), page))
            pending.clear()
            page_size = 0

        def settle(parser):
            nonlocal page_size
            result = parser.finish()
            facts = result["facts"]
            group = {"facts": facts, "pending_events": result["pending_events"],
                     "orphan_compound_groups": result["orphan_compound_groups"]}
            size = len(canonical(group))
            if page_size + size > PAGE_BYTES:
                flush()
            pending.append(group)
            page_size += size
            totals["source_events"] += facts["source_events"]
            totals["source_records"] += facts["source_records"]
            totals["duplicate_records"] += facts["duplicate_records"]
            for key in ("events", "integrity_events"):
                totals[key] += len(facts[key])
            totals["pending_events"] += len(result["pending_events"])
            totals["orphan_compound_groups"] += result["orphan_compound_groups"]

        parser, prior, fingerprint, lines = None, None, 0, 0
        for event, sha, data, copies, tag in self.connection.execute(
                "SELECT event,sha,data,copies,tag FROM records ORDER BY event,sha"):
            self._budget()
            self._check(event, sha, data, copies, tag)
            record = json.loads(data)
            if event != canonical(record["identity"]).decode() or sha != record["sha256"]:
                raise Refused("KERNEL_REPLAY_SCRATCH_INTEGRITY_CHANGED")
            if prior != event:
                if parser is not None:
                    settle(parser)
                parser = H.EventReplay(host=self.parser.host, keys=self.parser.keys)
                prior = event
            parser._record(record)
            parser.duplicates += copies - 1
            fingerprint = (fingerprint + int.from_bytes(hmac.digest(self.secret, data, "sha256")) * copies) % MODULUS
            lines += copies
        if fingerprint != self.expected or lines != self.lines:
            raise Refused("KERNEL_REPLAY_SCRATCH_RECORDS_MISSING_OR_DUPLICATED")
        if parser is not None:
            settle(parser)
        flush()
        blockers = []
        for condition, reason in ((self.partial, "KERNEL_EVENT_PARTIAL_LINE"),
                                  (totals["pending_events"], "KERNEL_EVENT_PENDING_COMPOUND_RECORDS"),
                                  (totals["orphan_compound_groups"], "KERNEL_EVENT_ORPHAN_COMPOUND_GROUPS")):
            if condition:
                blockers.append(reason)
        self.closed = True
        return {"schema": "forge-c/kernel-event-replay/2", "facts": None, "fact_pages": pages,
                "totals": totals, "status": "INCOMPLETE_EVENT_PREFIX" if blockers else "SELECTED_EVENT_FACTS_REPLAYED",
                "input_bytes": self.input_bytes, "input_sha256": self.input_hash.hexdigest(),
                "pending_line": {"length": len(self.partial), "sha256": hashlib.sha256(self.partial).hexdigest()},
                "blockers": blockers, "unexpected_interventions": None,
                "scope": "SELECTED_PAGED_RECORD_FACTS_NOT_ALL_RECORD_COMPLETENESS_OR_HOST_COVERAGE"}


def _captures(manifest, frozen, plan, observer_plan_ref, host_plan_ref, refs, budget):
    from . import audit_segments as S

    segments, previous, metadata, boots = [], None, 0, set()
    for index, ref in enumerate(refs):
        budget()
        record, size = H._capture_record(manifest, frozen, plan, observer_plan_ref, host_plan_ref, ref,
                                        with_size=True, limit=O.MAX_TRACE_BYTES - metadata)
        metadata += size  # Original serialized bytes, including whitespace.
        seg = S.validate(record.get("kernel_segment"), plan["segments"])
        if (type(seg.get("sequence")) is not int or seg["sequence"] != index
                or seg.get("previous_segment_ref") != previous):
            raise Refused("HOST_AUDIT_SEGMENT_CAPTURE_CHAIN_DISCONTINUITY")
        if seg.get("rotation") is not None:
            rotation = seg["rotation"]
            if not isinstance(rotation, dict) or not isinstance(rotation.get("observation"), dict):
                raise Refused("HOST_AUDIT_SEGMENT_ROTATION_INVALID")
            status = record.get("kernel_status")
            if (not isinstance(status, dict) or type(status.get("pid")) is not int
                    or rotation["observation"].get("pid") != status["pid"]):
                raise Refused("HOST_AUDIT_SEGMENT_DAEMON_BINDING_UNKNOWN")
        boot = record.get("boot_id")
        boots.add(boot if isinstance(boot, str) else None)
        segments.append(seg)
        previous = ref
    return segments, boots


def verify(manifest, observer_plan_ref, host_plan_ref, refs, destination):
    """Opt-in existing host-audit command; every original capture starts at zero."""
    from . import audit_segments as S

    started, cpu_started = time.monotonic(), time.process_time()
    frozen, plan = H._plans(manifest, observer_plan_ref, host_plan_ref)
    config = configuration(plan.get("continuous_replay"))
    if plan.get("segments") is None or not isinstance(refs, list) or not 1 <= len(refs) <= 50000:
        raise Refused("HOST_AUDIT_SEGMENT_REFERENCES_INVALID")
    destination = O.artifact(frozen, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    binding = {"manifest_sha256": digest(manifest), "observer_plan_ref": observer_plan_ref,
               "host_plan_ref": host_plan_ref, "capture_refs_sha256": digest(refs)}

    def publish(index, page):
        path = destination.with_name(destination.name + ".events") / (str(index) + ".json")
        sha = immutable_json(O.artifact(frozen, path), page)
        return {"path": str(path), "sha256": sha}

    with Replay(config, host=plan["host"], keys=plan["keys"], scratch_parent=destination.parent) as replay:
        replay.started, replay.cpu_started = started, cpu_started
        segments, boots = _captures(manifest, frozen, plan, observer_plan_ref, host_plan_ref, refs, replay._budget)
        boot_known = (len(boots) == 1 and isinstance(next(iter(boots)), str)
                      and H.re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", next(iter(boots))))
        byte_chain = None
        for batch in S.verify_chain_batches(plan["segments"], segments,
                consume=replay.feed if boot_known else None, maximum=config["max_source_bytes"], max_segments=50000):
            replay._budget()
            byte_chain = batch
        if not byte_chain or byte_chain["status"] != "CAPTURED_BYTE_PREFIX_REPLAYED":
            raise Refused("KERNEL_REPLAY_BYTE_CHAIN_INCOMPLETE")
        if boot_known:
            events = replay.finish(publish, binding)
            if events["input_bytes"] != byte_chain["bytes"]:
                raise Refused("HOST_AUDIT_EVENT_REPLAY_INPUT_MISMATCH")
        else:
            events = {"schema": "forge-c/kernel-event-replay/2", "status": "BLOCKED", "facts": None,
                      "fact_pages": [], "unexpected_interventions": None,
                      "blockers": ["KERNEL_EVENT_REPLAY_BOOT_CONTINUITY_UNKNOWN"]}
    result = {"schema": "forge-c/host-audit-segment-replay/2", **binding,
              "first_capture_ref": refs[0], "last_capture_ref": refs[-1], "byte_chain": byte_chain,
              "kernel_event_replay": events, "status": "INCOMPLETE_SOURCE_COVERAGE",
              "unexpected_interventions": None,
              "blockers": sorted(set(events["blockers"] + [
                  "KERNEL_AUDIT_FULL_RECORD_AND_WINDOW_QUALIFICATION_REQUIRED",
                  "HOST_AUDIT_ALL_CHANNEL_CONTINUOUS_COVERAGE_REQUIRED"])),
              "scope": "CAPTURED_BYTE_PREFIX_NOT_HOST_INTERVENTION_VERIFICATION"}
    if len(canonical(result)) > O.MAX_BYTES:
        raise Refused("HOST_AUDIT_SEGMENT_REPLAY_OUTPUT_BOUND_EXCEEDED")
    immutable_json(destination, result)
    return result
