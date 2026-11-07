"""Private kernel/process/SQLite controls; not native/model role competence."""

import copy
import fcntl
import json
import os
import sqlite3
import subprocess
import sys

import pytest
from forge_factory.afo import owner_bootstrap_history as H
from forge_factory.afo import owner_profile_bootstrap as B
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.line_launcher import LineConfig, ShellHost
from forge_factory.afo.line_orders import Placer
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.lrtx import stack
from test_owner_supervised_development import supervised  # noqa: F401 - real private guardian fixture


def native_database(path, statuses=("succeeded", "failed")):
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as c:
        for table, columns in H.TABLE_COLUMNS.items():
            parts = ['"' + name + '" ' + kind for name, kind, _ in columns]
            pk = [name for name, _, k in sorted(columns, key=lambda x: x[2]) if k]
            if pk:
                parts += ["PRIMARY KEY(" + ",".join('"' + name + '"' for name in pk) + ")"]
            c.execute('CREATE TABLE "' + table + '"(' + ",".join(parts) + ")")
        c.execute("INSERT INTO legacy_run_history_activation(singleton) VALUES(1)")
        for n, status in enumerate(statuses):
            c.execute("INSERT INTO runs(id,status) VALUES(?,?)", ("PRIVATE-" + str(n), status))


class NativeClient:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def _get(self, _, **params):
        if params.get("status") == "removing":
            return {"data": [], "meta": {"total": 0, "has_more": False}}
        with sqlite3.connect(self.path) as c:
            data = [
                {"id": rid, "lifecycle": {"status": {"kind": status}}}
                for rid, status in c.execute("SELECT id,status FROM runs ORDER BY id")
            ]
        offset = params["page[offset]"]
        return {"data": data[offset : offset + 100], "meta": {"total": len(data), "has_more": offset + 100 < len(data)}}


@pytest.fixture
def boot(supervised, tmp_path, monkeypatch):  # noqa: F811 - imported pytest fixture is requested by name
    store = supervised["store"]
    root = store.path.parents[2]
    (root / "run").mkdir(mode=0o700)
    (root / "run").chmod(0o700)
    (root / "run/stack.lock").touch(mode=0o600)
    lock = root / "gpu.lock"
    lock.write_text("")
    lock.chmod(0o600)
    native = root / "fabro/storage/db/fabro.sqlite3"
    native_database(native)
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(root))
    monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", D.PROFILE)
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    # Only the external volume and fixed deployment path leaves are private TEST layout.
    monkeypatch.setattr("forge_factory.afo.host.preflight", lambda: {"ok": True})
    monkeypatch.setattr(B, "GPU_LOCK", lock)
    binary = root / "PRIVATE-TEST-fabro"
    binary.write_text("private measured binary identity; never executed")
    monkeypatch.setenv("FORGE_FABRO_BIN", str(binary))
    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    cfg = LineConfig(launch_dir=root, stack_root=root, gpu_lock=lock, fabro_bin=str(binary))
    monkeypatch.setattr(LineConfig, "from_env", classmethod(lambda cls: cfg))
    monkeypatch.setattr(ShellHost, "_client", lambda self: NativeClient(native))
    # Fresh TEST-only metadata and own guardian, never rewrite the first immutable control.
    from forge_factory import workorder
    from forge_factory.afo import line_native_transport as T
    from forge_factory.afo.durable import immutable_json
    from forge_factory.common import REPO_ROOT, sha256_file

    revision = {"commit": "a" * 40, "dirty": False}
    monkeypatch.setattr(workorder, "factory_revision", lambda: copy.deepcopy(revision))
    profile = stack.lp.load(D.PROFILE)
    native_id = "01M6KFRJB2PA9ZTN3K2M42V19H"
    proof = {
        "schema": T.SCHEMA,
        "scope": T.SCOPE,
        "verdict": "PASS",
        "production_mutations": False,
        "source_tracked_dirty": False,
        "source_revision": revision["commit"],
        "profile": D.PROFILE,
        "profile_sha256": D.PROFILE_SHA,
        "binary_sha256": sha256_file(binary),
        "launch_returncode": 0,
        "terminal_status": "SUCCEEDED",
        "labels_match": True,
        "fixture_terminal_confirmed": True,
        "own_server_stopped": True,
        "all_headers_equal_actual_run_id": True,
        "adapter_sha256": {n: sha256_file(REPO_ROOT / "factory/python/forge_factory" / n) for n in T.ADAPTERS},
        "harness_sha256": "c" * 64,
        "settings_sha256": "d" * 64,
        "graph_sha256": "e" * 64,
        "native_run_id": native_id,
        "request_count": len(profile["models"]["allowed"]),
        "requests": [
            {
                "path": "/v1/chat/completions",
                "x_session_id": native_id,
                "model": model,
                "stream": True,
                "max_tokens": 16384,
                "max_completion_tokens": None,
            }
            for model in profile["models"]["allowed"]
        ],
        "identity_controls": {k: {"pass": True, "accepted": value} for k, value in T.CONTROLS.items()},
    }
    measured = root / "PRIVATE-TEST-measurement.json"
    immutable_json(measured, proof)
    control = copy.deepcopy(supervised["control"])
    control["native_transport_ref"] = {"path": str(measured), "sha256": sha256_file(measured)}
    new_control = root / "PRIVATE-TEST-control-with-transport.json"
    immutable_json(new_control, control)
    D.close_guardian(supervised["ref"])
    record_ref = D.create(
        store,
        control_ref={"path": str(new_control), "sha256": sha256_file(new_control)},
        runtime_policy=supervised["runtime"],
        line_policy=supervised["line"],
        directive=D.DIRECTIVE,
        expiry_ticket=supervised["ticket"],
    )
    monkeypatch.setenv(D.FILE, record_ref["path"])
    monkeypatch.setenv(D.SHA, record_ref["sha256"])
    placer = Placer(object(), policy_path=supervised["line"], owner_supervised_development=True)
    children, effects = [], []

    def start(settings, *, recovery, control_only=False):
        assert settings["root"] == root and recovery
        stack._guard_effect()
        # An actual owned harmless process marks the physical effect boundary.
        p = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        children.append(p)
        effects.append("control" if control_only else "provider")
        return {"health": {"fabro": True}}

    monkeypatch.setattr(stack, "_start", start)
    monkeypatch.setattr(stack, "expose_api", lambda *_: {"api_bridge": "UP"})
    monkeypatch.setattr(
        stack, "status", lambda _: {"health": dict.fromkeys(["fabro", "ollama", "gateway", "llama_server"], True)}
    )
    record = D.current()
    instance = {
        "root": str(root),
        "profile": D.PROFILE,
        "profile_sha256": D.PROFILE_SHA,
        "owner_development_view": {
            "record_sha256": digest(record),
            "socket_identity": record["guardian_socket_identity"],
            "store_identity": record["store_identity"],
            "store_path": record["store_path"],
        },
    }
    monkeypatch.setattr(stack, "serving_instance", lambda _: instance)
    yield dict(
        store=store,
        placer=placer,
        root=root,
        native=native,
        effects=effects,
        children=children,
        original=supervised,
        instance=instance,
        lock=lock,
        binary=binary,
        proof=measured,
        cfg=cfg,
    )
    D.close_guardian(record_ref)
    if placer._act_lock:
        placer._act_lock.close()
    for p in children:
        if p.poll() is None:
            p.terminate()
        p.wait(timeout=3)


def test_supported_bootstrap_canonical_store_real_locks_guardian_and_processes(boot):
    store, placer = boot["store"], boot["placer"]
    before = MissionLedger(store).snapshot(D.MISSION)
    result = B.bootstrap(store, placer)
    assert result["status"] == "READY" and result["model_calls"] == result["placed_jobs"] == 0
    assert boot["effects"] == ["control", "provider"] and all(p.poll() is None for p in boot["children"])
    assert MissionLedger(store).snapshot(D.MISSION) == before
    assert placer._act_lock and not (boot["root"] / "state/conductor/conductor.sqlite3").exists()
    assert not store.orders() and not store.commands()
    with store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (B.INTENT_KIND,)).fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?", (B.RESULT_KIND,)).fetchone()[0] == 1
        intent = json.loads(
            c.execute("SELECT record FROM afo_independent_decisions WHERE kind=?", (B.INTENT_KIND,)).fetchone()[0]
        )
    # The first SWE.1 order of the first campaign lineage, with its own driver class.
    assert intent["request"]["order_id"] == D.ORDERS[0] == "WO-F014-SWE1-GPIOL-20261107-L40"
    assert intent["request"]["driver_class"] == "STM32N6_GPIO_LL_ST"
    fd = os.open(boot["lock"], os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # temporary GPU fence released, ACT retained
    finally:
        os.close(fd)


@pytest.mark.parametrize("status", ["UNKNOWN", "PENDING", "IN_FLIGHT", "UNRECOGNIZED"])
def test_all_uncertain_command_states_refuse_without_effects(boot, status):
    with boot["store"].tx() as c:
        # Exact outbox columns use a copied normal row shape (no execution fabricated).
        columns = [r[1] for r in c.execute("PRAGMA table_info(afo_commands_outbox)")]
        row = {k: "" for k in columns}
        row.update(command_id="private-uncertain", order_id="historical", attempt_id="old", kind="OTHER_KIND", state=status)
        c.execute(
            "INSERT INTO afo_commands_outbox(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")",
            [row[k] for k in columns],
        )
    with pytest.raises(Refused, match="COMMAND_OUTCOME_UNRESOLVED"):
        B.bootstrap(boot["store"], boot["placer"])
    assert boot["effects"] == []


@pytest.mark.parametrize("status", ["ACKED", "FAILED", "QUARANTINED"])
def test_inactive_history_is_preserved_not_cancelled_or_reset(boot, status):
    from test_afo_m2_queue import _env

    repo = boot["root"] / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    oid, _ = boot["store"].submit(_env(repo), repo=repo, max_queued=10)
    boot["store"].transition(oid, "PAUSED", "Historical inactive order")
    with boot["store"].tx() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(afo_commands_outbox)")]
        row = {k: "" for k in cols}
        row.update(command_id="private-ended", order_id=oid, attempt_id="old", kind="FABRO_LAUNCH", state=status)
        c.execute(
            "INSERT INTO afo_commands_outbox(" + ",".join(cols) + ") VALUES(" + ",".join("?" for _ in cols) + ")",
            [row[k] for k in cols],
        )
    before = boot["store"].order(oid), boot["store"].commands()
    assert B.bootstrap(boot["store"], boot["placer"])["status"] == "READY"
    assert (boot["store"].order(oid), boot["store"].commands()) == before


@pytest.mark.parametrize("status", ["running", "queued", "removing", "aborted", "dead", "timeout", "error", None])
def test_unknown_or_active_native_refuses_before_any_start(boot, status):
    with sqlite3.connect(boot["native"]) as c:
        c.execute("UPDATE runs SET status=? WHERE id=?", (status, "PRIVATE-0"))
    with pytest.raises(Refused, match="NATIVE_NOT_TERMINAL"):
        B.bootstrap(boot["store"], boot["placer"])
    assert boot["effects"] == []


def test_missing_native_db_never_becomes_empty_history(boot):
    boot["native"].unlink()
    with pytest.raises(Refused, match="NATIVE_DB_MISSING"):
        B.bootstrap(boot["store"], boot["placer"])
    assert boot["effects"] == [] and not boot["native"].exists()


def test_partial_control_start_writes_unknown_and_revokes_without_retry(boot, monkeypatch):
    def failure(*_, **__):
        stack._guard_effect()
        boot["effects"].append("possible-control-effect")
        raise OSError("PRIVATE simulated post-spawn transport failure")

    monkeypatch.setattr(stack, "_start", failure)
    with pytest.raises(OSError):
        B.bootstrap(boot["store"], boot["placer"])
    with boot["store"].tx() as c:
        rows = [
            json.loads(r[0]) for r in c.execute("SELECT record FROM afo_independent_decisions WHERE kind=?", (B.RESULT_KIND,))
        ]
    assert rows[0]["status"] == "UNKNOWN_REQUIRES_RECONCILIATION" and rows[0]["no_retry"]
    with pytest.raises(Refused):
        D.current()
    assert boot["effects"] == ["possible-control-effect"] and not boot["placer"]._act_lock


def test_native_change_during_control_start_blocks_provider_before_load(boot, monkeypatch):
    def start(*_, **kwargs):
        stack._guard_effect()
        boot["effects"].append("control")
        with sqlite3.connect(boot["native"]) as c:
            c.execute("INSERT INTO run_events(run_id,seq) VALUES('PRIVATE-0',1)")

    monkeypatch.setattr(stack, "_start", start)
    with pytest.raises(Refused, match="NATIVE_HISTORY_CHANGED"):
        B.bootstrap(boot["store"], boot["placer"])
    assert boot["effects"] == ["control"]


def test_control_cancellation_prevents_next_physical_effect(boot, monkeypatch):
    stopped = [False]

    def start(*_, **kwargs):
        stack._guard_effect()
        boot["effects"].append("control")
        stopped[0] = True

    monkeypatch.setattr(stack, "_start", start)
    with pytest.raises(Refused, match="CANCELLED"):
        B.bootstrap(boot["store"], boot["placer"], cancelled=lambda: stopped[0])
    assert boot["effects"] == ["control"]


def test_guard_catches_cancel_during_blocking_authorization_before_spawn(boot, monkeypatch):
    from forge_factory.afo import line_recovery_control as C

    original = C.configuration
    stopped = [False]
    calls = [0]

    def delayed(*args, **kw):
        result = original(*args, **kw)
        calls[0] += 1
        if calls[0] >= 4:
            stopped[0] = True
        return result

    monkeypatch.setattr(C, "configuration", delayed)
    with pytest.raises(Refused):
        B.bootstrap(boot["store"], boot["placer"], cancelled=lambda: stopped[0])
    assert "provider" not in boot["effects"]


def test_initial_intent_lock_is_nonblocking_and_does_not_change_intent(boot):
    from forge_factory.afo.operations import Intent

    before = Intent().read()
    with Intent().lock():
        with pytest.raises(Refused, match="OPERATIONS_INTENT_BUSY"):
            B.bootstrap(boot["store"], boot["placer"])
    assert Intent().read() == before and not boot["effects"]


@pytest.mark.parametrize("kind", ["missing-env", "foreign-env", "changed-binary", "missing-proof"])
def test_missing_or_different_native_binary_proof_refuses_before_effect(boot, monkeypatch, kind):
    if kind == "missing-env":
        monkeypatch.delenv("FORGE_FABRO_BIN")
    elif kind == "foreign-env":
        monkeypatch.setenv("FORGE_FABRO_BIN", "/foreign/unmeasured/fabro")
    elif kind == "changed-binary":
        boot["binary"].write_text("unmeasured replacement")
    else:
        boot["proof"].unlink()
    with pytest.raises(Refused):
        B.bootstrap(boot["store"], boot["placer"])
    assert boot["effects"] == []


@pytest.mark.parametrize("kind", ["gpu", "stack", "act"])
def test_existing_physical_lock_contention_refuses_without_effect(boot, kind):
    paths = {"gpu": boot["lock"], "stack": boot["root"] / "run/stack.lock", "act": boot["store"].path.parent / "act.lock"}
    path = paths[kind]
    path.touch(mode=0o600)
    with path.open("r+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises((Refused, stack.StackLockHeld)):
            B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"] and boot["placer"]._act_lock is None


@pytest.mark.parametrize("clock", ["monotonic", "boottime"])
def test_effect_tail_catches_expiry_during_heavy_authorization(boot, monkeypatch, clock):
    import time
    from types import SimpleNamespace

    from forge_factory.afo import line_recovery_control as C

    delta = [0]
    calls = [0]
    original = C.configuration
    monkeypatch.setattr(
        B,
        "time",
        SimpleNamespace(
            monotonic=lambda: time.monotonic() + (delta[0] if clock == "monotonic" else 0),
            clock_gettime=lambda which: time.clock_gettime(which) + (delta[0] if clock == "boottime" else 0),
            CLOCK_BOOTTIME=time.CLOCK_BOOTTIME,
            sleep=time.sleep,
        ),
    )

    def expires(*args, **kw):
        result = original(*args, **kw)
        calls[0] += 1
        if calls[0] >= 4:
            delta[0] = 601
        return result

    monkeypatch.setattr(C, "configuration", expires)
    with pytest.raises(Refused, match="DEADLINE"):
        B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"]


def test_guardian_loss_in_authorization_is_seen_before_spawn(boot, monkeypatch):
    from forge_factory.afo import line_recovery_control as C

    original = C.configuration
    calls = [0]

    def closes(*args, **kw):
        result = original(*args, **kw)
        calls[0] += 1
        if calls[0] >= 4:
            D.close_guardian({"path": os.environ[D.FILE]})
        return result

    monkeypatch.setattr(C, "configuration", closes)
    with pytest.raises(Refused):
        B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"]


@pytest.mark.parametrize("order", ["WO-F014-SWE6-AFOQUAL-20261104-L90", "WO-F014-SWE6-AFOQUAL-20261104-L90D",
                                   "WO-F014-SWE6-AFOQUAL-20261104-L90AA",  # allowance C, closed
                                   "WO-F014-SWE6-AFOQUAL-20261104-L90AD",  # allowance D, never registered
                                   "WO-F014-SWE1-GPIOL-20261107-L40BM"])  # beyond 64 per phase
def test_spent_and_beyond_allowance_orders_cannot_authorize_service(boot, order):
    with pytest.raises(Refused, match="BCD_SERVICE_ACTION_REFUSED"):
        B.bootstrap(boot["store"], boot["placer"], order_wo=order)
    assert not boot["effects"]


def test_any_campaign_order_bootstraps_with_its_own_driver(boot):
    order = "WO-F014-SWE3-SPIL-20261107-L41C"
    assert D.ORDER_DRIVERS[order] == "STM32N6_SPI_LL_ST"
    assert B.bootstrap(boot["store"], boot["placer"], order_wo=order)["status"] == "READY"


@pytest.mark.parametrize("value", ["foreign-profile", None])
def test_missing_or_foreign_managed_scope_is_not_bootstrap_authority(boot, monkeypatch, value):
    if value:
        monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", value)
    else:
        monkeypatch.delenv("FORGE_OPERATIONS_PROFILE")
    with pytest.raises(Refused):
        B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"]


def test_holder_file_without_services_projection_is_unknown(boot):
    (boot["root"] / "run/holder.pid").write_text("999999")
    with pytest.raises(Refused, match="HOLDER_PROJECTION_REMAINS"):
        B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"]


def test_unrecorded_owned_harmless_stack_process_is_not_absent(boot):
    import time

    from forge_factory.afo.line_launcher import ProcFS

    p = subprocess.Popen(["sleep", "infinity"], cwd=boot["root"])
    boot["children"].append(p)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        observed = ProcFS().get(p.pid)
        if observed and observed.cmdline == ["sleep", "infinity"]:
            break
        time.sleep(0.01)
    assert p.poll() is None
    with pytest.raises(Refused, match="UNRECORDED_STACK_PROCESS_PRESENT"):
        B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"]


def test_every_native_history_table_and_schema_changes_fingerprint(boot):
    before = H.native_checkpoint(boot["root"])
    with sqlite3.connect(boot["native"]) as c:
        c.execute("INSERT INTO run_events(run_id,seq,event_json) VALUES('PRIVATE-0',1,?)", ("PRIVATE artifact",))
    assert H.native_checkpoint(boot["root"]) != before
    with sqlite3.connect(boot["native"]) as c:
        c.execute("ALTER TABLE run_session_records ADD COLUMN unreviewed TEXT")
    with pytest.raises(Refused, match="NATIVE_SCHEMA_UNKNOWN"):
        H.native_checkpoint(boot["root"])


def test_actual_process_creation_checks_effect_guard_after_log_open(tmp_path, monkeypatch):
    monkeypatch.setattr(stack, "_nsenter", lambda _: [])
    children = []

    def refused():
        raise Refused("PRIVATE_EFFECT_FENCE_REFUSED")

    with stack.line_effect_guard(refused):
        with pytest.raises(Refused, match="PRIVATE_EFFECT_FENCE_REFUSED"):
            stack._in_ns(123, [sys.executable, "-c", "raise SystemExit(66)"], dict(os.environ), tmp_path / "log", tmp_path)
    # Same existing primitive still starts an actual harmless child when no scoped guard applies.
    proc = stack._in_ns(123, [sys.executable, "-c", "raise SystemExit(0)"], dict(os.environ), tmp_path / "log", tmp_path)
    children.append(proc)
    assert proc.wait(timeout=3) == 0


def test_main_optional_stage_retains_actual_signal_cancellation_before_cycle(boot, monkeypatch):
    import signal

    from forge_factory.afo import line_orders

    record = D.current()
    seen = []

    class PrivatePlacer:
        def __init__(self, *_, **__):
            pass

        def cycle(self):
            seen.append("UNEXPECTED_CYCLE")
            raise AssertionError("placement not expected")

    def stage(store, placer, *, cancelled):
        assert D.current()["guardian_pid"] == os.getpid()
        assert not cancelled()
        os.kill(os.getpid(), signal.SIGTERM)
        assert cancelled()
        seen.append("SIGNAL_CANCEL_PROPAGATED")

    monkeypatch.setattr(line_orders, "Placer", PrivatePlacer)
    monkeypatch.setattr(B, "bootstrap", stage)
    original = boot["original"]
    result = D.main(
        [
            "--control",
            record["control_ref"]["path"],
            "--runtime-policy",
            str(original["runtime"]),
            "--line-policy",
            str(original["line"]),
            "--campaigns",
            str(boot["root"] / "unused-campaigns"),
            "--expiry-ticket",
            str(original["ticket_path"]),
            "--bootstrap-managed-profile",
        ]
    )
    assert result == 0 and seen == ["SIGNAL_CANCEL_PROPAGATED"]


def test_missing_runtime_run_directory_cannot_skip_stack_fence(boot):
    (boot["root"] / "run/stack.lock").unlink()
    (boot["root"] / "run").rmdir()
    with pytest.raises(Refused, match="STACK_RUN_DIRECTORY_UNKNOWN"):
        B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"]


def test_gpu_lock_replacement_during_authorization_refuses_before_spawn(boot, monkeypatch):
    from forge_factory.afo import line_recovery_control as C

    original = C.configuration
    calls = [0]

    def replaced(*args, **kw):
        value = original(*args, **kw)
        calls[0] += 1
        if calls[0] == 4:
            boot["lock"].unlink()
            boot["lock"].write_text("replacement")
        return value

    monkeypatch.setattr(C, "configuration", replaced)
    with pytest.raises(Refused, match="PHYSICAL_LOCK_IDENTITY_CHANGED"):
        B.bootstrap(boot["store"], boot["placer"])
    assert not boot["effects"]


def test_null_and_future_unknown_states_are_not_quiescence():
    # Pure SQL predicate control: NULL remains unknown even in a future nullable schema.
    with sqlite3.connect(":memory:") as c:
        c.execute("CREATE TABLE afo_resource_ownership(resource TEXT,holder TEXT)")
        c.execute("CREATE TABLE afo_execution_liveness(record TEXT)")
        c.execute("CREATE TABLE afo_request_ledger(state TEXT)")
        c.execute("CREATE TABLE afo_commands_outbox(state TEXT)")
        c.execute("INSERT INTO afo_commands_outbox VALUES(NULL)")
        with pytest.raises(Refused, match="COMMAND_OUTCOME_UNRESOLVED"):
            B.quiet_ledger(c)
        c.execute("DELETE FROM afo_commands_outbox")
        c.execute("INSERT INTO afo_request_ledger VALUES(NULL)")
        with pytest.raises(Refused, match="REQUEST_NOT_QUIESCENT"):
            B.quiet_ledger(c)
