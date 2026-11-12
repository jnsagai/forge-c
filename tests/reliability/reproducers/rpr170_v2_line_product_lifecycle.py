"""Independent existing public line-product/stack API scenario. No owner keys, model or live services."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack

from forge_factory import workorder
from forge_factory.afo import line_launcher as LL, line_orders as O
from forge_factory.afo import line_recovery_control as C, line_recovery_coordination as K
from forge_factory.afo import line_recovery_product as P, line_recovery_worker as W, local_agent as L
from forge_factory.afo import operations, policy, host
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file
from forge_factory.lrtx import stack as ST
from forge_factory.lrtx.profile import load

SIG = "line-local product launch cannot prepare its owned provider without global shutdown"


def fixture(root):
    state = root / "lrtx/state"
    os.environ.update(FORGE_STATE_DIR=str(state), FORGE_AFO_QUEUE_SCOPE="line-local",
                      FORGE_OPERATIONS_INTENT=str(root / "intent.json"), FORGE_LRTX_ROOT=str(root / "lrtx"))
    os.environ.pop("FORGE_DURABLE_AUTONOMY", None)
    store = Store(state / "supervisor/line-queue.sqlite3")
    operations.Intent().set("RUNNING", actor="isolated-normal-fixture", reason="Bounded independent lifecycle control", initialize=True)
    repo = root / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    supplied = repo / "afo-manifests/m1.json"
    supplied.write_text('{"example":"isolated-lifecycle"}')
    wo = "WO-F014-SWE3-CONTROL-20261104-L99"
    profile = load("local-rtx-v2-omniverse2")
    eff = SimpleNamespace(mode="PILOT", sha256="c" * 64,
                          get=lambda k, default=None: {"budgets.max_model_tokens_per_order": 120000,
                          "budgets.max_order_wall_seconds": 600}.get(k, default))
    limits = dict(max_attempts=3, max_jobs=3, max_requests=20, max_tokens=500000,
                  max_tools=50, max_corrections=2, deadline=time.time() + 600)
    control = {"mission": {"mission_id": "rpr170-mission", "lineage": "rpr170-lineage", "limits": limits},
               "source_revision": "a" * 40, "policy_sha256": eff.sha256, "authorization_ref": "isolated-test-authority",
               "profile": profile["id"], "profile_sha256": profile["_sha256"], "role_capabilities": {},
               "product_role_trial": None, "operations_intent": os.environ["FORGE_OPERATIONS_INTENT"]}
    control_path = root / "control.json"
    immutable_json(control_path, control)
    ref = {"path": str(control_path), "sha256": sha256_file(control_path)}
    spec = {"schema": "forge-c/line-order/1", "wo": wo, "revision": "a" * 40,
            "profile": profile["id"], "run_model": "qwen3.6:35b-a3b", "purpose": "ASPICE_ONLY",
            "example": "0014-crc-st", "driver_class": "STM32N6_CRC_HAL", "phase": "SWE.3", "stop_after": "SWE.3",
            "resume_from": None, "resume_upto": None, "provided_from": None,
            "quality": {"targets": {"test": 100}}, "quality_via": "FLAG", "durable_control": ref}
    spec["digest"] = O._digest(spec)
    envelope = {"schema_version": "1.0", "request_id": wo, "tenant_scope": "line-local",
                "manifest_sha256": sha256_file(supplied), "input_manifest_ref": "afo-manifests/m1.json",
                "approved_by": "ISOLATED_TEST_FIXTURE", "authorization_ref": "AUTH-ISOLATED",
                "driver_class": spec["driver_class"], "target": spec["example"], "safety_scope": "SC-CONTROL",
                "model_profile": profile["id"], "submitted_utc": "2026-10-19T08:00:00Z", "priority": "NORMAL",
                "payload_digest": spec["digest"]}
    oid, _ = store.submit(envelope, repo=repo, max_queued=10)
    epoch = store.acquire_lease("line:local", "control", 600)
    aid = store.admit(oid, epoch=epoch, scope="line:local", policy_sha256=eff.sha256,
                      authorization_id="isolated-test-authority", max_concurrent=1)
    path = O.supervisor_dir() / "line-orders" / (wo + ".json")
    immutable_json(path, spec)
    worker = {"schema": "forge-c/line-recovery-worker-request/1", "mode": "PRODUCT", "order_id": oid,
              "attempt_id": aid, "control_ref": ref, "spec_ref": {"path": str(path), "sha256": sha256_file(path)},
              "line_origin": {"campaign_path": str(root / "approved-campaign.yaml")}}
    cmd = store.commands("PENDING")[0]
    K._bind_command(store, cmd["command_id"], worker)
    cmd = K.command(store, cmd["command_id"])
    (root / "line").mkdir()
    (root / "lrtx/run").mkdir(parents=True)
    cfg = LL.LineConfig(stack_root=root / "lrtx", repo=repo, runs_root=root / "runs", launch_dir=root,
                        gpu_lock=root / "line/gpu.lock", python=Path(sys.executable), guard=None)
    os.environ.update(W.config_environment(cfg))
    return SimpleNamespace(store=store, oid=oid, aid=aid, cmd=cmd, worker=worker, spec=spec,
                           control=control, eff=eff, cfg=cfg, profile=profile)


def main():
    with tempfile.TemporaryDirectory(prefix="rpr170-") as td, ExitStack() as mocks:
        root = Path(td)
        p = fixture(root)
        grant = SimpleNamespace(permit=lambda *a, **kw: SimpleNamespace(allow=True, code="AUTH_OK"))
        # Explicit fixture leaves only: public authorization, measured transport, native observation and effects.
        # SQLite queue/outbox/job/nonce/mission/lease/intent and launch claims remain production implementations.
        mocks.enter_context(patch.object(W, "bound_order", lambda *a: {"grant": grant}))
        mocks.enter_context(patch.object(C, "configuration", lambda *a, **kw: copy.deepcopy(p.control)))
        mocks.enter_context(patch.object(C, "require_native_transport", lambda *a, **kw: {"fixture": True}))
        mocks.enter_context(patch.object(policy, "load", lambda: p.eff))
        mocks.enter_context(patch.object(workorder, "factory_revision", lambda: {"commit": "a" * 40, "dirty": False}))
        mocks.enter_context(patch.object(L, "authorized", lambda *a, **kw: True))
        mocks.enter_context(patch.object(LL.ShellHost, "fabro_runs", lambda self: []))
        # External physical-volume readiness is an explicit fixture leaf: the verifier correctly
        # mounts real data_root read-only, while this private lifecycle Store is writable.
        # Production volume checking, Store/queue/mission/lease/intent and all effect predicates stay unchanged.
        mocks.enter_context(patch.object(host, "preflight", lambda *a, **kw: {"ok": True, "fixture": "external-physical-volume-ready"}))
        before = operations.Intent().read()
        effects = []
        def stopped(s, *, managed=False):
            effects.append(("stop", managed))
            return {"stopped": []}
        def started(s, **kw):
            effects.append(("start", ST.managed_serving()))
            return {"health": {"fabro": True, "gateway": True}}
        mocks.enter_context(patch.object(ST, "_stop", stopped))
        mocks.enter_context(patch.object(ST, "_start", started))
        seen = {}
        def transport(order, cfg):
            exclusion = P.claim_for_launch(cfg, order)
            env = P.execution_context(order)
            with patch.dict(os.environ, env):
                s = ST.settings(p.profile["id"])
                try:
                    with LL.gpu_lock(cfg.gpu_lock), LL.held_stack_lock(cfg.stack_root) as fd:
                        with patch.dict(os.environ, {ST.LOCK_FD_ENV: str(fd)}):
                            ST.stop(s)
                            ST.start(s)
                            positive = list(effects)
                            wrong = {**s, "root": root / "foreign-stack"}
                            try:
                                ST.stop(wrong)
                            except Refused:
                                pass
                            else:
                                raise RuntimeError("FOREIGN_STACK_LIFECYCLE_ACCEPTED")
                            if effects != positive:
                                raise RuntimeError("FOREIGN_STACK_EFFECT")
                except Refused as exc:
                    if exc.code == "MANAGED_PROFILE_SCOPE_MISMATCH":
                        seen["symptom"] = True
                    else:
                        raise
            after = operations.Intent().read()
            if after["mode"] != "RUNNING" or after["epoch"] != before["epoch"] or (cfg.stack_root / "state/conductor/conductor.sqlite3").exists():
                seen["symptom"] = True
            seen["effects"] = list(effects)
            seen["exclusion"] = exclusion
            return {"outcome": "LAUNCHED", "fabro_run_id": "ISOLATED-NATIVE-TRANSPORT"}
        out = P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, SimpleNamespace(list_runs=lambda **kw: []),
                         cfg=p.cfg, launch=transport)
        if not seen.get("exclusion") or out["actions"][0]["action"] != "launched":
            raise RuntimeError("NORMAL_REGISTERED_DISPATCH_SCENARIO_NOT_REACHED:" + str(out.get("actions", [])))
        if seen.get("symptom"):
            print("SYMPTOM_PRESENT:" + SIG)
            return 1
        if effects != [("stop", True), ("start", True)]:
            raise RuntimeError("MANAGED_LIFECYCLE_EFFECT_CONTROL_NOT_REACHED")
        if MissionLedger(p.store).snapshot("rpr170-mission")["attempts"] != 1:
            raise RuntimeError("MISSION_ATTEMPT_REFILLED")
    print("SYMPTOM_ABSENT")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:180])
        raise SystemExit(2)
