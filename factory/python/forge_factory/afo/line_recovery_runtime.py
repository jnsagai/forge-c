"""M6 native launch adapter using the M0/M2 host locks, guard, runtime and existing durable job nonce.

No stack restart, scheduler, job creation or grant widening. An unavailable stack or a different executing
revision refuses before model serving. Native Fabro submission rechecks the job's current authorities.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..common import REPO_ROOT, state_dir
from . import line_launcher as LL
from . import line_orders as LO
from . import line_recovery as R
from . import local_agent as L
from .queue import Store


def authorize(job, store=None):
    from .policy import load

    store = store or Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    order = store.order(job["order_id"])
    eff = load()
    protocol = ((job.get("role") == "afo-recovery-planner" and job.get("durable_protocol"))
                or (job.get("role") == "afo-factory-maintainer" and job.get("durable_native") == "maintenance-1"))
    if (not order or not protocol or not job.get("line_origin") or job.get("policy_sha256") != eff.sha256
            or job.get("state") != "LAUNCHING" or time.time() >= job.get("deadline_epoch", 0)
            or not L.enabled(job["role"], eff) or not L.authorized_job(order, eff, job)):
        return False
    from .execution_lifecycle import Executions
    from .mission_ledger import MissionLedger
    from .operations import Intent

    intent_path = (job.get("native_context") or {}).get("FORGE_OPERATIONS_INTENT")
    if not intent_path or not Path(intent_path).is_absolute() or type(job.get("operations_epoch")) is not int:
        return False
    intent = Intent(intent_path).read()
    if intent["mode"] != "RUNNING" or intent["epoch"] != job["operations_epoch"]:
        return False

    mission = MissionLedger(store).snapshot(job["mission_id"])
    execution = Executions(store).get(job["job_id"])
    if (time.time() >= mission["limits"]["deadline"] or not execution
            or execution["authorization_state"] != "VALID" or execution["resource_lease"] != "HELD"
            or execution["mission_id"] != job["mission_id"] or execution["launch_nonce"] != job["nonce"]):
        return False
    from .line_recovery_control import native_envelope_minimum

    if job.get("durable_native") == "maintenance-1":
        from .line_recovery_control import require_native_transport

        require_native_transport(job)
    native_envelope_minimum(job)  # no model serving when even the smallest request cannot fit
    # Source runs do not qualify diagnosis. A measured receipt or an explicitly signed trial is mandatory.
    entry = (job.get("role_capabilities") or {}).get(job["role"])
    if entry:
        from ..lrtx.role_capability import measured_objective, require

        identity = entry["identity"]
        if (identity["role"] != job["role"] or identity["model_digest"] != job.get("model_digest")
                or identity["precision"] != job.get("precision")
                or identity["adapter_revision"] != job["factory_revision"]["commit"]):
            return False
        size, work_class = measured_objective(job, job["role"])
        require(entry["ref"], identity, semantic_obligations=size, work_class=work_class)
    elif not job.get("qualification_manifest_sha256") and not job.get("product_role_trial"):
        return False
    origin = job["line_origin"]
    policy = LO.load_policy(Path(origin["policy_path"]) if origin.get("policy_path") else None)
    from . import owner_supervised_development as development

    if eff.mode == development.MODE:  # This lane has no signed grant file, by the owner's directive.
        grant = development.DevelopmentGrant(policy)
    else:
        grant = LO.verify_grant(policy, now=time.time(), base=Path(origin["auth_base"]) if origin.get("auth_base") else None,
                                allowed_signers=Path(origin["allowed_signers"]) if origin.get("allowed_signers") else None)
    return grant.permit("launch_workorder", {**L.request_for(order), "service_action": "line_stack_restart"}).allow


class Journal:
    def __init__(self, path):
        self.path = path

    def step(self, step, outcome="OK", **details):
        """Same shape as line_launcher.Attempt.step: _guard passes the guard's text as `result`."""
        from .line_conductor import append_jsonl

        append_jsonl(self.path, {"step": step, "outcome": outcome, **details})


def launch(job, *, cfg=None, host=None, procs=None, authorization=None):
    """Existing local_agent.poll launch_fn: one serialized native submission, no retry loop.

    Any failure before the native command is independently known not to have submitted Fabro. After it is
    invoked, uncertainty is retained by the existing job lifecycle and reconciled with its original nonce.
    """
    cfg = cfg or LL.LineConfig.from_env()
    host = host or LL.ShellHost(cfg)
    procs = procs or LL.ProcFS()
    permitted = authorization or authorize
    native_invoked = False
    try:
        if not permitted(job):
            raise R.BindingRefused("LINE_RECOVERY_NOT_AUTHORIZED")
        logs = L.directory(job["job_id"]) / "runtime-launch"
        logs.mkdir(parents=True, exist_ok=True)
        journal = Journal(logs / "steps.jsonl")
        env = LL.run_env(cfg, REPO_ROOT, job["profile"])
        # M2 intentionally drops managed intent; this role job must retain its already-bound stop fence.
        env.update(L.execution_context(job))
        cwd = REPO_ROOT / "factory/python"
        with LL.gpu_lock(cfg.gpu_lock), LL.held_stack_lock(cfg.stack_root):
            from .line_liveness import claim

            exclusion = claim(cfg, job)
            LL.live_runs(cfg, host, procs, **({"durable_exclusion": exclusion} if exclusion else {}))
            LL._guard(journal, host, procs, cfg, lambda _line: None)
            rc, output = host.stack(["status"], env=env, cwd=cwd, log=logs / "status.log")
            status = LL._last_json(output) or {}
            health = status.get("health")
            if rc or status.get("status") != "UP" or not isinstance(health, dict) or not health or not all(health.values()):
                raise R.BindingRefused("LINE_RECOVERY_STACK_NOT_HEALTHY")
            # This runs under the stack's actual environment. Never substitute patch similarity for exact provenance.
            rc, output = host.stack(["exec", "--", "python", "-c",
                                     "import json;from forge_factory.workorder import factory_revision;"
                                     "print(json.dumps(factory_revision()))"],
                                    env=env, cwd=cwd, log=logs / "revision.log")
            revision = LL._last_json(output) or {}
            if (rc or revision.get("dirty") is not False
                    or revision.get("commit") != job["factory_revision"].get("commit")):
                raise R.BindingRefused("LINE_RECOVERY_RUNTIME_REVISION_MISMATCH")
            from ..lrtx.profile import load

            profile = load(job["profile"])
            rc, output = host.stack(["exec", "--", "curl", "-s", "-m", "5",
                                     f"http://127.0.0.1:{profile['deployment']['ports']['gateway']}/health"],
                                    env=env, cwd=cwd, log=logs / "gateway-scope.log")
            gateway = LL._last_json(output) or {}
            gateway_revision = gateway.get("factory_revision") or {}
            if (rc or gateway.get("afo_queue_scope") != "line-local"
                    or gateway_revision.get("dirty") is not False
                    or gateway_revision.get("commit") != job["factory_revision"].get("commit")):
                raise R.BindingRefused("LINE_RECOVERY_GATEWAY_SCOPE_OR_REVISION_MISMATCH")
            if job.get("durable_native") == "maintenance-1" and gateway.get("durable_native_header") is not True:
                raise R.BindingRefused("LINE_NATIVE_TRANSPORT_GATEWAY_NOT_ENABLED")
            if not permitted(job):
                raise R.BindingRefused("LINE_RECOVERY_NOT_AUTHORIZED")
            rc, _ = host.stack(["exec", "--", "python", "-m", "forge_factory.lrtx.stack", "serve", "--model", job["model"]],
                               env=env, cwd=cwd, log=logs / "serve.log")
            if rc:
                raise R.BindingRefused("LINE_RECOVERY_MODEL_SERVE_FAILED")
            port = profile["deployment"]["ports"]["llama"]
            rc, output = host.stack(["exec", "--", "curl", "-s", "-m", "5",
                                     f"http://127.0.0.1:{port}/v1/models"],
                                    env=env, cwd=cwd, log=logs / "models.log")
            models = (LL._last_json(output) or {}).get("data")
            if (rc or not isinstance(models, list) or len(models) != 1
                    or not isinstance(models[0], dict) or models[0].get("id") != job["model"]):
                raise R.BindingRefused("LINE_RECOVERY_SERVED_MODEL_MISMATCH")
            LL._guard(journal, host, procs, cfg, lambda _line: None)
            if not permitted(job):
                raise R.BindingRefused("LINE_RECOVERY_NOT_AUTHORIZED")
            native_invoked = True
            rc, output = host.stack(["exec", "--", "python", "-m", "forge_factory.afo.line_recovery_runtime",
                                     "native-job", "--job", job["job_id"], "--order", job["order_id"]],
                                    env=env, cwd=cwd, log=logs / "native-launch.log")
            result = LL._last_json(output) or {}
            if rc or result.get("job_id") != job["job_id"] or result.get("nonce") != job["nonce"] or not result.get("run_id"):
                raise RuntimeError("LINE_RECOVERY_NATIVE_LAUNCH_UNCERTAIN")
            journal.step("native_launch", "RECEIPTED", run_id=result["run_id"])
            return result["run_id"]
    except Exception as exc:
        from .line_liveness import ClaimUncertain

        if isinstance(exc, ClaimUncertain):
            raise  # prior nonce claim is not proof that the job never submitted
        if not native_invoked:
            raise L.LaunchNotStarted(job, exc) from exc
        raise


def native_job(order_id, job_id):
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    rows = [job for job in L.records(store, order_id) if job["job_id"] == job_id]
    if len(rows) != 1 or not authorize(rows[0], store):
        raise R.BindingRefused("LINE_RECOVERY_NATIVE_JOB_NOT_AUTHORIZED")
    job = rows[0]
    if job["state"] != "LAUNCHING":
        raise R.BindingRefused("LINE_RECOVERY_NATIVE_JOB_STATE")
    return {"job_id": job_id, "nonce": job["nonce"], "run_id": L.launch(job)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["native-job"])
    parser.add_argument("--job", required=True)
    parser.add_argument("--order", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(native_job(args.order, args.job)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
