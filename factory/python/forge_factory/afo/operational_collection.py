"""Crash-replayable observation on the existing soak cadence, without service authority.

Receipts are artifacts in the frozen observer evidence root, not a second ledger.
Collection ending never changes factory intent, grants, budgets or native leases.
Host byte captures remain incomplete coverage until their independent verifier passes.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import time
from pathlib import Path

from ..common import sha256_file, utc_now
from . import fault_observer as O
from . import host_audit as H
from . import soak
from .durable import Refused, digest, immutable_json

SCHEMA = "forge-c/operational-collection-receipt/1"


def validate_configuration(value, expected_sources):
    """Qwen job 081 candidate, independently reviewed; strict integer checks corrected."""
    if not isinstance(value, dict) or not isinstance(expected_sources, dict):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
    expected_keys = {"source_sha256", "soak_source_sha256", "campaign_source_sha256"}
    required = expected_keys | {"interval_seconds", "max_samples", "minimum_free_bytes"}
    if set(value) != required or set(expected_sources) != expected_keys:
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
    for key in expected_keys:
        val = expected_sources[key]
        if not isinstance(val, str) or not re.fullmatch(r"[0-9a-f]{64}", val):
            raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
        if not isinstance(value[key], str) or value[key] != val:
            raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
    for key, lower, upper in (
        ("interval_seconds", 5, 600),
        ("max_samples", 1, 50000),
        ("minimum_free_bytes", 64 * 1024 * 1024, 2**63 - 1),
    ):
        if type(value[key]) is not int or not lower <= value[key] <= upper:
            raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
    return dict(value)


def source_hashes():
    from . import operational_campaign

    return {
        "source_sha256": sha256_file(Path(__file__)),
        "soak_source_sha256": sha256_file(Path(soak.__file__)),
        "campaign_source_sha256": sha256_file(Path(operational_campaign.__file__)),
    }


def configuration(value):
    return validate_configuration(value, source_hashes())


def reference(path):
    raw = O.read_bytes(path)
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


class Collector:
    def __init__(self, manifest, soak_id, plan_ref, host_plan_ref=None):
        self.manifest, self.soak_id = manifest, soak_id
        self.plan_ref, self.host_plan_ref = plan_ref, host_plan_ref
        self.frozen = O.plan(manifest, plan_ref)
        self.config = configuration(self.frozen.get("collection"))
        self.log = soak.path(soak_id)
        if host_plan_ref is not None:
            _, host = H._plans(manifest, plan_ref, host_plan_ref)
            if host.get("segments") is None:
                raise Refused("HOST_AUDIT_SEGMENT_PLAN_REQUIRED_FOR_RESUME")

    def directory(self, sequence):
        return O.artifact(self.frozen, Path(self.frozen["evidence_root"]) / "collections" / self.soak_id / str(sequence))

    def history(self):
        raw = O.read_bytes(self.log, O.MAX_TRACE_BYTES)
        if not raw.endswith(b"\n"):
            raise Refused("OPERATIONAL_COLLECTION_PARTIAL_LOG_TAIL")
        lines = raw.splitlines()
        if not 1 <= len(lines) <= 50001 or any(not x or len(x) > 65536 for x in lines):
            raise Refused("OPERATIONAL_COLLECTION_HISTORY_BOUND")
        rows = [O.strict_json(x, 65536) for x in lines]
        head = rows[0]
        if (
            head.get("kind") != "start"
            or head.get("soak_id") != self.soak_id
            or head.get("interval_s") != self.config["interval_seconds"]
            or head.get("target_hours") != int(self.manifest["stage"].split("-")[1])
            or digest(O.read_json(self.log.with_suffix(".manifest.json"))) != digest(self.manifest)
        ):
            raise Refused("OPERATIONAL_COLLECTION_HEAD_UNBOUND")
        for sequence, row in enumerate(rows[1:]):
            if (
                row.get("kind") != "sample"
                or row.get("collection_sequence") != sequence
                or row.get("collection_ref", {}).get("path") != str(self.directory(sequence) / "receipt.json")
                or row.get("manifest_sha256") != digest(self.manifest)
                or row.get("plan_ref") != self.plan_ref
                or row.get("host_plan_ref") != self.host_plan_ref
            ):
                raise Refused("OPERATIONAL_COLLECTION_HISTORY_UNBOUND")
        for a, b in zip(rows, rows[1:], strict=False):
            if (
                any(type(r.get(k)) not in (int, float) or not math.isfinite(r[k]) for r in (a, b) for k in ("wall", "mono"))
                or not a.get("boot_id")
                or not b.get("boot_id")
                or b["wall"] <= a["wall"]
                or (a["boot_id"] == b["boot_id"] and b["mono"] <= a["mono"])
            ):
                raise Refused("OPERATIONAL_COLLECTION_CLOCK_ORDER_INVALID")
        return rows

    def _attempt(self, sequence, kind, previous_host_ref):
        directory = self.directory(sequence)
        path = directory / (kind + "-attempt.json")
        target = directory / (kind + ".json")
        if not path.exists():
            out = {"kind": kind, "artifact_ref": None, "error": None}
            try:
                if not target.exists():
                    if kind == "host":
                        H.capture(self.manifest, self.plan_ref, self.host_plan_ref, target, previous_ref=previous_host_ref)
                    else:
                        O.capture(self.manifest, self.plan_ref, target)
                out["artifact_ref"] = reference(target)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                out["error"] = getattr(exc, "code", type(exc).__name__)
            out.update(wall=time.time(), mono=time.monotonic(), boot_id=soak._boot_id(), utc=utc_now())
            immutable_json(path, out)
        return O.read_json(path, 65536), reference(path)

    def _sample(self, receipt):
        return {
            "kind": "sample",
            "collection_sequence": receipt["sequence"],
            "manifest_sha256": receipt["manifest_sha256"],
            "plan_ref": self.plan_ref,
            "host_plan_ref": self.host_plan_ref,
            **receipt["sample"],
        }

    def replay(self, sequence, previous_ref):
        path = self.directory(sequence) / "receipt.json"
        record = O.read_json(path)
        if (
            record.get("schema") != SCHEMA
            or record.get("sequence") != sequence
            or record.get("manifest_sha256") != digest(self.manifest)
            or record.get("plan_ref") != self.plan_ref
            or record.get("host_plan_ref") != self.host_plan_ref
            or record.get("configuration") != self.config
            or record.get("previous_receipt_ref") != previous_ref
            or record.get("unexpected_interventions") is not None
        ):
            raise Refused("OPERATIONAL_COLLECTION_RECEIPT_UNBOUND")
        previous_host = None
        if sequence:
            if not isinstance(previous_ref, dict) or previous_ref.get("path") != str(
                self.directory(sequence - 1) / "receipt.json"
            ):
                raise Refused("OPERATIONAL_COLLECTION_RECEIPT_UNBOUND")
            previous = O.bound_json(previous_ref, path=O.artifact(self.frozen, previous_ref["path"]))
            previous_host = previous.get("last_host_ref")
        elif previous_ref is not None:
            raise Refused("OPERATIONAL_COLLECTION_RECEIPT_UNBOUND")
        expected_host = previous_host
        for kind in ("observation", "host"):
            attempt_ref = record.get(kind + "_attempt_ref")
            if kind == "host" and self.host_plan_ref is None:
                if attempt_ref is not None:
                    raise Refused("OPERATIONAL_COLLECTION_RECEIPT_UNBOUND")
                continue
            if not isinstance(attempt_ref, dict) or attempt_ref.get("path") != str(
                self.directory(sequence) / (kind + "-attempt.json")
            ):
                raise Refused("OPERATIONAL_COLLECTION_ATTEMPT_UNBOUND")
            attempt = O.bound_json(attempt_ref, path=O.artifact(self.frozen, attempt_ref["path"]))
            ref = attempt.get("artifact_ref")
            if ref is not None:
                if ref.get("path") != str(self.directory(sequence) / (kind + ".json")):
                    raise Refused("OPERATIONAL_COLLECTION_ATTEMPT_UNBOUND")
                if kind == "observation":
                    row, _ = O.load_sample(self.manifest, self.plan_ref, ref, frozen=self.frozen)
                    if record["sample"] != self.observed_sample(row):
                        raise Refused("OPERATIONAL_COLLECTION_SAMPLE_CHANGED")
                else:
                    _, host = H._plans(self.manifest, self.plan_ref, self.host_plan_ref)
                    capture = H._capture_record(self.manifest, self.frozen, host, self.plan_ref, self.host_plan_ref, ref)
                    if capture.get("previous_capture_ref") != previous_host:
                        raise Refused("OPERATIONAL_COLLECTION_HOST_CHAIN_CHANGED")
                    expected_host = ref
            elif kind == "observation":
                expected = {k: attempt[k] for k in ("wall", "mono", "boot_id", "utc")}
                expected.update(probes={}, healthy=False, observation_complete=False)
                if record["sample"] != expected or not attempt.get("error"):
                    raise Refused("OPERATIONAL_COLLECTION_FAILURE_CHANGED")
        if record.get("last_host_ref") != expected_host:
            raise Refused("OPERATIONAL_COLLECTION_HOST_CHAIN_CHANGED")
        return record

    @staticmethod
    def observed_sample(row):
        probes = row.get("health")
        if (
            not isinstance(probes, dict)
            or set(probes) != {"conductor", "fabro", "gateway", "data_volume"}
            or any(type(v) is not bool for v in probes.values())
        ):
            probes = {}
        # A healthy HTTP endpoint alone cannot turn an incomplete independent capture into known telemetry.
        if row.get("complete") is not True:
            probes = {}
        return {
            **{k: row[k] for k in ("wall", "mono", "boot_id")},
            "utc": row.get("utc"),
            "probes": probes,
            "healthy": bool(probes) and all(probes.values()),
            "observation_complete": row.get("complete") is True,
        }

    def __call__(self, soak_id, *, probes=None):
        if soak_id != self.soak_id or probes is not None:
            raise Refused("OPERATIONAL_COLLECTION_CANNOT_OVERRIDE_PROBES")
        with soak.locked(self.log):
            rows = self.history()
            sequence = len(rows) - 1
            if sequence >= self.config["max_samples"]:
                raise Refused("OPERATIONAL_COLLECTION_SAMPLE_ALLOWANCE_EXHAUSTED")
            previous_ref = rows[-1].get("collection_ref")
            prior = self.replay(sequence - 1, rows[-2].get("collection_ref")) if sequence else None
            if sequence and previous_ref != reference(self.directory(sequence - 1) / "receipt.json"):
                raise Refused("OPERATIONAL_COLLECTION_LOG_CHANGED")
            if prior is not None and self._sample(prior) != {k: v for k, v in rows[-1].items() if k != "collection_ref"}:
                raise Refused("OPERATIONAL_COLLECTION_LOG_CHANGED")
            path = self.directory(sequence) / "receipt.json"
            if not path.exists():
                # Leave the signed reserve after two maximum captures + bounded metadata. Never delete evidence.
                usage = os.statvfs(self.frozen["evidence_root"])
                if usage.f_bavail * usage.f_frsize < self.config["minimum_free_bytes"] + 2 * O.MAX_BYTES + 262144:
                    raise Refused("OPERATIONAL_COLLECTION_EVIDENCE_DISK_RESERVE")
                host_attempt, host_attempt_ref = (None, None)
                previous_host = prior.get("last_host_ref") if prior else None
                if self.host_plan_ref is not None:
                    host_attempt, host_attempt_ref = self._attempt(sequence, "host", previous_host)
                observation, observation_ref = self._attempt(sequence, "observation", None)
                if observation["artifact_ref"] is None:
                    sample = {k: observation[k] for k in ("wall", "mono", "boot_id", "utc")}
                    sample.update(probes={}, healthy=False, observation_complete=False)
                else:
                    row, _ = O.load_sample(self.manifest, self.plan_ref, observation["artifact_ref"], frozen=self.frozen)
                    sample = self.observed_sample(row)
                record = {
                    "schema": SCHEMA,
                    "sequence": sequence,
                    "manifest_sha256": digest(self.manifest),
                    "plan_ref": self.plan_ref,
                    "host_plan_ref": self.host_plan_ref,
                    "configuration": self.config,
                    "previous_receipt_ref": previous_ref,
                    "observation_attempt_ref": observation_ref,
                    "host_attempt_ref": host_attempt_ref,
                    "last_host_ref": (host_attempt or {}).get("artifact_ref") or previous_host,
                    "sample": sample,
                    "unexpected_interventions": None,
                    "host_coverage": "INCOMPLETE_SOURCE_COVERAGE" if self.host_plan_ref else "NOT_COLLECTED",
                }
                immutable_json(path, record)
            record = self.replay(sequence, previous_ref)
            row = {**self._sample(record), "collection_ref": reference(path)}
            last = rows[-1]
            if row["wall"] <= last["wall"] or (row["boot_id"] == last["boot_id"] and row["mono"] <= last["mono"]):
                raise Refused("OPERATIONAL_COLLECTION_CLOCK_ORDER_INVALID")
            soak._append_locked(self.log, row)
            return row

    def verify(self):
        """Replay original evidence, including older artifacts; never trust log success flags."""
        with soak.locked(self.log):
            rows = self.history()
            previous_ref = None
            budget = O.MAX_TRACE_BYTES
            observations = []
            for sequence, row in enumerate(rows[1:]):
                # Bound total verification work before parsing each source again.
                directory = self.directory(sequence)
                for name in ("receipt.json", "host-attempt.json", "host.json", "observation-attempt.json", "observation.json"):
                    p = directory / name
                    if p.exists():
                        budget -= len(O.read_bytes(p, min(O.MAX_BYTES, max(0, budget))))
                record = self.replay(sequence, previous_ref)
                expected = {**self._sample(record), "collection_ref": reference(directory / "receipt.json")}
                if row != expected:
                    raise Refused("OPERATIONAL_COLLECTION_LOG_CHANGED")
                observations.append(O.bound_json(record["observation_attempt_ref"])["artifact_ref"])
                previous_ref = row["collection_ref"]
            return {
                "status": "SOURCE_REPLAY_PASS",
                "samples": len(rows) - 1,
                "unexpected_interventions": None,
                "host_coverage": "SEPARATE_INDEPENDENT_VERIFICATION_REQUIRED",
                "observation_refs": observations,
            }
