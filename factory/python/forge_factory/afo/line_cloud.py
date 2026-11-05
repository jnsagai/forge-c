"""Cloud product scheduling reuses the line's durable retries, upstream routing and strike history.

Cloud slots are independent of the Omniverse GPU. Capacity is explicit in the
separately signed cloud policy; healthy checks make no model calls. The local
PILOT policy and authorization cannot enable this scheduler.
"""
import argparse
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path

from ..common import sha256_file
from . import line_orders as LO

PROFILE = "cloud-bridge-terra-author-sol-inspector"
CAPACITY = 2


def context_arguments(spec):
    context = spec.get("rework_context")
    if context is None:
        return []
    from ..rework_context import request

    try:
        context = request(context, spec.get("stop_after"), spec.get("resume_from"))
        if context["source_work_order"] == spec.get("wo"):
            raise ValueError("self source")
    except ValueError as exc:
        raise ValueError("CLOUD_REWORK_BINDING_INVALID") from exc
    args = ["--rework-from", context["source_work_order"],
            "--rework-inspection-sha256", context["inspection_sha256"],
            "--rework-gates-sha256", context["gate_log_sha256"]]
    if "source_phase" in context:
        args += ["--rework-source-phase", context["source_phase"],
                 "--rework-upstream-sha256", context["upstream_sha256"]]
    return args


def failed_context(line, plan):
    previous = plan.current
    upstream = plan.order.get("kind") == "UPSTREAM"
    if (previous is None or (not upstream and previous.phase != plan.order["phase"]) or not previous.rid
            or not line.ended_run(previous.wo, previous.rid)):
        raise ValueError("CLOUD_REWORK_SOURCE_NOT_KNOWN_TERMINAL")
    ws = line.workspace(previous.wo)
    if ws.is_symlink() or ws.parent.is_symlink() or not ws.is_dir():
        raise ValueError("CLOUD_REWORK_SOURCE_INVALID")

    def pin(path):
        if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ws.resolve())
                or path.stat().st_size > 1024 * 1024
                or any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(ws))):
            raise ValueError("CLOUD_REWORK_SOURCE_INVALID")
        return sha256_file(path)

    gates = pin(ws / ".forge-run/gates/gate-log.jsonl")
    inspections = sorted((ws / "inspection" / previous.phase).glob("INS*"))
    context = {"source_work_order": previous.wo, "phase": previous.phase, "gate_log_sha256": gates,
               "inspection_sha256": pin(inspections[-1]) if inspections else "ABSENT"}
    if upstream:
        from ..common import canonical_json, sha256_bytes
        from ..rework_context import upstream_snapshot

        routing = upstream_snapshot(ws, plan.order["phase"], previous.phase)
        context.update(phase=plan.order["phase"], source_phase=previous.phase,
                       upstream_sha256=sha256_bytes(canonical_json(routing)))
    context_arguments({**plan.order, "rework_context": context})
    return context


def validate_profile(profile):
    roles = {"author": "gpt-6.1-terra", "inspector": "gpt-6.1-sol"}
    models = ((profile.get("runtime") or {}).get("cloud_bridge") or {}).get("models") or {}
    if (profile.get("id") != PROFILE or profile.get("models", {}).get("default") != roles["author"]
            or (profile.get("structured") or {}).get("role_models") != roles
            or any(not isinstance(models.get(model), dict) or models[model].get("backend") != "codex"
                   or models[model].get("model") != model for model in roles.values())):
        raise ValueError("CLOUD_ACCOUNT_ROLE_BINDING_REQUIRED")


class CloudLine(LO.RealLine):
    """Observe the cloud Fabro server; launch into its existing namespace only."""
    def __init__(self, cfg=None, **kwargs):
        from ..lrtx import stack

        super().__init__(cfg, **kwargs)
        expected = stack.settings(PROFILE)["root"]
        if self.cfg.stack_root.resolve() != expected.resolve():
            raise ValueError("CLOUD_STACK_ROOT_MISMATCH")

    def live_runs(self):
        # The pinned Fabro API accepts pending/running, not the launcher aliases
        # submitted/queued/paused. A full page refuses rather than assuming that
        # additional active work is absent.
        try:
            with self.host._client() as client:
                runs = []
                for status in ("pending", "running"):
                    page = client.list_runs(limit=100, status=status)
                    if len(page) >= 100 or any(self.LL._kind(r) != status for r in page):
                        return None
                    runs.extend(page)
        except Exception:  # unavailable or malformed observation never means idle
            return None
        prefix = str(self.cfg.stack_root / "state") + "/"
        if any(not isinstance(r.get("id"), str) for r in runs):
            return None
        return sorted({r["id"] for r in runs if str(r.get("source_directory", "")).startswith(prefix)})

    def gpu_holders(self):
        raise ValueError("CLOUD_HAS_NO_GPU_ADMISSION")

    def spawn_launch(self, argv, wo):
        spec = LO.supervisor_dir() / "line-orders" / f"{wo}.json"
        out = self.cfg.launch_dir / f"launch-{wo}.out"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("ab") as fh:
            p = subprocess.Popen([self.python, "-m", "forge_factory.afo.line_cloud", "launch", "--spec", str(spec)],
                                 cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        return {"pid": p.pid, "start": LO._proc_start(p.pid)}

    def sweep(self):
        return {"ok": False, "refused": "CLOUD_INFRA_RECOVERY_REQUIRES_OWNED_RECIPE"}


def _authorized_spec(path, cfg):
    """A launch child rechecks the current signed policy, campaign and admitted queue command."""
    from . import line_campaign as campaigns
    from .queue import Store

    path = Path(path)
    spec = LO._load(path)
    if not spec or not isinstance(spec.get("wo"), str):
        raise ValueError("CLOUD_ORDER_SPEC_REQUIRED")
    expected = LO.supervisor_dir() / "line-orders" / f"{spec['wo']}.json"
    if path.is_symlink() or path.resolve() != expected.resolve() or spec.get("digest") != LO._digest(spec):
        raise ValueError("CLOUD_ORDER_SPEC_CHANGED")
    context_arguments(spec)
    policy = LO.load_policy()
    if not CloudPlacer._policy_valid(policy):
        raise ValueError("CLOUD_POLICY_REQUIRED")
    grant = LO.verify_grant(policy, now=time.time())
    request = {"order_id": spec["wo"], "driver_class": spec.get("driver_class"), "model": spec.get("profile")}
    for action in ("submit_workorder", "launch_workorder", "recover_workorder"):
        if not grant.permit(action, request).allow:
            raise ValueError("CLOUD_AUTHORIZATION_REFUSED")
    cdir = Path(policy.get("campaigns_dir"))
    if not cdir.is_absolute():
        from ..common import REPO_ROOT
        cdir = REPO_ROOT / cdir
    approved, _ = campaigns.load_all(cdir, line="cloud")
    camp = next((c for c in approved if c.campaign_id == spec.get("campaign_id")
                 and c.sha256 == spec.get("campaign_sha256") and c.commit == spec.get("campaign_commit")), None)
    lineage = next((entry for entry in camp.lineages if entry.key == spec.get("lineage")
                    and entry.sha256 == spec.get("lineage_sha")), None) if camp else None
    if lineage is None or lineage.profile != PROFILE or spec.get("run_model") != "gpt-6.1-terra":
        raise ValueError("CLOUD_CAMPAIGN_CHANGED")
    from . import line_launcher as LL
    if LL.resolve_rev(cfg.repo, lineage.factory_revision) != spec.get("revision"):
        raise ValueError("CLOUD_REVISION_CHANGED")
    db = LO.supervisor_dir() / "line-queue.sqlite3"
    if not db.is_file() or db.is_symlink():
        raise ValueError("CLOUD_ADMITTED_QUEUE_REQUIRED")
    store = Store(db, must_exist=True)
    rows = LO._queue_rows(db)
    row = rows.get(spec["wo"])
    if not row or row["state"] != "ADMITTED":
        raise ValueError("CLOUD_ADMITTED_ORDER_REQUIRED")
    attempts = store.attempts(row["order_id"])
    if not attempts or attempts[-1]["state"] != "DISPATCH_PENDING":
        raise ValueError("CLOUD_PENDING_DISPATCH_REQUIRED")
    if (row["envelope"].get("payload_digest") != spec["digest"]
            or row["envelope"].get("authorization_ref") != grant.authorization_id):
        raise ValueError("CLOUD_QUEUE_BINDING_CHANGED")
    if spec.get("quality_via") == "FLAG":
        q = LO.supervisor_dir() / "line-orders" / f"{spec['wo']}.quality.json"
        if q.is_symlink() or spec.get("quality_file") != str(q) or LO._load(q) != spec.get("quality"):
            raise ValueError("CLOUD_QUALITY_BINDING_CHANGED")
    elif spec.get("quality_file") is not None:
        raise ValueError("CLOUD_QUALITY_BINDING_CHANGED")
    return spec


def launch(path, *, line=None, run=subprocess.run):
    """Serialize admission, retain uncertain dispatches, and never restart the shared server."""
    from . import line_launcher as LL
    line = line or CloudLine()
    cfg = line.cfg
    spec = _authorized_spec(path, cfg)
    order = LL.Order(wo=spec["wo"], rev=spec["revision"], example=spec["example"], profile=spec["profile"],
                     model=spec["run_model"], purpose=spec["purpose"], stop_after=spec["stop_after"],
                     resume_from=spec.get("resume_from"), provided_from=spec.get("provided_from"),
                     resume_upto=spec.get("resume_upto"), quality_file=spec.get("quality_file"))
    order.validate()
    cfg.launch_dir.mkdir(parents=True, exist_ok=True)
    with (cfg.launch_dir / "cloud-dispatch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = _authorized_spec(path, cfg)  # authority may have expired while acquiring the lock
        if current != spec:
            raise ValueError("CLOUD_ORDER_SPEC_CHANGED")
        live = line.live_runs()
        if live is None or len(live) >= CAPACITY:
            raise ValueError("CLOUD_CAPACITY_UNAVAILABLE")
        ws = line.workspace(order.wo)
        if ws.exists():
            raise ValueError("CLOUD_ORDER_ALREADY_PREPARED")
        transcript = cfg.runs_root / ".launch" / order.wo / "attempt-1.json"
        if transcript.exists():
            raise ValueError("CLOUD_DISPATCH_ALREADY_ATTEMPTED")
        # A shared stack is already running. All source preparation is private
        # to this order; there is no stop/start/swap/sweep operation here.
        wt, _ = LL.ensure_worktree(cfg, order, order.rev)
        reader = LL.RevReader(cfg.repo, order.rev)
        import yaml
        validate_profile(yaml.safe_load(reader.read(f"config/factory/profiles/{PROFILE}.yaml") or b"{}"))
        rework_args = context_arguments(spec)
        consumer = reader.read("factory/python/forge_factory/workorder.py") or b""
        required = ["--rework-from"]
        if (spec.get("rework_context") or {}).get("source_phase"):
            required += ["--rework-source-phase", "--rework-upstream-sha256"]
        if rework_args and any(flag.encode() not in consumer for flag in required):
            raise ValueError("CLOUD_REWORK_NOT_SUPPORTED_AT_REVISION")
        inputs = LL.plan_inputs(reader, order.example, cfg, wt)
        LL.provision_inputs(inputs, wt, cfg.inputs_cache)
        env = LL.run_env(cfg, wt, order.profile)
        command = [str(cfg.python), "-m", "forge_factory.lrtx.stack", "exec", "--", str(cfg.python),
                   "-m", "forge_factory.workorder", *order.workorder_args(), *rework_args]
        log = cfg.launch_dir / f"cloud-submit-{order.wo}.out"
        record = {"attempt": 1, "work_order": order.wo, "revision": order.rev, "started_at": LO._utc(time.time()),
                  "outcome": "CLOUD_DISPATCH_UNCERTAIN", "class": "REFUSED"}
        LO._atomic(transcript, record)  # persisted before any possible native submit
        with log.open("ab") as out:
            try:
                proc = run(command, cwd=wt / "factory/python", env=env, stdin=subprocess.DEVNULL,
                           stdout=out, stderr=subprocess.STDOUT, timeout=600)
            except (subprocess.TimeoutExpired, OSError):
                return {"outcome": "CLOUD_DISPATCH_UNCERTAIN", "work_order": order.wo}
        # Factory-owned binding is authoritative; transport output alone cannot
        # prove that the expected workspace and native run were created.
        manifest = LO._load(ws / ".forge-run/manifest.json") or {}
        rid_path = ws / ".forge-run/fabro_run_id"
        rid = rid_path.read_text().strip() if rid_path.is_file() else None
        if proc.returncode or manifest.get("work_order") != order.wo or not rid:
            return {"outcome": "CLOUD_DISPATCH_UNCERTAIN", "work_order": order.wo}
        try:
            native = line.host.fabro_run(rid)
        except LL.FabroUnavailable:
            return {"outcome": "CLOUD_DISPATCH_UNCERTAIN", "work_order": order.wo}
        if native.get("id") != rid or native.get("source_directory") != str(ws):
            return {"outcome": "CLOUD_DISPATCH_UNCERTAIN", "work_order": order.wo}
        record.update(outcome="LAUNCHED", fabro_run_id=rid, ended_at=LO._utc(time.time()))
        LO._atomic(transcript, record)
        return {"outcome": "LAUNCHED", "fabro_run_id": rid, "work_order": order.wo}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["launch"])
    parser.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    try:
        outcome = launch(args.spec)
    except (ValueError, OSError) as exc:
        outcome = {"outcome": "REFUSED", "code": getattr(exc, "code", str(exc))[:160]}
    print(json.dumps(outcome))
    return 0 if outcome["outcome"] == "LAUNCHED" else 2


class CloudRecords(LO.Records):
    def attempt(self, wo, phase, n):
        attempt = super().attempt(wo, phase, n)
        if not attempt.rid and any(t.get("outcome") == "CLOUD_DISPATCH_UNCERTAIN"
                                   for t in self.line.transcripts(wo)):
            # An expired launcher observation is not proof that native submit
            # failed. Keep its slot and lineage pending without another launch.
            attempt.status, attempt.launching = "LAUNCHING", True
        return attempt

    def phase_attempts(self, lineage, phase):
        # The manual cloud ladders started some phases at D/E. The local dense
        # naming heuristic would miss those attempts and lose their strike and
        # last-good history. Discover exact names instead of inventing new series.
        prefix = lineage.wo(phase, 1)
        names = set(self.queue_rows)
        launch_root = self.line.run_worktree(prefix).parent / ".launch"
        for root, suffix in ((self.line.state_root / "workorders", ""), (self.orders_dir, ".json"),
                             (launch_root, "")):
            if root.is_dir():
                names.update(p.name.removesuffix(suffix) if suffix else p.name for p in root.iterdir())
        names.update(self.legacy)
        found = []
        for name in names:
            tail = name.removeprefix(prefix)
            if not name.startswith(prefix) or (tail and not re.fullmatch(r"[A-Z]+", tail)):
                continue
            n = 0
            for ch in tail:
                n = n * 26 + ord(ch) - ord("A") + 1
            n = n or 1
            if lineage.wo(phase, n) == name and self.exists(name):
                found.append(self.attempt(name, phase, n))
        return sorted(found, key=lambda a: a.n)


class CloudPlacer(LO.Placer):
    def __init__(self, line, *, policy_path, **kwargs):
        if kwargs.pop("line_id", "cloud") != "cloud":
            raise ValueError("CLOUD_LINE_ID_REQUIRED")
        super().__init__(line, line_id="cloud", policy_path=policy_path, **kwargs)

    def _records(self, now, capa_of):
        return CloudRecords(self.line, self.queue_path, now, capa_of)

    @staticmethod
    def _policy_valid(policy):
        return (not policy.issues and policy.get("line") == "cloud"
                and policy.get("pacing.max_concurrent_cloud_runs") == CAPACITY
                and policy.get("models") == PROFILE)

    def cycle(self, now=None):
        policy = LO.load_policy(self.policy_path)
        if not self._policy_valid(policy):
            return {"mode": "OBSERVING", "error": "CLOUD_POLICY_REQUIRED", "lineages": [], "actions": [],
                    "model_calls_healthy": 0, "policy_issues": policy.issues}
        return super().cycle(now)

    def _admission_capacity(self, policy):
        if not self._policy_valid(policy):
            raise ValueError("CLOUD_POLICY_REQUIRED")
        return CAPACITY

    def _gpu(self, plans):
        # A transient API failure is busy, never a reason to relaunch. Include
        # work not enumerated in the campaign before claiming a free slot.
        live = self.line.live_runs()
        if live is None:
            return {"busy": True, "reason": "FABRO_API_UNREACHABLE", "wo": None}
        running = [p for p in plans if p.state in ("RUNNING", "LAUNCHING")]
        known = {p.current.rid for p in running if p.current and p.current.rid}
        unknown = set(live) - known
        if unknown:
            return {"busy": True, "reason": "RUN_LIVE_NOT_IN_CAMPAIGN", "wo": None}
        used = max(len(running), len(live))
        return {"busy": used >= CAPACITY, "reason": "CLOUD_CAPACITY" if used >= CAPACITY else None,
                "wo": None, "used": used, "capacity": CAPACITY}

    def _requests(self, plan):
        # Account-backed cloud orders share an already running server. They do
        # not request local model swaps, a GPU lock, stack restarts or orphan kills.
        req = {"order_id": plan.order["wo"], "driver_class": plan.lineage.driver_class, "model": plan.lineage.profile}
        result = [("launch_workorder", req)]
        if plan.action == "PLACE":
            result.insert(0, ("submit_workorder", req))
        if plan.order["kind"] in LO.RETRY_KINDS:
            result.append(("recover_workorder", req))
        return result

    def _execute(self, plan, policy, grant, campaigns, now, *, execute):
        if plan.lineage.profile != PROFILE or plan.order.get("run_model") != "gpt-6.1-terra":
            return {"action": plan.action, "wo": plan.order["wo"], "outcome": "REFUSED",
                    "detail": "CLOUD_ROLE_PROFILE_REQUIRED"}
        if plan.sweep:
            return {"action": plan.action, "wo": plan.order["wo"], "outcome": "REFUSED",
                    "detail": "CLOUD_INFRA_RECOVERY_REQUIRES_OWNED_RECIPE"}
        if plan.order["kind"] in ("RETRY", "UPSTREAM"):
            try:
                previous_spec = getattr(plan.current, "spec", None) or {}
                retained = plan.order.get("rework_context")
                if retained is None and not getattr(plan.current, "rid", None):
                    retained = previous_spec.get("rework_context")
                if retained is not None:
                    if previous_spec and previous_spec.get("digest") != LO._digest(previous_spec):
                        raise ValueError("CLOUD_ORDER_SPEC_CHANGED")
                    context_arguments({**plan.order, "rework_context": retained})
                    plan.order["rework_context"] = retained
                else:
                    plan.order["rework_context"] = failed_context(self.line, plan)
            except (OSError, ValueError) as exc:
                return {"action": plan.action, "wo": plan.order["wo"], "outcome": "REFUSED",
                        "detail": str(exc)[:160]}
        return super()._execute(plan, policy, grant, campaigns, now, execute=execute)


if __name__ == "__main__":
    raise SystemExit(main())
