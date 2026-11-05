"""Append-only OS-owner acknowledgement of an independently cleaned failed startup.

This never cleans a process, renews authority, releases resources or changes an
old outcome. The independent cleanup file is data; current authority and fresh
normal physical quiescence are required by the coordinator on both paths.
"""

import math
import os
import re
import time
from pathlib import Path

from .durable import canonical, digest, strict_json
from .owner_profile_bootstrap import INTENT_KIND, RESULT_KIND, require

KIND = "OWNER_PROFILE_BOOTSTRAP_RECONCILED"
SCHEMA = "forge-c/owner-bootstrap-cleanup-evidence/1"


def owner_context():
    from ..lrtx.provider_process import boot_id, owner_view

    return dict(boot_id=boot_id(), **owner_view(os.getpid()))


def ledger_checkpoint(path):
    """Only append-only issuer/diagnostic decisions may differ across cleanup."""
    import sqlite3

    from .owner_bootstrap_history import table_hashes

    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3) as c:
        names = [
            r[0]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "AND name!='afo_independent_decisions' ORDER BY name"
            )
        ]
    require(bool(names), "RECONCILIATION_LEDGER_UNKNOWN")
    return table_hashes(path, names)


def _row(c, key, kind):
    row = c.execute("SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=? AND kind=?", (key, kind)).fetchone()
    require(row is not None, "RECONCILIATION_ROW_MISSING")
    value = strict_json(row[0].encode(), 4 * 1024 * 1024)
    require(digest(value) == row[1], "RECONCILIATION_ROW_HASH_CHANGED")
    return value


def _ended(expected):
    from ..lrtx.provider_process import identity

    require(
        type(expected.get("pid")) is int and expected["pid"] > 1 and re.fullmatch(r"\d+", str(expected.get("start_ticks", ""))),
        "RECONCILIATION_LIFETIME_INVALID",
    )
    current = identity(expected["pid"])  # unreadable is an error, never absence
    require(
        current is None
        or current["boot_id"] != expected["boot_id"]
        or current["start_ticks"] != expected["start_ticks"]
        or current["state"] == "Z",
        "RECONCILIATION_OLD_LIFETIME_LIVE",
    )


def validate(c, store, record, request, native):
    """Recheck exact independent cleanup and current kernels; returns bound data."""
    from . import owner_supervised_development as D
    from .owner_bootstrap_history import native_checkpoint

    require(set(request) == {"intent_id", "result_sha256", "evidence_ref"}, "RECONCILIATION_REQUEST_INVALID")
    old_intent = _row(c, request["intent_id"], INTENT_KIND)
    old_result = _row(c, request["intent_id"] + "-result", RESULT_KIND)
    old_sha = old_intent["record_sha256"]
    require(
        request["intent_id"] == "owner-profile-bootstrap-" + old_sha and re.fullmatch("[0-9a-f]{64}", old_sha),
        "RECONCILIATION_NONCE_CHANGED",
    )
    require(
        old_result["status"] == "UNKNOWN_REQUIRES_RECONCILIATION"
        and old_result["no_retry"] is True
        and digest(old_result) == request["result_sha256"]
        and old_result["record_sha256"] == old_sha,
        "RECONCILIATION_NOT_EXACT_UNKNOWN",
    )
    parent = Path(record["intent_path"]).parent
    old_path = parent / "owner-supervised-development" / (old_sha + ".json")
    D._private(old_path)
    old = strict_json(old_path.read_bytes(), 1024 * 1024)
    require(digest(old) == old_sha and old["control_ref"] == old_intent["control_ref"], "RECONCILIATION_OLD_RECORD_CHANGED")
    require(
        old.get("schema") == D.SCHEMA
        and old.get("mode") == D.MODE
        and old.get("qualification_only") is True
        and old.get("acceptance") == "UNACCEPTED"
        and old.get("directive_sha256") == digest(dict(external_directive=D.DIRECTIVE))
        and _row(c, "owner-development-" + old_sha, D.MODE) == old,
        "RECONCILIATION_ORIGINAL_ISSUANCE_UNPROVEN",
    )
    _ended(dict(pid=old["guardian_pid"], **old["guardian"]))
    require(old_sha != digest(record) and old["guardian_pid"] != record["guardian_pid"], "RECONCILIATION_NEW_ISSUER_REQUIRED")
    require(
        all(
            old[k] == record[k]
            for k in (
                "intent_path",
                "intent_epoch",
                "store_path",
                "store_identity",
                "profile",
                "profile_sha256",
                "mission",
                "mission_anchor",
                "driver_class",
                "order_ids",
                "runtime_policy_sha256",
                "line_policy_sha256",
            )
        ),
        "RECONCILIATION_LINEAGE_OR_ACCOUNTING_CHANGED",
    )
    ref = request["evidence_ref"]
    require(
        isinstance(ref, dict) and set(ref) == {"path", "sha256"} and re.fullmatch("[0-9a-f]{64}", str(ref["sha256"])),
        "RECONCILIATION_EVIDENCE_REF_INVALID",
    )
    path = Path(ref["path"])
    require(
        path.is_absolute() and path.parent == parent / "owner-bootstrap-reconciliation", "RECONCILIATION_PRIVATE_PATH_REQUIRED"
    )
    D._private(path.parent, directory=True)
    D._private(path)
    raw = path.read_bytes()
    import hashlib

    require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "RECONCILIATION_EVIDENCE_CHANGED")
    evidence = strict_json(raw, 4 * 1024 * 1024)
    bindings = dict(
        old_intent_id=request["intent_id"],
        bootstrap_nonce=request["intent_id"],
        old_intent_sha256=digest(old_intent),
        old_result_sha256=digest(old_result),
        old_record_sha256=old_sha,
        old_source_revisions=old["source_revisions"],
        old_control_ref=old["control_ref"],
        profile=old["profile"],
        profile_sha256=old["profile_sha256"],
        mission=old["mission"],
        store_path=old["store_path"],
        store_identity=old["store_identity"],
        intent_epoch=old["intent_epoch"],
    )
    require(
        evidence.get("schema") == SCHEMA
        and evidence.get("status") == "WHOLE_STACK_QUIET_HISTORY_CONSERVED"
        and all(evidence.get(k) == v for k, v in bindings.items()),
        "RECONCILIATION_EVIDENCE_BINDING_CHANGED",
    )
    require(evidence.get("next_source_revisions") == record["source_revisions"], "RECONCILIATION_NEXT_SOURCE_CHANGED")
    old_unit = evidence.get("old_unit")
    require(
        isinstance(old_unit, dict)
        and set(old_unit) == {"name", "MainPID", "InvocationID"}
        and re.fullmatch(r"forge-c-owner-development-[0-9a-f]{8}-[0-9]{8}\.service", str(old_unit["name"]))
        and any(old_unit["name"].startswith("forge-c-owner-development-" + rev[:8] + "-") for rev in old["source_revisions"])
        and old_unit["MainPID"] == "0"
        and re.fullmatch("[0-9a-f]{32}", str(old_unit["InvocationID"])),
        "RECONCILIATION_OLD_UNIT_INVALID",
    )
    import subprocess

    status = subprocess.check_output(
        [
            "systemctl",
            "--user",
            "show",
            old_unit["name"],
            "--property=MainPID",
            "--property=InvocationID",
            "--property=LoadState",
            "--property=ActiveState",
        ],
        text=True,
        timeout=5,
    )
    actual_unit = dict(line.split("=", 1) for line in status.splitlines() if "=" in line)
    require(
        actual_unit.get("MainPID") == "0"
        and actual_unit.get("ActiveState") in ("inactive", "failed")
        and (
            (actual_unit.get("LoadState") == "loaded" and actual_unit.get("InvocationID") == old_unit["InvocationID"])
            or (
                actual_unit.get("LoadState") == "not-found"
                and actual_unit.get("ActiveState") == "inactive"
                and actual_unit.get("InvocationID") == ""
            )
        ),
        "RECONCILIATION_OLD_UNIT_CHANGED",
    )
    namespace = evidence.get("old_namespace")
    require(
        isinstance(namespace, dict)
        and set(namespace) == {"user", "net", "pid", "uid_map"}
        and all(re.fullmatch(k + r":\[\d+\]", str(namespace[k])) for k in ("user", "net", "pid"))
        and namespace["uid_map"] == [[0, old["guardian"]["uid"], 1]],
        "RECONCILIATION_NAMESPACE_INVALID",
    )
    services = Path(store.path).parents[2] / "run/services.json"
    require(
        evidence.get("services_before_sha256")
        == evidence.get("services_after_sha256")
        == hashlib.sha256(services.read_bytes()).hexdigest(),
        "RECONCILIATION_SERVICES_CHANGED",
    )
    require(
        evidence.get("holder_file_removed_after_quiet") is True
        and evidence.get("old_lifetimes_fds_quiet") is True
        and evidence.get("no_charge_reset_or_relabel") is True,
        "RECONCILIATION_CLEANUP_BOUNDARY_UNKNOWN",
    )
    require(
        evidence.get("owner_context") == owner_context()
        and evidence.get("unknown_occupants") == []
        and evidence.get("whole_stack_quiet") is True,
        "RECONCILIATION_OWNER_OR_QUIET_UNKNOWN",
    )
    for field, now in (("observed_monotonic", time.monotonic()), ("observed_boottime", time.clock_gettime(time.CLOCK_BOOTTIME))):
        value = evidence.get(field)
        require(type(value) in (int, float) and math.isfinite(value) and 0 <= now - value <= 60, "RECONCILIATION_EVIDENCE_STALE")
    lifetimes = evidence.get("lifetimes")
    require(
        isinstance(lifetimes, list) and 1 <= len(lifetimes) <= 32 and len({x["pid"] for x in lifetimes}) == len(lifetimes),
        "RECONCILIATION_LIFETIMES_INVALID",
    )
    for item in lifetimes:
        require(
            set(item) == {"pid", "boot_id", "start_ticks"} and item["boot_id"] == old["guardian"]["boot_id"],
            "RECONCILIATION_LIFETIME_BINDING_CHANGED",
        )
        _ended(item)
    require(
        evidence.get("native_before") == evidence.get("native_after") == native == native_checkpoint(Path(store.path).parents[2]),
        "RECONCILIATION_NATIVE_HISTORY_CHANGED",
    )
    ledger = ledger_checkpoint(store.path)
    require(evidence.get("ledger_before") == evidence.get("ledger_after") == ledger, "RECONCILIATION_LEDGER_HISTORY_CHANGED")
    require(
        old_intent["root"] == str(Path(store.path).parents[2])
        and old_intent["request"]["order_id"] in record["order_ids"]
        and old_intent["request"]["service_action"] == "line_stack_restart",
        "RECONCILIATION_OLD_SCOPE_CHANGED",
    )
    return dict(
        bindings=bindings,
        evidence_ref=ref,
        owner_context=owner_context(),
        native=native,
        ledger=ledger,
        evidence_times={k: evidence[k] for k in ("observed_monotonic", "observed_boottime")},
    )


def _fresh_tail(value):
    for field, now in (("observed_monotonic", time.monotonic()), ("observed_boottime", time.clock_gettime(time.CLOCK_BOOTTIME))):
        require(0 <= now - value["evidence_times"][field] <= 60, "RECONCILIATION_FINAL_EVIDENCE_STALE")


def append(c, store, record, request, native, guard):
    checked = validate(c, store, record, request, native)
    value = dict(
        schema="forge-c/owner-bootstrap-reconciliation/1",
        status="FAILED_ATTEMPT_RECONCILED_QUIESCENT",
        request=request,
        reconciler_record_sha256=digest(record),
        reconciler_source_revisions=record["source_revisions"],
        **checked,
        observed_monotonic=time.monotonic(),
        observed_boottime=time.clock_gettime(time.CLOCK_BOOTTIME),
        no_authority_renewal=True,
        old_outcomes_unchanged=True,
    )
    key = request["intent_id"] + "-reconciliation-" + digest(dict(request=request, issuer=digest(record)))
    require(
        c.execute("SELECT 1 FROM afo_independent_decisions WHERE decision_id=?", (key,)).fetchone() is None,
        "RECONCILIATION_ALREADY_APPENDED_NO_REPLAY",
    )
    guard()  # fresh current issuer/Intent/action/both clocks before small freshness tail
    _fresh_tail(value)
    c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)", (key, KIND, canonical(value).decode(), digest(value)))
    return dict(decision_id=key, sha256=digest(value))


def consume(c, store, record, ref, intent_id, native, guard):
    require(isinstance(ref, dict) and set(ref) == {"decision_id", "sha256"}, "RECONCILIATION_OPT_IN_REQUIRED")
    value = _row(c, ref["decision_id"], KIND)
    require(
        digest(value) == ref["sha256"]
        and value["status"] == "FAILED_ATTEMPT_RECONCILED_QUIESCENT"
        and value["reconciler_record_sha256"] == digest(record)
        and value["request"]["intent_id"] == intent_id
        and value["no_authority_renewal"] is True
        and value["old_outcomes_unchanged"] is True,
        "RECONCILIATION_PAIR_OR_ISSUER_CHANGED",
    )
    require(
        validate(c, store, record, value["request"], native)
        == {k: value[k] for k in ("bindings", "evidence_ref", "owner_context", "native", "ledger", "evidence_times")},
        "RECONCILIATION_FRESH_QUIET_CHANGED",
    )
    guard()
    _fresh_tail(value)
