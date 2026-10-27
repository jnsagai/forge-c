"""Read-only, model-free evidence capture outside the Conductor (DA-AT-052).

The observer never injects a fault, repairs storage, admits work or grants authority.
Missing observations remain unknown. Its plan is an input of the frozen campaign;
artifacts belong to the existing qualification evidence tree, not another database.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

from ..common import sha256_file
from . import qualification, soak
from .durable import Refused, digest, immutable_json, strict_json

SCHEMA = "forge-c/independent-operational-observation/1"
FIELDS = {
    "afo_missions": ("mission_id", "lineage", "limits", "authorization_ref"),
    "afo_mission_executions": ("identity", "mission_id", "kind", "reserved_tokens", "charge", "reported_tokens"),
    "afo_request_ledger": ("request_id", "mission_id", "job_id", "charge", "state"),
    "afo_execution_liveness": ("job_id", "launch_nonce", "native_run_ids", "resource_lease", "execution_liveness"),
}
MAX_BYTES = 16 * 1024 * 1024


def read_json(path, limit=MAX_BYTES):
    # Never wait on a FIFO or follow a final-component symlink when state is damaged.
    import stat

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        mode = os.fstat(f.fileno())
        if not stat.S_ISREG(mode.st_mode) or mode.st_size > limit:
            raise Refused("OBSERVER_ARTIFACT_NOT_BOUNDED_REGULAR_FILE")
        return strict_json(f.read(limit + 1), limit)


def plan(manifest, ref):
    qualification.validate(manifest)
    if not manifest["stage"].startswith("operation-") or ref not in manifest["inputs"]:
        raise Refused("OBSERVER_PLAN_NOT_FROZEN")
    p = Path(ref["path"])
    d = read_json(p)
    if sha256_file(p) != ref["sha256"]:
        raise Refused("OBSERVER_PLAN_CHANGED")
    if (
        d.get("schema") != "forge-c/operational-observer-plan/1"
        or not re.fullmatch(r"[A-Za-z0-9_.@-]+\.service", d.get("unit", ""))
        or d.get("observer_source_sha256") != sha256_file(Path(__file__))
        or type(d.get("max_rows")) is not int
        or not 1 <= d["max_rows"] <= 10000
        or not all(
            isinstance(d.get(k), str) and Path(d[k]).is_absolute()
            for k in ("database", "intent", "data_root", "heartbeat", "evidence_root")
        )
    ):
        raise Refused("OBSERVER_PLAN_INVALID")
    if any(Path(d["data_root"]).resolve() not in Path(d[k]).resolve().parents for k in ("database", "heartbeat")):
        raise Refused("OBSERVER_DATABASE_OUTSIDE_DATA_ROOT")
    if not isinstance(d.get("mount_uuid"), str) or not re.fullmatch(r"[0-9a-fA-F-]{8,64}", d["mount_uuid"]):
        raise Refused("OBSERVER_MOUNT_IDENTITY_REQUIRED")
    if Path(d["data_root"]).resolve() in (Path(d["evidence_root"]).resolve(), *Path(d["evidence_root"]).resolve().parents):
        raise Refused("OBSERVER_EVIDENCE_MUST_BE_OUTSIDE_FACTORY_STATE")
    urls = d.get("health_urls")
    if not isinstance(urls, dict) or set(urls) != {"fabro", "gateway"}:
        raise Refused("OBSERVER_LOCAL_PROBES_REQUIRED")
    for raw in urls.values():
        parsed = urlsplit(raw)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "::1")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path != "/health"
            or not parsed.port
        ):
            raise Refused("OBSERVER_PROBE_MUST_BE_LOOPBACK")
    return d


def artifact(frozen, path):
    from .diagnosis_packet import scoped_path

    root = Path(frozen["evidence_root"]).resolve()
    try:
        relative = Path(path).absolute().relative_to(root)
    except ValueError:
        raise Refused("OBSERVER_EVIDENCE_OUTSIDE_APPROVED_ROOT") from None
    return scoped_path(root, str(relative))


def ledger(path, limit):
    """Snapshot authoritative tables in one read transaction; never call Store/migrate."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise Refused("OBSERVER_DATABASE_UNAVAILABLE")
    with closing(sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA query_only=ON")
        c.execute("BEGIN")
        result = {}
        for table, fields in FIELDS.items():
            rows = c.execute("SELECT record FROM " + table + " LIMIT ?", (limit + 1,)).fetchall()  # noqa: S608
            if len(rows) > limit:
                raise Refused("OBSERVER_LEDGER_ROW_BOUND_EXCEEDED")
            result[table] = [{k: row.get(k) for k in fields} for row in (strict_json(r[0], MAX_BYTES) for r in rows)]
        orders = c.execute(
            "SELECT order_id,state,authorization_id FROM afo_work_orders ORDER BY order_id LIMIT ?", (limit + 1,)
        ).fetchall()
        commands = c.execute(
            "SELECT command_id,kind,idempotency_key,ack_ref FROM afo_commands_outbox ORDER BY command_id LIMIT ?", (limit + 1,)
        ).fetchall()
        actions = c.execute("SELECT seq,action FROM afo_operator_actions ORDER BY seq LIMIT ?", (limit + 1,)).fetchall()
        if max(len(orders), len(commands), len(actions)) > limit:
            raise Refused("OBSERVER_LEDGER_ROW_BOUND_EXCEEDED")
        result.update(orders=[dict(r) for r in orders], commands=[dict(r) for r in commands], actions=[dict(r) for r in actions])
        return result


def unit_status(unit):
    result = subprocess.run(
        ["systemctl", "--user", "show", unit, "--property=ActiveState,SubState,Result,MainPID,ControlGroup,NRestarts"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode:
        raise Refused("OBSERVER_UNIT_UNAVAILABLE")
    props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return {k: props.get(k) for k in ("ActiveState", "SubState", "Result", "MainPID", "ControlGroup", "NRestarts")}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _healthy(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(url, timeout=2) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def health(frozen, bound):
    checks = {key: _healthy(url) for key, url in frozen["health_urls"].items()}
    try:
        heartbeat = read_json(frozen["heartbeat"], 65536)
        checks["conductor"] = heartbeat.get("ok") is True and 0 <= time.time() - heartbeat["epoch"] <= bound
    except (OSError, ValueError, KeyError, TypeError):
        checks["conductor"] = False
    result = subprocess.run(
        ["findmnt", "--noheadings", "--output", "UUID", "--target", frozen["data_root"]],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    checks["data_volume"] = result.returncode == 0 and result.stdout.strip() == frozen["mount_uuid"]
    return checks


def _intent(path):
    record = read_json(path, 65536)
    if record.get("mode") not in ("RUNNING", "PAUSED", "DRAINING", "STOPPED") or type(record.get("epoch")) is not int:
        raise Refused("OBSERVER_OPERATIONS_INTENT_UNKNOWN")
    return {k: record[k] for k in ("mode", "epoch")}


def capture(manifest, plan_ref, destination):
    """One bounded external sample; safe while the controller or engineering grant is down."""
    frozen = plan(manifest, plan_ref)
    started = time.monotonic()
    out = {
        "schema": SCHEMA,
        "manifest_sha256": digest(manifest),
        "plan_ref": plan_ref,
        "observer_source_sha256": sha256_file(Path(__file__)),
        "host": socket.gethostname(),
        "observer_pid": os.getpid(),
        "wall": time.time(),
        "mono": started,
        "boot_id": soak._boot_id(),
        "errors": {},
    }
    probes = {
        "ledger": lambda: ledger(frozen["database"], frozen["max_rows"]),
        "intent": lambda: _intent(frozen["intent"]),
        "unit": lambda: unit_status(frozen["unit"]),
        "health": lambda: health(frozen, manifest["bounds"]["control_cycle_seconds"]),
        "free_bytes": lambda: os.statvfs(frozen["data_root"]).f_bavail * os.statvfs(frozen["data_root"]).f_frsize,
        "observer_cgroups": lambda: [s.split(":", 2)[-1] for s in Path("/proc/self/cgroup").read_text().splitlines()],
    }
    for name, probe in probes.items():
        try:
            out[name] = probe()
        except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
            # No exception messages (which can contain private data), no artificial healthy defaults.
            out[name] = None
            out["errors"][name] = getattr(exc, "code", type(exc).__name__)
    unit = out.get("unit") or {}
    cgroup = unit.get("ControlGroup")
    out["independent_process"] = bool(
        cgroup
        and unit.get("MainPID") != str(os.getpid())
        and out.get("observer_cgroups")
        and all(g != cgroup and not g.startswith(cgroup + "/") for g in out["observer_cgroups"])
    )
    out["capture_seconds"] = time.monotonic() - started
    out["complete"] = (
        not out["errors"] and out["independent_process"] and out["capture_seconds"] <= manifest["bounds"]["control_cycle_seconds"]
    )
    immutable_json(artifact(frozen, destination), out)
    return out


def _rows(snapshot, table, key):
    rows = snapshot["ledger"][table]
    out = {r[key]: r for r in rows}
    if len(rows) != len(out):
        raise Refused("OBSERVER_DUPLICATE_LEDGER_IDENTITY")
    return out


def invariants(samples):
    """Unknown or truncated accounting cannot be converted into zero loss/duplicates."""
    if not samples or any(not s.get("complete") or not s.get("ledger") for s in samples):
        return {"ledger_reset": None, "duplicate_effects": None, "false_ready": None, "unexpected_interventions": None}
    reset, duplicates = False, 0
    for a, b in zip(samples, samples[1:], strict=False):
        for table, key in (
            ("afo_missions", "mission_id"),
            ("afo_mission_executions", "identity"),
            ("afo_request_ledger", "request_id"),
        ):
            before, after = _rows(a, table, key), _rows(b, table, key)
            reset |= not set(before) <= set(after)
            for ident in set(before) & set(after):
                old, new = before[ident], after[ident]
                if table == "afo_missions":
                    reset |= old != new  # even higher limits require a separately audited amendment, not replacement
                else:
                    reset |= old["mission_id"] != new["mission_id"] or new["charge"] < old["charge"]
                    if table == "afo_mission_executions":
                        reset |= old["reserved_tokens"] != new["reserved_tokens"]
                        reset |= old["reported_tokens"] is not None and (
                            new["reported_tokens"] is None or new["reported_tokens"] < old["reported_tokens"]
                        )
                    else:
                        reset |= old["job_id"] != new["job_id"]
        old_commands = {r["command_id"]: r for r in a["ledger"]["commands"]}
        new_commands = {r["command_id"]: r for r in b["ledger"]["commands"]}
        reset |= not set(old_commands) <= set(new_commands)
        for ident in set(old_commands) & set(new_commands):
            old, new = old_commands[ident], new_commands[ident]
            reset |= old["idempotency_key"] != new["idempotency_key"] or bool(old["ack_ref"] and old["ack_ref"] != new["ack_ref"])
    for sample in samples:
        for ex in sample["ledger"]["afo_execution_liveness"]:
            duplicates = max(duplicates, max(0, len(set(ex["native_run_ids"])) - 1))
        keys = [(r["kind"], r["idempotency_key"]) for r in sample["ledger"]["commands"]]
        duplicates = max(duplicates, len(keys) - len(set(keys)))
    ready = any(r["state"] == "READY_FOR_OFFLINE_REVIEW" for s in samples for r in s["ledger"]["orders"])
    return {
        "ledger_reset": bool(reset),
        "duplicate_effects": duplicates,
        "false_ready": None if ready else False,  # READY requires the separate independent package oracle
        "unexpected_interventions": None,  # authenticated actions alone cannot exclude host-level manual intervention
    }


def load_samples(manifest, plan_ref, refs):
    frozen = plan(manifest, plan_ref)
    rows = []
    if not 2 <= len(refs) <= 50000:
        raise Refused("OBSERVER_SAMPLE_COUNT_INVALID")
    for ref in refs:
        p = artifact(frozen, ref["path"])
        row = read_json(p)
        if (
            sha256_file(p) != ref["sha256"]
            or row.get("schema") != SCHEMA
            or row.get("manifest_sha256") != digest(manifest)
            or row.get("plan_ref") != plan_ref
        ):
            raise Refused("OBSERVER_SAMPLE_UNBOUND")
        if any(type(row.get(k)) not in (float, int) or not math.isfinite(row[k]) for k in ("wall", "mono")):
            raise Refused("OBSERVER_SAMPLE_CLOCK_INVALID")
        rows.append(row)
    if len({r["host"] for r in rows}) != 1 or any(r.get("observer_source_sha256") != sha256_file(Path(__file__)) for r in rows):
        raise Refused("OBSERVER_SAMPLE_SOURCE_CHANGED")
    if any(
        b["wall"] <= a["wall"] or (a["boot_id"] == b["boot_id"] and b["mono"] <= a["mono"])
        for a, b in zip(rows, rows[1:], strict=False)
    ):
        raise Refused("OBSERVER_SAMPLE_ORDER_INVALID")
    return rows


def evaluate(manifest, plan_ref, injection_ref, sample_refs, destination):
    """Correlate objective signal-fault restoration; no hand-entered success flags."""
    frozen = plan(manifest, plan_ref)
    receipt = read_json(artifact(frozen, injection_ref["path"]))
    if sha256_file(Path(injection_ref["path"])) != injection_ref["sha256"] or receipt.get("manifest_sha256") != digest(manifest):
        raise Refused("OBSERVER_FAULT_RECEIPT_UNBOUND")
    fault = receipt.get("fault")
    if fault not in manifest["faults"]:
        raise Refused("OBSERVER_FAULT_NOT_FROZEN")
    rows = load_samples(manifest, plan_ref, sample_refs)
    before = [s for s in rows if s["wall"] <= receipt["at"]]
    after = [s for s in rows if s["wall"] > receipt["at"]]
    from .operational_campaign import SIGNALS

    exposure = bool(
        fault in SIGNALS
        and receipt.get("schema") == "forge-c/operational-fault/1"
        and receipt.get("unit") == frozen["unit"]
        and receipt.get("returncode") == 0
        and receipt.get("command")
        == ["systemctl", "--user", "kill", "--kill-who=main", "--signal=" + SIGNALS[fault], frozen["unit"]]
        and before
        and before[-1].get("complete")
        and before[-1]["unit"]["ActiveState"] == "active"
        and before[-1]["intent"]["mode"] == "RUNNING"
        and receipt.get("host") == before[-1]["host"]
        and 0 <= receipt["at"] - before[-1]["wall"] <= manifest["bounds"]["probe_gap_seconds"]
    )
    affected = (
        [
            s
            for s in after
            if s.get("unit") and (s["unit"]["ActiveState"] != "active" or s["unit"]["MainPID"] != before[-1]["unit"]["MainPID"])
        ]
        if before
        else []
    )
    restored = next(
        (
            s
            for s in affected
            if s.get("complete")
            and set(s.get("health") or {}) == {"conductor", "fabro", "gateway", "data_volume"}
            and all(value is True for value in s["health"].values())
            and s.get("intent") == before[-1]["intent"]
            and s["unit"]["ActiveState"] == "active"
            and s["unit"]["MainPID"] != before[-1]["unit"]["MainPID"]
        ),
        None,
    )
    gaps = any(
        b["wall"] - a["wall"] > manifest["bounds"]["probe_gap_seconds"]
        or (a["boot_id"] == b["boot_id"] and abs((b["wall"] - a["wall"]) - (b["mono"] - a["mono"])) > soak.CLOCK_SKEW_S)
        for a, b in zip(rows, rows[1:], strict=False)
    )
    facts = invariants(rows)
    record = {
        "schema": "forge-c/independent-operational-fault/1",
        "producer": "INDEPENDENT_OPERATIONAL_OBSERVER",
        "manifest_sha256": digest(manifest),
        "plan_ref": plan_ref,
        "fault": fault,
        "injection_ref": injection_ref,
        "sample_refs": sample_refs,
        "fault_exposed": exposure,
        "independently_restored": bool(exposure and restored and not gaps),
        "restoration_seconds": restored["wall"] - receipt["at"] if restored and exposure else None,
        "observation_gaps": gaps,
        **facts,
        "status": "OBSERVED_REQUIRES_HOST_AUDIT" if exposure and restored and not gaps else "INCOMPLETE",
        "limitations": [
            "HOST_INTERVENTION_AUDIT_REQUIRED",
            *(["INDEPENDENT_READY_ORACLE_REQUIRED"] if facts["false_ready"] is None else []),
            *(["EXTERNAL_FAULT_EXPOSURE_FIXTURE_REQUIRED"] if fault not in SIGNALS else []),
        ],
    }
    if destination is not None:
        immutable_json(artifact(frozen, destination), record)
    return record


def verify(manifest, record):
    if record.get("schema") != "forge-c/independent-operational-fault/1":
        raise Refused("INDEPENDENT_OPERATIONAL_OBSERVER_REQUIRED")
    actual = evaluate(manifest, record["plan_ref"], record["injection_ref"], record["sample_refs"], None)
    if actual != record:
        raise Refused("OPERATIONAL_OBSERVER_VERDICT_CHANGED")
    return actual


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("capture", "evaluate"))
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--plan-ref", type=Path, required=True, help="JSON path+sha256 reference already frozen in manifest inputs")
    ap.add_argument("--evidence", type=Path, help="JSON with injection_ref and sample_refs")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    m, ref = read_json(args.manifest), read_json(args.plan_ref)
    if args.command == "capture":
        result = capture(m, ref, args.out)
    else:
        if not args.evidence:
            ap.error("--evidence required for evaluate")
        result = evaluate(m, ref, **read_json(args.evidence), destination=args.out)
    print(json.dumps({k: result[k] for k in ("schema", "manifest_sha256")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
