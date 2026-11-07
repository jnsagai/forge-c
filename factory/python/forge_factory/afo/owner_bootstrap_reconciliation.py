"""Append-only OS-owner acknowledgement of an independently cleaned failed startup.

This never cleans a process, renews authority, releases resources or changes an
old outcome. The independent cleanup file is data; current authority and fresh
normal physical quiescence are required by the coordinator on both paths.
"""

import hashlib
import math
import os
import re
import subprocess
import time
from pathlib import Path

from .durable import canonical, digest, strict_json
from .owner_profile_bootstrap import INTENT_KIND, RESULT_KIND, require

KIND = "OWNER_PROFILE_BOOTSTRAP_RECONCILED"
CONSUMED_KIND = "OWNER_PROFILE_BOOTSTRAP_RECONCILIATION_CONSUMED"
SCHEMA = "forge-c/owner-bootstrap-cleanup-evidence/1"
SCOPE_FIELDS = (
    "intent_path", "intent_epoch", "store_path", "store_identity", "profile", "profile_sha256",
    "mission", "driver_class", "order_ids", "order_drivers", "runtime_policy_sha256", "line_policy_sha256",
)
HOST_FIELDS = ("intent_path", "intent_epoch", "store_path", "store_identity")
COUNTER_KEYS = {"attempts", "jobs", "requests", "tools", "corrections", "charged_tokens"}
# Audited producer *formats*, not machine-specific records or source revisions.
# Only this old coordinator could consume without an explicit durable receipt.
LEGACY_FORMAT = {
    "owner_profile_bootstrap.py": "a175cd76a014c3e30cdace1b8c29a3a18143b8d42254e2bdd3748782a8ef25d1",
    "owner_bootstrap_reconciliation.py": "3fc096ede3677d8ce40f302d3fdbe8f2884f42acf4cc22c58604510de89cf522",
    "owner_supervised_development.py": "3cf9888de2cb97d51ca8dccdcaed499e58bfd574a68a201a2a1481411d15a3d0",
}


def _legacy_format(revisions):
    from ..common import REPO_ROOT

    if not isinstance(revisions, list) or not revisions:
        return False
    for revision in revisions:
        if not isinstance(revision, str) or not re.fullmatch("[0-9a-f]{40}", revision):
            return False
        for name, expected in LEGACY_FORMAT.items():
            obj = revision + ":factory/python/forge_factory/afo/" + name
            try:
                size = int(subprocess.check_output(
                    ["git", "-C", str(REPO_ROOT), "cat-file", "-s", obj], timeout=3, stderr=subprocess.DEVNULL
                ))
                if not 0 < size <= 128 * 1024:
                    return False
                raw = subprocess.check_output(
                    ["git", "-C", str(REPO_ROOT), "cat-file", "blob", obj], timeout=3, stderr=subprocess.DEVNULL
                )
            except (OSError, ValueError, subprocess.SubprocessError):
                return False
            if hashlib.sha256(raw).hexdigest() != expected:
                return False
    return True


def _scope(old, current):
    """An issuer of the closed mission is compared with how that mission ended; only host identity is current."""
    from . import owner_supervised_development as D

    if (old.get("mission") or {}).get("mission_id") == D.PRIOR_MISSION:
        return {**{k: current[k] for k in HOST_FIELDS}, **D.PRIOR_SCOPE}
    return current


def _driver(scope, order_id):
    drivers = scope.get("order_drivers")
    return scope["driver_class"] if drivers is None else drivers.get(order_id)


def _issued(c, sha, current):
    """Authenticate historical data only; never attest an expired/dead guardian."""
    from . import owner_supervised_development as D

    require(isinstance(sha, str) and re.fullmatch("[0-9a-f]{64}", sha), "RECONCILIATION_ISSUER_INVALID")
    old = _row(c, "owner-development-" + sha, D.MODE)
    scope = _scope(old, current)
    require(
        digest(old) == sha and old.get("schema") == D.SCHEMA and old.get("mode") == D.MODE
        and old.get("qualification_only") is True and old.get("acceptance") == "UNACCEPTED"
        and old.get("directive_sha256") == digest(dict(external_directive=D.DIRECTIVE))
        and all(old.get(k) == scope.get(k) for k in SCOPE_FIELDS),
        "RECONCILIATION_HISTORICAL_SCOPE_CHANGED",
    )
    _monotonic_accounting(old.get("mission_anchor"), scope.get("mission_anchor"))
    control = D._read_file(old["control_ref"])
    require(
        digest(control) == old["control_sha256"] and control["mission"] == old["mission"]
        and control["product_role_trials"] == old["trial_refs"]
        and control["source_revision"] in old["source_revisions"],
        "RECONCILIATION_HISTORICAL_CONTROL_CHANGED",
    )
    D._trial_envelopes(control)
    return old


def _monotonic_accounting(old, current):
    """Same-base restore cannot erase historical spend or unknown usage."""
    for anchor in (old, current):
        require(
            isinstance(anchor, dict) and set(anchor) == {"base_sha256", "counters", "usage_unknown"}
            and isinstance(anchor["base_sha256"], str) and re.fullmatch("[0-9a-f]{64}", anchor["base_sha256"])
            and isinstance(anchor["counters"], dict) and set(anchor["counters"]) == COUNTER_KEYS
            and all(type(v) is int and v >= 0 for v in anchor["counters"].values())
            and type(anchor["usage_unknown"]) is bool,
            "RECONCILIATION_ACCOUNTING_ANCHOR_INVALID",
        )
    require(
        old["base_sha256"] == current["base_sha256"]
        and all(current["counters"][k] >= old["counters"][k] for k in COUNTER_KEYS),
        "RECONCILIATION_ACCOUNTING_REBOUND",
    )
    require(not old["usage_unknown"] or current["usage_unknown"], "RECONCILIATION_HISTORICAL_UNKNOWN_USAGE_CHANGED")


def _scoped_request(value, issuer, current):
    """A bootstrap request names one order of its issuer's scope, with that order's driver class."""
    request = value.get("request", {})
    scope = _scope(issuer, current)
    return request == dict(
        order_id=request.get("order_id"), driver_class=_driver(scope, request.get("order_id")),
        model=scope["profile"], service_action="line_stack_restart",
    ) and request.get("order_id") in scope["order_ids"]


def _chain(c, current, intent_id, ack):
    """Check immutable old failure -> acknowledgement -> issuing successor data."""
    intent = _row(c, intent_id, INTENT_KIND)
    result = _row(c, intent_id + "-result", RESULT_KIND)
    old = _issued(c, intent["record_sha256"], current)
    reconciler = _issued(c, ack["reconciler_record_sha256"], current)
    successor_id = "owner-profile-bootstrap-" + digest(reconciler)
    successor = _row(c, successor_id, INTENT_KIND)
    bindings = ack.get("bindings") or {}
    require(
        intent_id == "owner-profile-bootstrap-" + digest(old)
        and intent_id != successor_id
        and result.get("status") == "UNKNOWN_REQUIRES_RECONCILIATION" and result.get("no_retry") is True
        and result.get("record_sha256") == digest(old)
        and intent.get("control_ref") == old["control_ref"]
        and ack.get("schema") == "forge-c/owner-bootstrap-reconciliation/1"
        and ack.get("status") == "FAILED_ATTEMPT_RECONCILED_QUIESCENT"
        and ack.get("no_authority_renewal") is True and ack.get("old_outcomes_unchanged") is True
        and ack["request"] == dict(intent_id=intent_id, result_sha256=digest(result), evidence_ref=ack["evidence_ref"])
        and bindings == dict(
            old_intent_id=intent_id, bootstrap_nonce=intent_id, old_intent_sha256=digest(intent),
            old_result_sha256=digest(result), old_record_sha256=digest(old), old_source_revisions=old["source_revisions"],
            old_control_ref=old["control_ref"], profile=old["profile"], profile_sha256=old["profile_sha256"],
            mission=old["mission"], store_path=old["store_path"], store_identity=old["store_identity"],
            intent_epoch=old["intent_epoch"],
        )
        and ack.get("reconciler_source_revisions") == reconciler["source_revisions"]
        and successor.get("record_sha256") == digest(reconciler)
        and successor.get("control_ref") == reconciler["control_ref"]
        and successor.get("root") == intent.get("root") == str(Path(current["store_path"]).parents[2])
        and successor.get("qualification_only") is True and successor.get("acceptance") == "UNACCEPTED"
        and successor.get("model_calls") == 0
        and _scoped_request(intent, old, current) and _scoped_request(successor, reconciler, current),
        "RECONCILIATION_HISTORICAL_CHAIN_CHANGED",
    )
    return reconciler, successor_id, successor


def historical_acknowledged(c, store, current, intent_id):
    """Past consumption is data, never current authority or refreshed cleanup.

    No old guardian challenge, clock/freshness extension, or current-history
    equality is implied here. The coordinator always performs its normal fresh
    issuer/Intent/physical/native checks, including the current pending failure.
    """
    require(str(store.path.resolve()) == current["store_path"], "RECONCILIATION_HISTORICAL_STORE_CHANGED")
    matches = []
    for key, in c.execute("SELECT decision_id FROM afo_independent_decisions WHERE kind=?", (KIND,)):
        ack = _row(c, key, KIND)
        if ack.get("request", {}).get("intent_id") != intent_id:
            continue
        require(
            key == intent_id + "-reconciliation-" + digest(dict(request=ack["request"], issuer=ack["reconciler_record_sha256"])),
            "RECONCILIATION_HISTORICAL_KEY_CHANGED",
        )
        successor_id = "owner-profile-bootstrap-" + str(ack.get("reconciler_record_sha256"))
        exists = c.execute(
            "SELECT 1 FROM afo_independent_decisions WHERE decision_id=? AND kind=?", (successor_id, INTENT_KIND)
        ).fetchone()
        if exists is None:
            continue  # An unconsumed or future acknowledgement is not history.
        reconciler, successor_id, successor = _chain(c, current, intent_id, ack)
        token = dict(decision_id=key, sha256=digest(ack))
        consumed_id = successor_id + "-reconciliation-consumed"
        exists = c.execute("SELECT 1 FROM afo_independent_decisions WHERE decision_id=?", (consumed_id,)).fetchone()
        if exists:
            consumed = _row(c, consumed_id, CONSUMED_KIND)
            require(
                consumed == _consumption_value(
                    intent_id, token, current=reconciler, successor_id=successor_id, successor=successor
                )
                and successor.get("schema") == "forge-c/owner-profile-bootstrap-intent/2"
                and successor.get("reconciliation_ref") == token,
                "RECONCILIATION_CONSUMPTION_CHANGED",
            )
        else:
            require(
                successor.get("schema") == "forge-c/owner-profile-bootstrap-intent/1"
                and "reconciliation_ref" not in successor and _legacy_format(reconciler["source_revisions"]),
                "RECONCILIATION_LEGACY_FORMAT_UNPROVEN",
            )
        matches.append(key)
    require(len(matches) <= 1, "RECONCILIATION_MULTIPLE_HISTORICAL_ACKS")
    return bool(matches)


def _consumption_value(intent_id, ref, *, current, successor_id, successor):
    return dict(
        schema="forge-c/owner-bootstrap-reconciliation-consumed/1", status="CONSUMED_BY_FOLLOWING_BOOTSTRAP_INTENT",
        old_intent_id=intent_id, reconciliation_ref=ref, successor_intent_id=successor_id,
        successor_intent_sha256=digest(successor), issuer_record_sha256=digest(current),
        no_authority_renewal=True, old_outcomes_unchanged=True,
    )


def record_consumption(c, current, ref, intent_id, successor_id, successor, checked, guard):
    """Same writer transaction as successor INTENT; any failure rolls back both."""
    guard()
    _fresh_tail(checked)
    value = _consumption_value(intent_id, ref, current=current, successor_id=successor_id, successor=successor)
    c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)", (
        successor_id + "-reconciliation-consumed", CONSUMED_KIND, canonical(value).decode(), digest(value),
    ))


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
            old.get(k) == record.get(k)
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
                "order_drivers",
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
    return value
