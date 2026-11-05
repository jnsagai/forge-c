"""Real private old issuer death, canonical receipts and fresh normal fences; no cleanup API."""

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from forge_factory.afo import owner_bootstrap_history as H
from forge_factory.afo import owner_bootstrap_reconciliation as R
from forge_factory.afo import owner_profile_bootstrap as B
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.common import sha256_file
from test_owner_profile_bootstrap import boot  # noqa: F401 - real private canonical fixture
from test_owner_supervised_development import supervised  # noqa: F401 - transitive guardian fixture

OLD_ISSUER = r"""
import json,os,sys
from pathlib import Path
from forge_factory.afo import owner_supervised_development as D,owner_profile_bootstrap as B,line_recovery_control as C,host
from forge_factory.afo.queue import Store
from forge_factory.afo.line_orders import Placer
from forge_factory.afo.line_launcher import LineConfig
from forge_factory.afo.durable import digest
from forge_factory.lrtx import stack
from forge_factory import workorder
workorder.factory_revision=lambda:dict(commit='a'*40,dirty=False)
cfg=json.loads(sys.argv[1]);root=Path(cfg['root'])
C.revision=lambda:dict(commit='a'*40,dirty=False)
host.preflight=lambda:dict(ok=True)
B.GPU_LOCK=Path(cfg['gpu'])
LineConfig.from_env=classmethod(lambda cls:LineConfig(launch_dir=root,stack_root=root,gpu_lock=Path(cfg['gpu']),fabro_bin=cfg['binary']))
store=Store(Path(os.environ['FORGE_STATE_DIR'])/'supervisor/line-queue.sqlite3',must_exist=True)
ref=D.create(store,control_ref=cfg['control_ref'],runtime_policy=Path(cfg['runtime']),line_policy=Path(cfg['line']),directive=D.DIRECTIVE,expiry_ticket=cfg['ticket'])
os.environ.update({D.FILE:ref['path'],D.SHA:ref['sha256']})
record=D.current()
def fail(*a,**k):raise RuntimeError('PRIVATE_FAILED_BOOTSTRAP_NO_MODEL')
stack._start=fail
placer=Placer(object(),policy_path=Path(cfg['line']),owner_supervised_development=True)
try:
 try:B.bootstrap(store,placer)
 except RuntimeError:pass
 key='owner-profile-bootstrap-'+digest(record)
 with store.tx() as c: result=json.loads(c.execute('SELECT record FROM afo_independent_decisions WHERE decision_id=?',(key+'-result',)).fetchone()[0])
 print(json.dumps(dict(record=record,intent_id=key,result_sha256=digest(result))),flush=True)
finally:D.close_guardian(ref)
"""


@pytest.fixture
def pending(boot, monkeypatch, request):  # noqa: F811 - imported fixture
    current = D.current()
    cfg = dict(
        root=str(boot["root"]),
        gpu=str(boot["lock"]),
        binary=str(boot["binary"]),
        control_ref=current["control_ref"],
        runtime=str(boot["original"]["runtime"]),
        line=str(boot["original"]["line"]),
        ticket=boot["original"]["ticket"],
    )
    child = subprocess.run(
        [sys.executable, "-c", OLD_ISSUER, json.dumps(cfg)], capture_output=True, text=True, timeout=15, check=False
    )
    assert child.returncode == 0, child.stderr[-2000:]
    old = json.loads(child.stdout.strip().splitlines()[-1])
    # Real isolated namespace lifetime; no hardware/model/service is involved.
    probe = subprocess.Popen(["unshare", "--user", "--map-root-user", "--net", "sleep", "30"])
    try:
        until = time.monotonic() + 3
        while time.monotonic() < until:
            if probe.poll() is not None:
                raise RuntimeError("PRIVATE_NAMESPACE_LEAF_UNAVAILABLE")
            net = os.readlink(f"/proc/{probe.pid}/ns/net")
            if net != os.readlink("/proc/self/ns/net"):
                break
            time.sleep(0.01)
        namespace = {k: os.readlink(f"/proc/{probe.pid}/ns/{k}") for k in ("user", "net", "pid")}
        namespace["uid_map"] = [list(map(int, x.split())) for x in Path(f"/proc/{probe.pid}/uid_map").read_text().splitlines()]
        from forge_factory.lrtx.provider_process import identity

        observed = identity(probe.pid)
    finally:
        if probe.poll() is None:
            probe.terminate()
        probe.wait(timeout=3)
    D.close_guardian(dict(path=os.environ[D.FILE]))
    ref = D.create(
        boot["store"],
        control_ref=current["control_ref"],
        runtime_policy=boot["original"]["runtime"],
        line_policy=boot["original"]["line"],
        directive=D.DIRECTIVE,
        expiry_ticket=boot["original"]["ticket"],
    )
    request.addfinalizer(lambda: D.close_guardian(ref))
    monkeypatch.setenv(D.FILE, ref["path"])
    monkeypatch.setenv(D.SHA, ref["sha256"])
    new = D.current()
    boot["instance"]["owner_development_view"].update(
        record_sha256=digest(new),
        socket_identity=new["guardian_socket_identity"],
        store_identity=new["store_identity"],
        store_path=new["store_path"],
    )
    oldrecord = old["record"]
    with boot["store"].tx() as c:
        intent = json.loads(
            c.execute("SELECT record FROM afo_independent_decisions WHERE decision_id=?", (old["intent_id"],)).fetchone()[0]
        )
        before_unknown = c.execute(
            "SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=?", (old["intent_id"] + "-result",)
        ).fetchone()
    # Unchanged stopped projection, just as root's independently cleaned214 case.
    services = boot["root"] / "run/services.json"
    stack_record = dict(root=str(boot["root"]), profile_sha256=D.PROFILE_SHA, processes={})
    services.write_text(json.dumps(stack_record))
    services.chmod(0o600)
    unit = dict(name="forge-c-owner-development-aaaaaaaa-20261105.service", MainPID="0", InvocationID="b" * 32)
    real_check_output = subprocess.check_output

    def systemctl_leaf(argv, *a, **k):
        if argv[:3] == ["systemctl", "--user", "show"]:
            assert argv[3] == unit["name"]
            return "MainPID=0\nInvocationID=" + unit["InvocationID"] + "\nLoadState=loaded\nActiveState=failed\n"
        return real_check_output(argv, *a, **k)

    monkeypatch.setattr(subprocess, "check_output", systemctl_leaf)
    native = H.native_checkpoint(boot["root"])
    ledger = R.ledger_checkpoint(boot["store"].path)
    evidence = dict(
        schema=R.SCHEMA,
        status="WHOLE_STACK_QUIET_HISTORY_CONSERVED",
        old_intent_id=old["intent_id"],
        bootstrap_nonce=old["intent_id"],
        old_intent_sha256=digest(intent),
        old_result_sha256=old["result_sha256"],
        old_record_sha256=digest(oldrecord),
        old_source_revisions=oldrecord["source_revisions"],
        old_control_ref=oldrecord["control_ref"],
        profile=oldrecord["profile"],
        profile_sha256=oldrecord["profile_sha256"],
        mission=oldrecord["mission"],
        store_path=oldrecord["store_path"],
        store_identity=oldrecord["store_identity"],
        intent_epoch=oldrecord["intent_epoch"],
        next_source_revisions=new["source_revisions"],
        old_unit=unit,
        old_namespace=namespace,
        owner_context=R.owner_context(),
        observed_monotonic=time.monotonic(),
        observed_boottime=time.clock_gettime(time.CLOCK_BOOTTIME),
        whole_stack_quiet=True,
        unknown_occupants=[],
        lifetimes=[
            dict(
                pid=oldrecord["guardian_pid"],
                boot_id=oldrecord["guardian"]["boot_id"],
                start_ticks=oldrecord["guardian"]["start_ticks"],
            ),
            dict(pid=probe.pid, boot_id=observed["boot_id"], start_ticks=observed["start_ticks"]),
        ],
        native_before=native,
        native_after=native,
        ledger_before=ledger,
        ledger_after=ledger,
        services_before_sha256=sha256_file(services),
        services_after_sha256=sha256_file(services),
        holder_file_removed_after_quiet=True,
        old_lifetimes_fds_quiet=True,
        no_charge_reset_or_relabel=True,
    )
    parent = Path(new["intent_path"]).parent / "owner-bootstrap-reconciliation"
    parent.mkdir(mode=0o700)
    path = parent / "independent-cleanup.json"

    def write(value):
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return dict(path=str(path), sha256=sha256_file(path))

    return dict(
        boot=boot, old=old, evidence=evidence, write=write, ref=write(evidence), before_unknown=before_unknown, ledger=ledger
    )


def reconcile(p):
    return B.reconcile_unknown(
        p["boot"]["store"],
        p["boot"]["placer"],
        intent_id=p["old"]["intent_id"],
        result_sha256=p["old"]["result_sha256"],
        evidence_ref=p["ref"],
    )


def test_explicit_reconciliation_appends_exact_receipt_then_fresh_bootstrap(pending):
    p = pending
    b = p["boot"]
    with pytest.raises(Refused, match="PRIOR_ATTEMPT_UNRESOLVED"):
        B.bootstrap(b["store"], b["placer"])
    token = reconcile(p)
    assert b["effects"] == [] and b["placer"]._act_lock is None
    with b["store"].tx() as c:
        assert (
            c.execute(
                "SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=?", (p["old"]["intent_id"] + "-result",)
            ).fetchone()
            == p["before_unknown"]
        )
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (R.KIND,)).fetchone()[0] == 1
    assert R.ledger_checkpoint(b["store"].path) == p["ledger"]
    assert B.bootstrap(b["store"], b["placer"], reconciliation_ref=token)["status"] == "READY"
    with b["store"].tx() as c:
        consumed = c.execute(
            "SELECT record FROM afo_independent_decisions WHERE kind=?", (R.CONSUMED_KIND,)
        ).fetchall()
        assert len(consumed) == 1
        value = json.loads(consumed[0][0])
        successor = R._row(c, value["successor_intent_id"], B.INTENT_KIND)
        assert digest(successor) == value["successor_intent_sha256"]
        assert successor["reconciliation_ref"] == token
        assert R.historical_acknowledged(c, b["store"], D.current(), p["old"]["intent_id"])


@pytest.mark.parametrize("reject", ["intent", "consumed"])
def test_consumed_receipt_and_following_intent_rollback_together(pending, reject):
    p = pending
    b = p["boot"]
    key = "owner-profile-bootstrap-" + digest(D.current())
    # Reject either the first INTENT insert OR the second CONSUMED insert. The
    # latter proves the already-inserted successor is rolled back as well.
    condition = "NEW.decision_id='" + key + "'" if reject == "intent" else "NEW.kind='" + R.CONSUMED_KIND + "'"
    with b["store"].tx() as c:
        c.execute(
            "CREATE TRIGGER private_reject_bootstrap BEFORE INSERT ON afo_independent_decisions "
            "WHEN " + condition + " BEGIN SELECT RAISE(ABORT,'PRIVATE_INTENT_ABORT'); END"
        )
    p["evidence"]["ledger_before"] = p["evidence"]["ledger_after"] = R.ledger_checkpoint(b["store"].path)
    p["ref"] = p["write"](p["evidence"])
    token = reconcile(p)
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError, match="PRIVATE_INTENT_ABORT"):
        B.bootstrap(b["store"], b["placer"], reconciliation_ref=token)
    with b["store"].tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (R.CONSUMED_KIND,)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE decision_id=?", (key,)).fetchone()[0] == 0
    assert b["effects"] == []


@pytest.fixture
def acknowledged(pending):
    p = pending
    token = reconcile(p)
    B.bootstrap(p["boot"]["store"], p["boot"]["placer"], reconciliation_ref=token)
    p["token"] = token
    p["successor_id"] = "owner-profile-bootstrap-" + digest(D.current())
    return p


def test_historical_consumption_never_refreshes_cleanup_or_attests_old_guardian(acknowledged, monkeypatch):
    from types import SimpleNamespace

    p = acknowledged

    def unexpected(*_, **__):
        raise AssertionError("HISTORICAL_DATA_MUST_NOT_REISSUE_OR_REFRESH_AUTHORITY")

    monkeypatch.setattr(R, "validate", unexpected)
    monkeypatch.setattr(R, "time", SimpleNamespace(monotonic=unexpected, clock_gettime=unexpected))
    with p["boot"]["store"].tx() as c:
        assert R.historical_acknowledged(c, p["boot"]["store"], D.current(), p["old"]["intent_id"])


def change_row(c, key, update):
    from forge_factory.afo.durable import canonical

    row = c.execute("SELECT record FROM afo_independent_decisions WHERE decision_id=?", (key,)).fetchone()
    value = json.loads(row[0])
    update(value)
    c.execute("UPDATE afo_independent_decisions SET record=?,sha256=? WHERE decision_id=?",
              (canonical(value).decode(), digest(value), key))


@pytest.mark.parametrize("mutation", ["consumed", "successor", "old_result", "ack_issuer", "issuer_missing", "unconsumed_new_format"])
def test_historical_tamper_missing_wrong_issuer_and_new_unconsumed_ack_refuse(acknowledged, mutation):
    p = acknowledged
    with p["boot"]["store"].tx() as c:
        if mutation == "consumed":
            change_row(c, p["successor_id"] + "-reconciliation-consumed", lambda v:v.update(successor_intent_sha256="0"*64))
        elif mutation == "successor":
            change_row(c, p["successor_id"], lambda v:v["request"].update(order_id="FOREIGN"))
        elif mutation == "old_result":
            change_row(c, p["old"]["intent_id"] + "-result", lambda v:v.update(record_sha256="0"*64))
        elif mutation == "ack_issuer":
            change_row(c, p["token"]["decision_id"], lambda v:v.update(reconciler_record_sha256="0"*64))
        elif mutation == "issuer_missing":
            c.execute("DELETE FROM afo_independent_decisions WHERE decision_id=?", ("owner-development-" + p["old"]["intent_id"].removeprefix("owner-profile-bootstrap-"),))
        else:
            c.execute("DELETE FROM afo_independent_decisions WHERE decision_id=?", (p["successor_id"] + "-reconciliation-consumed",))
        with pytest.raises(Refused):
            R.historical_acknowledged(c, p["boot"]["store"], D.current(), p["old"]["intent_id"])


def test_unconsumed_future_acknowledgement_never_resolves_failure(pending):
    p = pending
    reconcile(p)
    with p["boot"]["store"].tx() as c:
        assert not R.historical_acknowledged(c, p["boot"]["store"], D.current(), p["old"]["intent_id"])
    with pytest.raises(Refused, match="PRIOR_ATTEMPT_UNRESOLVED"):
        B.bootstrap(p["boot"]["store"], p["boot"]["placer"])


def test_normal_coordinator_never_skips_a_second_pending_failure(pending):
    from forge_factory.afo.durable import canonical

    p = pending
    token = reconcile(p)
    current = D.current()
    b = p["boot"]
    cfg = dict(root=str(b["root"]), gpu=str(b["lock"]), binary=str(b["binary"]), control_ref=current["control_ref"],
               runtime=str(b["original"]["runtime"]), line=str(b["original"]["line"]), ticket=b["original"]["ticket"])
    issue_only = OLD_ISSUER.split("\ndef fail(", 1)[0] + "\nprint(json.dumps(record),flush=True)\nD.close_guardian(ref)\n"
    process = subprocess.run([sys.executable, "-c", issue_only, json.dumps(cfg)], capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr[-2000:]
    extra = json.loads(process.stdout.strip().splitlines()[-1])
    key = "owner-profile-bootstrap-" + digest(extra)
    # Deliberate private durable-history fault injection, not a claimed native
    # event: a second unresolved pair appears after the first cleanup receipt.
    # Its canonical issuer is real; no new process/native/charge is fabricated.
    with p["boot"]["store"].tx() as c:
        intent = copy.deepcopy(R._row(c, p["old"]["intent_id"], B.INTENT_KIND))
        intent.update(record_sha256=digest(extra), control_ref=extra["control_ref"])
        result = copy.deepcopy(R._row(c, p["old"]["intent_id"] + "-result", B.RESULT_KIND))
        result["record_sha256"] = digest(extra)
        for did, kind, value in ((key, B.INTENT_KIND, intent), (key + "-result", B.RESULT_KIND, result)):
            c.execute("INSERT INTO afo_independent_decisions VALUES(?,?,?,?)", (did, kind, canonical(value).decode(), digest(value)))
    with pytest.raises(Refused, match="PRIOR_ATTEMPT_UNRESOLVED"):
        B.bootstrap(p["boot"]["store"], p["boot"]["placer"], reconciliation_ref=token)
    assert p["boot"]["effects"] == []
    with p["boot"]["store"].tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (R.CONSUMED_KIND,)).fetchone()[0] == 0


@pytest.mark.parametrize("scope", ["mission", "store", "epoch", "orders", "driver", "policy"])
def test_historical_receipts_cannot_rebind_current_mission_or_scope(acknowledged, scope):
    p = acknowledged
    current = copy.deepcopy(D.current())
    if scope == "mission":
        current["mission"]["limits"]["max_jobs"] += 1
    elif scope == "store":
        current["store_path"] += ".foreign"
    elif scope == "epoch":
        current["intent_epoch"] += 1
    elif scope == "orders":
        current["order_ids"].append("UNLISTED-FIFTH")
    elif scope == "driver":
        current["driver_class"] = "FOREIGN"
    else:
        current["runtime_policy_sha256"] = "0" * 64
    with p["boot"]["store"].tx() as c, pytest.raises(Refused):
        R.historical_acknowledged(c, p["boot"]["store"], current, p["old"]["intent_id"])


def test_legacy_source_format_requires_actual_three_immutable_git_blobs():
    assert R._legacy_format(["887820300340dcc31a03f3dc46c31107e9aef9f3"])
    assert not R._legacy_format(["0" * 40])
    assert not R._legacy_format(["6eeac5962a45e40ba39414eafa5dd612bd669d56"])
    assert not R._legacy_format(["887820300340dcc31a03f3dc46c31107e9aef9f3", "0" * 40])


@pytest.mark.parametrize("approved", [True, False])
def test_legacy_receipt_chain_uses_format_proof_without_reaging_evidence(acknowledged, monkeypatch, approved):
    p = acknowledged
    called = []
    # ONLY the fake fixture source 'a'*40 is overlaid. The preceding test checks
    # real Git objects; all canonical issuer/control/role/receipt checks stay real.
    monkeypatch.setattr(R, "_legacy_format", lambda rev:called.append(rev) or approved)
    with p["boot"]["store"].tx() as c:
        c.execute("DELETE FROM afo_independent_decisions WHERE decision_id=?", (p["successor_id"] + "-reconciliation-consumed",))
        def legacy(v):
            v["schema"] = "forge-c/owner-profile-bootstrap-intent/1"
            del v["reconciliation_ref"]
        change_row(c, p["successor_id"], legacy)
        if approved:
            assert R.historical_acknowledged(c, p["boot"]["store"], D.current(), p["old"]["intent_id"])
        else:
            with pytest.raises(Refused, match="LEGACY_FORMAT_UNPROVEN"):
                R.historical_acknowledged(c, p["boot"]["store"], D.current(), p["old"]["intent_id"])
    assert called == [["a" * 40]]


@pytest.mark.parametrize(
    "field,value",
    [
        ("old_result_sha256", "0" * 64),
        ("old_intent_sha256", "0" * 64),
        ("old_record_sha256", "0" * 64),
        ("bootstrap_nonce", "foreign"),
        ("old_source_revisions", ["c" * 40]),
        ("next_source_revisions", ["c" * 40]),
        ("intent_epoch", 99),
        ("store_identity", {}),
        ("profile_sha256", "0" * 64),
        ("mission", {}),
        ("owner_context", {}),
        ("unknown_occupants", [123]),
        ("whole_stack_quiet", False),
        ("observed_monotonic", 0),
        ("observed_boottime", 0),
        ("native_before", {}),
        ("ledger_before", {}),
        ("services_before_sha256", "0" * 64),
        ("no_charge_reset_or_relabel", False),
        ("holder_file_removed_after_quiet", False),
        ("old_lifetimes_fds_quiet", False),
    ],
)
def test_wrong_stale_or_unaccounted_independent_evidence_refuses(pending, field, value):
    p = pending
    bad = copy.deepcopy(p["evidence"])
    bad[field] = value
    p["ref"] = p["write"](bad)
    with pytest.raises(Refused):
        reconcile(p)
    assert p["boot"]["effects"] == []
    with p["boot"]["store"].tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (R.KIND,)).fetchone()[0] == 0


def test_receipt_requires_exact_optin_and_rechecks_actual_history(pending):
    p = pending
    b = p["boot"]
    token = reconcile(p)
    with pytest.raises(Refused, match="PRIOR_ATTEMPT_UNRESOLVED"):
        B.bootstrap(b["store"], b["placer"])
    with pytest.raises(Refused):
        B.bootstrap(b["store"], b["placer"], reconciliation_ref={**token, "sha256": "0" * 64})
    with b["store"].tx() as c:
        c.execute(
            "INSERT INTO afo_operator_actions(action,actor,reason,utc) VALUES('PRIVATE','OWNER','changed after receipt','now')"
        )
    with pytest.raises(Refused, match="LEDGER_HISTORY_CHANGED"):
        B.bootstrap(b["store"], b["placer"], reconciliation_ref=token)
    assert b["effects"] == []


def test_live_foreign_lifetime_cannot_be_declared_clean(pending):
    p = pending
    own = subprocess.Popen(["sleep", "30"])
    try:
        from forge_factory.lrtx.provider_process import identity

        i = identity(own.pid)
        bad = copy.deepcopy(p["evidence"])
        bad["lifetimes"].append(dict(pid=own.pid, boot_id=i["boot_id"], start_ticks=i["start_ticks"]))
        p["ref"] = p["write"](bad)
        with pytest.raises(Refused, match="OLD_LIFETIME_LIVE"):
            reconcile(p)
        assert own.poll() is None
    finally:
        own.terminate()
        own.wait(timeout=3)


def test_collected_failed_unit_retains_historical_invocation_in_evidence(pending, monkeypatch):
    p = pending
    real = subprocess.check_output

    def collected(argv, *a, **k):
        if argv[:3] == ["systemctl", "--user", "show"]:
            return "MainPID=0\nInvocationID=\nLoadState=not-found\nActiveState=inactive\n"
        return real(argv, *a, **k)

    monkeypatch.setattr(subprocess, "check_output", collected)
    assert reconcile(p)["sha256"]
    assert p["evidence"]["old_unit"]["InvocationID"] == "b" * 32


@pytest.mark.parametrize(
    "fields",
    [
        dict(MainPID="123", InvocationID="b" * 32, LoadState="loaded", ActiveState="active"),
        dict(MainPID="0", InvocationID="c" * 32, LoadState="loaded", ActiveState="failed"),
        dict(MainPID="0", InvocationID="c" * 32, LoadState="not-found", ActiveState="inactive"),
    ],
)
def test_replaced_or_active_failed_unit_refuses(pending, monkeypatch, fields):
    p = pending
    real = subprocess.check_output

    def changed(argv, *a, **k):
        if argv[:3] == ["systemctl", "--user", "show"]:
            return "\n".join(k + "=" + v for k, v in fields.items()) + "\n"
        return real(argv, *a, **k)

    monkeypatch.setattr(subprocess, "check_output", changed)
    with pytest.raises(Refused, match="OLD_UNIT_CHANGED"):
        reconcile(p)


@pytest.mark.parametrize("kind", ["missing", "mismatch"])
def test_original_canonical_issuance_required_without_old_liveness(pending, kind):
    p = pending
    key = "owner-development-" + p["evidence"]["old_record_sha256"]
    with p["boot"]["store"].tx() as c:
        if kind == "missing":
            c.execute("DELETE FROM afo_independent_decisions WHERE decision_id=?", (key,))
        else:
            altered = copy.deepcopy(p["old"]["record"])
            altered["acceptance"] = "FALSE_APPROVAL"
            from forge_factory.afo.durable import canonical

            c.execute(
                "UPDATE afo_independent_decisions SET record=?,sha256=? WHERE decision_id=?",
                (canonical(altered).decode(), digest(altered), key),
            )
    with pytest.raises(Refused):
        reconcile(p)
    assert p["boot"]["effects"] == []


def test_current_authority_cancelled_after_full_validation_cannot_append(pending, monkeypatch):
    p = pending
    cancelled = [False]
    original = R.validate

    def delayed(*a, **k):
        value = original(*a, **k)
        cancelled[0] = True
        return value

    monkeypatch.setattr(R, "validate", delayed)
    with pytest.raises(Refused, match="CANCELLED"):
        B.reconcile_unknown(
            p["boot"]["store"],
            p["boot"]["placer"],
            intent_id=p["old"]["intent_id"],
            result_sha256=p["old"]["result_sha256"],
            evidence_ref=p["ref"],
            cancelled=lambda: cancelled[0],
        )
    with p["boot"]["store"].tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (R.KIND,)).fetchone()[0] == 0


def test_explicit_reconcile_does_not_duplicate_same_issuer_receipt(pending):
    p = pending
    reconcile(p)
    with pytest.raises(Refused, match="ALREADY_APPENDED_NO_REPLAY"):
        reconcile(p)
    with p["boot"]["store"].tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (R.KIND,)).fetchone()[0] == 1


@pytest.mark.parametrize("clock", ["monotonic", "boottime"])
def test_evidence_freshness_checked_after_heavy_validation(pending, monkeypatch, clock):
    from types import SimpleNamespace

    p = pending
    delta = [0]
    original = R.validate
    real_mono, real_boot = time.monotonic, time.clock_gettime
    monkeypatch.setattr(
        R,
        "time",
        SimpleNamespace(
            monotonic=lambda: real_mono() + (delta[0] if clock == "monotonic" else 0),
            clock_gettime=lambda which: real_boot(which) + (delta[0] if clock == "boottime" else 0),
            CLOCK_BOOTTIME=time.CLOCK_BOOTTIME,
        ),
    )

    def delayed(*a, **k):
        value = original(*a, **k)
        delta[0] = 61
        return value

    monkeypatch.setattr(R, "validate", delayed)
    with pytest.raises(Refused, match="FINAL_EVIDENCE_STALE"):
        reconcile(p)
    with p["boot"]["store"].tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (R.KIND,)).fetchone()[0] == 0
