"""Scoped stack preparation for an already claimed line-local product execution.

This is not global shutdown or resource admission. The existing signed order,
finite mission, intent, lease, process identities and M0 locks remain authoritative.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

from .durable import Refused, canonical, digest

FILE = "FORGE_LINE_STACK_PAYLOAD"
SHA = "FORGE_LINE_STACK_PAYLOAD_SHA256"


def selected():
    return bool(os.environ.get(FILE) or os.environ.get(SHA))


def _descendant(pid, ancestor, start):
    from .line_orders import _proc_start

    if _proc_start(ancestor) != start:
        return False
    seen = set()
    while pid > 1 and pid not in seen:
        if pid == ancestor:
            return True
        seen.add(pid)
        try:
            raw = Path(f"/proc/{pid}/stat").read_text()
            pid = int(raw[raw.rfind(")") + 2:].split()[1])
        except (OSError, ValueError, IndexError):
            return False
    return False


def _bound(s):
    from . import line_recovery_control as C
    from . import line_recovery_product as P
    from .execution_lifecycle import Executions
    from .line_launcher import LineConfig
    from .local_agent import authorized, request_for
    from .operations import Intent
    from .policy import load
    from .queue import Store

    cfg = LineConfig.from_env()
    root = s["root"].resolve()
    if (os.environ.get("FORGE_DURABLE_AUTONOMY") != "1"
            or os.environ.get("FORGE_AFO_QUEUE_SCOPE") != "line-local"
            or cfg.stack_root.resolve() != root
            or Path(os.environ.get("FORGE_STATE_DIR", "/")).resolve() != root / "state"):
        raise Refused("LINE_STACK_SCOPE_MISMATCH")
    value = P.payload(os.environ.get(FILE), os.environ.get(SHA))
    store = Store(root / "state/supervisor/line-queue.sqlite3", must_exist=True)
    job, row, spec = P._job_for_payload(store, value)
    eff = load()
    control = C.configuration(job["line_role_authority_ref"], eff, request=request_for(row))
    C.require_job_binding(job, control, store=store)
    C.require_native_transport(job, cfg=cfg, control=control)
    intent = Intent(control["operations_intent"])
    record = intent.read()
    execution = Executions(store).get(job["job_id"])
    if (record["mode"] != "RUNNING" or record["epoch"] != job.get("operations_epoch")
            or os.environ.get("FORGE_OPERATIONS_INTENT") != control["operations_intent"]
            or os.environ.get("FORGE_OPERATIONS_PROFILE") != job["profile"]
            or s["profile"]["id"] != job["profile"] or s["profile"]["_sha256"] != job["profile_sha256"]
            or spec["profile"] != job["profile"] or eff.sha256 != job["policy_sha256"]
            or row["state"] not in ("ADMITTED", "RUNNING") or not authorized(row, eff, job["model"])
            or not time.time() < job["deadline_epoch"] or not execution
            or execution["launch_nonce"] != job["nonce"] or execution["mission_id"] != job["mission_id"]
            or execution["resource_lease"] != "HELD" or execution["authorization_state"] != "VALID"
            or execution["task_outcome"] != "ACTIVE"):
        raise Refused("LINE_STACK_AUTHORITY_OR_EXECUTION_FENCED")
    with store.tx() as c:
        owner = c.execute("SELECT holder,epoch FROM afo_resource_ownership WHERE resource='inference'").fetchone()
        held = c.execute(
            "SELECT record FROM afo_execution_liveness WHERE json_extract(record,'$.resource_lease')='HELD'"
        ).fetchall()
        requests = c.execute("SELECT 1 FROM afo_request_ledger WHERE state!='QUIESCENT' LIMIT 1").fetchone()
    if (not owner or tuple(owner) != (job["job_id"], execution["lease_epoch"])
            or len(held) != 1 or json.loads(held[0][0])["job_id"] != job["job_id"] or requests):
        raise Refused("LINE_STACK_RESOURCE_OR_REQUEST_NOT_QUIESCENT")
    from .line_recovery_worker import bound_order, metadata

    _, worker, _, _ = metadata(store, value["command_id"])
    if not bound_order(store, worker)["grant"].permit("launch_workorder", {
        "order_id": spec["wo"], "driver_class": spec["driver_class"], "model": spec["profile"],
        "service_action": "line_stack_restart",
    }).allow:
        raise Refused("LINE_STACK_ACTION_NOT_AUTHORIZED")

    def effect_guard():
        # File-based signed authority and deadline are fresh at each physical effect;
        # the intent/ledger locks keep their persisted bindings stable during it.
        current_policy = load()
        current_control = C.configuration(job["line_role_authority_ref"], current_policy, request=request_for(row))
        current_intent = intent.read()
        from .queue import ReadSnapshot

        with ReadSnapshot(root / "state/supervisor/line-queue.sqlite3", max_rows=10000, timeout_s=3) as reader:
            grant = bound_order(reader, worker)["grant"]
        if not grant.permit("launch_workorder", {"order_id": spec["wo"], "driver_class": spec["driver_class"],
                                               "model": spec["profile"], "service_action": "line_stack_restart"}).allow:
            raise Refused("LINE_STACK_ACTION_NOT_AUTHORIZED")
        if (current_control != control or current_policy.sha256 != eff.sha256
                or current_intent["mode"] != "RUNNING" or current_intent["epoch"] != job["operations_epoch"]
                or not time.time() < job["deadline_epoch"] or not authorized(row, current_policy, job["model"])):
            raise Refused("LINE_STACK_EFFECT_AUTHORITY_EXPIRED_OR_CHANGED")

    effect_guard.startup_binding = {k: job[k] for k in ("job_id", "nonce", "mission_id", "operations_epoch")}
    effect_guard.startup_binding["lease_epoch"] = execution["lease_epoch"]

    def failure_record(instance):
        return {"schema": "forge-c/line-startup-cleanup-unknown/1", "binding": effect_guard.startup_binding,
                "root": str(root), "profile": job["profile"], "profile_sha256": job["profile_sha256"],
                "provider_instance": instance, "provider_instance_sha256": digest(instance)}

    def record_failure(instance):
        value = failure_record(instance)
        with store.tx() as c:
            c.execute("INSERT OR IGNORE INTO afo_execution_evidence VALUES (?,?,?,?)", (job["job_id"],
                      "LINE_STARTUP_CLEANUP_UNKNOWN:" + digest(value), canonical(value).decode(), digest(value)))

    effect_guard.failure_record = failure_record
    effect_guard.record_cleanup_unknown = record_failure
    return cfg, store, job, execution, intent, effect_guard


def _observation_host(cfg, s):
    """A loopback relay and namespace-local Fabro are different observation subjects."""
    from dataclasses import replace

    from ..lrtx import stack
    from .line_launcher import ShellHost

    path = s["root"] / "run/services.json"
    record = json.loads(path.read_text()) if path.is_file() else {}
    if record.get("netns") == os.readlink("/proc/self/ns/net"):
        current = stack.process_identity(record.get("holder_pid"))
        if (record.get("root") != str(s["root"]) or record.get("profile") != s["profile"]["id"]
                or record.get("profile_sha256") != s["profile"]["_sha256"]
                or not stack._same_process(current, record.get("holder_identity"))
                or current.get("uid") != os.getuid()):
            raise Refused("LINE_STACK_OBSERVATION_NAMESPACE_UNPROVEN")
        return ShellHost(replace(cfg, fabro_host_port=s["ports"]["fabro"]))
    return ShellHost(cfg)


def _complete_runs(host):
    from ..fabro.client import RunInventory

    observation = host.fabro_run_inventory(active_only=True)
    if not isinstance(observation, RunInventory) or not observation.fresh():
        raise Refused("LINE_STACK_NATIVE_INVENTORY_UNKNOWN")
    return observation.rows


def _prelaunch(cfg, store, job, execution, s):
    from ..lrtx.stack import lock_path
    from .execution_lifecycle import Executions
    from .line_launcher import FabroInventoryUnknown, FabroUnavailable, ProcFS, flock_holders, survey
    from .line_liveness import KIND
    from .line_orders import _proc_start

    claim = Executions(store)._evidence(job["job_id"], KIND)
    if (not claim or claim.get("nonce") != job["nonce"] or claim.get("lease_epoch") != execution["lease_epoch"]
            or execution["native_run_ids"] or execution["admission_state"] != "DISPATCH_INTENT_RECORDED"
            or _proc_start(claim["pid"]) != claim["start"]
            or not _descendant(os.getpid(), claim["pid"], claim["start"])
            or claim["pid"] not in flock_holders(cfg.gpu_lock)
            or claim["pid"] not in flock_holders(lock_path(cfg.stack_root))):
        raise Refused("LINE_STACK_LAUNCH_CLAIM_OR_LOCKS_UNPROVEN")
    # The ordinary M2 API/PID rule: unavailable is allowed only when this root has no Fabro process.
    host = _observation_host(cfg, s)
    try:
        runs = _complete_runs(host)
    except (FabroInventoryUnknown, Refused) as exc:
        raise Refused("LINE_STACK_NATIVE_OBSERVATION_UNKNOWN") from exc
    except FabroUnavailable as exc:
        candidates, _ = survey(cfg.stack_root, ProcFS(), cfg.uid)
        if any(p["kind"] == "fabro" for p in candidates):
            raise Refused("LINE_STACK_NATIVE_OBSERVATION_UNKNOWN") from exc
        runs = []
    except Exception as exc:
        raise Refused("LINE_STACK_NATIVE_OBSERVATION_UNKNOWN") from exc
    if any((r.get("lifecycle", {}).get("status", {}).get("kind") or "").lower()
                             not in ("succeeded", "failed", "cancelled", "canceled", "dead")
                             for r in runs):
        raise Refused("LINE_STACK_NATIVE_NOT_QUIESCENT")


def _native_handoff(cfg, store, job, execution, workspace, model, s):
    """The existing native nonce reconciler handles a first serve before detach's receipt."""
    from .execution_lifecycle import Executions
    from .line_product_context import resolve
    from .product_job import from_native
    from .product_job import resolve as resolve_job

    bound = resolve_job(store, job["job_id"])
    context, _ = resolve(bound)
    if (Path(workspace).resolve() != Path(job["workspace"]).resolve()
            or model not in {m for models in context["role_models"].values() for m in models}):
        raise Refused("LINE_STACK_NATIVE_MODEL_CONTEXT_UNCONFIRMED")
    host = _observation_host(cfg, s)
    runs = _complete_runs(host)
    live = [r for r in runs if r.get("lifecycle", {}).get("status", {}).get("kind") not in
            ("succeeded", "failed", "cancelled", "canceled", "dead")]
    if len(live) != 1:
        raise Refused("LINE_STACK_NATIVE_IDENTITY_UNCONFIRMED")
    native = live[0]
    labels = native.get("labels") or {}
    if (native.get("lifecycle", {}).get("status", {}).get("kind") != "running"
            or labels.get("afo_agent") != job["job_id"] or labels.get("afo_nonce") != job["nonce"]
            or native.get("source_directory") != str(Path(job["workspace"]).resolve())):
        raise Refused("LINE_STACK_NATIVE_IDENTITY_CHANGED")
    if not execution["native_run_ids"]:
        submit = Executions(store)._evidence(job["job_id"], "PRODUCT_NATIVE_SUBMIT_INTENT")
        if (not submit or submit.get("job_id") != job["job_id"] or submit.get("nonce") != job["nonce"]
                or submit.get("role_context") != bound.get("line_product_context")
                or submit.get("source_revision") != job["factory_revision"]["commit"]):
            raise Refused("LINE_STACK_NATIVE_SUBMIT_INTENT_UNPROVEN")
        with host._client() as client:
            identity = from_native(store, native["id"], client=client)
        if identity != {"job_id": job["job_id"], "nonce": job["nonce"]}:
            raise Refused("LINE_STACK_NATIVE_ADOPTION_CHANGED")
    current = Executions(store).get(job["job_id"])
    if current["native_run_ids"] != [native["id"]] or current["identity_state"] != "CONFIRMED":
        raise Refused("LINE_STACK_NATIVE_IDENTITY_UNCONFIRMED")
    return current


@contextmanager
def fenced(s, action, *, model=None, workspace=None):
    """No global intent transition/store; keep actual intent locked through the bounded effect."""
    from .operations import Intent

    cfg, store, job, execution, intent, effect_guard = _bound(s)
    with intent.lock():
        current = Intent(intent.path).read()
        if current["mode"] != "RUNNING" or current["epoch"] != job["operations_epoch"]:
            raise Refused("LINE_STACK_OPERATIONS_SUPERSEDED")
        # Recheck the ledger after acquiring the shared intent fence.
        _, _, fresh, execution, _, effect_guard = _bound(s)
        if fresh != job:
            raise Refused("LINE_STACK_JOB_CHANGED")
        if action not in ("stop", "start", "serve"):
            raise Refused("LINE_STACK_ACTION_UNDECLARED")
        if action == "serve" and workspace is not None:
            execution = _native_handoff(cfg, store, job, execution, workspace, model, s)
        if execution["native_run_ids"]:
            if action != "serve":
                raise Refused("LINE_STACK_NATIVE_ALREADY_DISPATCHED")
            from ..lrtx import stack
            from .line_launcher import gpu_lock, held_stack_lock
            from .line_product_context import resolve
            from .product_job import resolve as resolve_job

            bound = resolve_job(store, job["job_id"])
            context, _ = resolve(bound)
            if (workspace is None or Path(workspace).resolve() != Path(job["workspace"]).resolve()
                    or model not in {m for models in context["role_models"].values() for m in models}
                    or len(execution["native_run_ids"]) != 1 or execution["identity_state"] != "CONFIRMED"):
                raise Refused("LINE_STACK_NATIVE_MODEL_CONTEXT_UNCONFIRMED")
            host = _observation_host(cfg, s)
            native = host.fabro_run(execution["native_run_ids"][0])
            if (native.get("lifecycle", {}).get("status", {}).get("kind") != "running"
                    or native.get("source_directory") != str(Path(job["workspace"]).resolve())
                    or (native.get("labels") or {}).get("afo_agent") != job["job_id"]
                    or (native.get("labels") or {}).get("afo_nonce") != job["nonce"]):
                raise Refused("LINE_STACK_NATIVE_IDENTITY_CHANGED")
            services = json.loads((s["root"] / "run/services.json").read_text())
            fabro = (services.get("processes") or {}).get("fabro") or {}
            observed_fabro = stack.process_identity(fabro.get("pid"))
            if (not fabro.get("identity") or not stack._same_process(observed_fabro, fabro["identity"])
                    or observed_fabro.get("uid") != os.getuid()
                    or not _descendant(os.getpid(), fabro["pid"], fabro["identity"]["start_ticks"])):
                raise Refused("LINE_STACK_NATIVE_CALLER_UNPROVEN")
            from ..lrtx import provider_process as provider

            provider.require_owner_view(fabro["pid"], fabro["identity"]["uid"], fabro.get("owner_view"))
            with gpu_lock(cfg.gpu_lock), held_stack_lock(cfg.stack_root), store.tx() as c:
                # Serialize a model change against new durable request reservations.
                current_execution = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?",
                                              (job["job_id"],)).fetchone()
                if (not current_execution or json.loads(current_execution[0]) != execution
                        or c.execute("SELECT 1 FROM afo_request_ledger WHERE state!='QUIESCENT' LIMIT 1").fetchone()):
                    raise Refused("LINE_STACK_EXECUTION_CHANGED_BEFORE_SERVE")
                effect_guard()
                def record_failure(instance):
                    value = effect_guard.failure_record(instance)
                    c.execute("INSERT OR IGNORE INTO afo_execution_evidence VALUES (?,?,?,?)", (job["job_id"],
                              "LINE_STARTUP_CLEANUP_UNKNOWN:" + digest(value), canonical(value).decode(), digest(value)))

                effect_guard.record_cleanup_unknown = record_failure
                failure = None
                try:
                    yield effect_guard
                except Exception as exc:
                    failure = exc
                # Commit a failed-startup hold before propagating its native node failure.
            if failure is not None:
                raise failure
        else:
            _prelaunch(cfg, store, job, execution, s)
            if model is not None and model not in s["profile"]["models"]["allowed"]:
                raise Refused("LINE_STACK_MODEL_NOT_PINNED")
            effect_guard()
            yield effect_guard


def stop(s):
    from ..lrtx import provider_process as provider
    from ..lrtx import stack

    with fenced(s, "stop") as guard, stack.line_effect_guard(guard):
        record = s["root"] / "run/services.json"
        if record.is_file() and json.loads(record.read_text()).get("serving_instance"):
            instance = stack.serving_instance(s)
            if not provider.stop(instance, fenced_effect=lambda effect: (guard(), effect())[1]):
                raise Refused("LINE_STACK_PROVIDER_QUIESCENCE_UNPROVEN")
        return stack._stop(s, managed=True)


def start(s, *, recovery=False):
    from ..lrtx import provider_process as provider
    from ..lrtx import stack

    with fenced(s, "start") as guard, stack.line_effect_guard(guard):
        path = s["root"] / "run/services.json"
        prior = json.loads(path.read_text()) if path.is_file() else {}
        if prior.get("serving_instance") and not provider.quiet(stack.serving_instance(s)):
            raise Refused("LINE_STACK_START_REQUIRES_STOPPED_PROFILE")
        if any(stack._alive(p["pid"], "ollama" if name == "ollama" else p["argv"][1])
               for name, p in (prior.get("processes") or {}).items()):
            raise Refused("LINE_STACK_START_REQUIRES_STOPPED_PROFILE")
        try:
            return stack._start(s, recovery=recovery)
        except Exception:
            instance = None
            # Failed startup teardown is monotonic under its original nonce.
            # It never renews start authority or releases unknown native capacity.
            try:
                record = json.loads(path.read_text())
                if record.get("startup_binding") != guard.startup_binding:
                    raise Refused("LINE_STACK_FAILED_STARTUP_CLEANUP_UNKNOWN")
                instance = record.get("serving_instance")
                if instance:
                    instance = stack.serving_instance(s)
                    if not provider.stop(instance, fenced_effect=lambda effect: effect()):
                        raise Refused("LINE_STACK_FAILED_STARTUP_CLEANUP_UNKNOWN")
                with stack.line_effect_guard(None):
                    stack._stop(s, managed=True)
                until = time.monotonic() + 3
                while True:
                    remaining = []
                    for process in (record.get("processes") or {}).values():
                        actual = provider.identity(process["pid"])
                        expected = process.get("identity") or {}
                        if (actual and actual.get("state") != "Z"
                                and actual.get("boot_id") == expected.get("boot_id")
                                and actual.get("start_ticks") == expected.get("start_ticks")):
                            remaining.append(process["pid"])
                    if not remaining:
                        break
                    if time.monotonic() >= until:
                        raise Refused("LINE_STACK_FAILED_STARTUP_CLEANUP_UNKNOWN")
                    time.sleep(0.02)
            except Exception as cleanup:
                guard.record_cleanup_unknown(instance)
                raise Refused("LINE_STACK_FAILED_STARTUP_CLEANUP_UNKNOWN") from cleanup
            raise


def serve(s, model, workspace=None):
    from ..lrtx import provider_process as provider
    from ..lrtx import stack

    with fenced(s, "serve", model=model, workspace=workspace) as guard, stack.line_effect_guard(guard):
        instance = stack.serving_instance(s)
        provider.require_live_instance(instance)
        return stack._serve_model(s, model, workspace, serving=instance)
