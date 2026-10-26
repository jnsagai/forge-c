"""AFO M4 (T037, T039-T043; AFO-FR-040..048; AT-023/028/029/031..036) - deterministic recovery decisions.

Order of authority for a blocked attempt (a FailureBundle):
  1. class routes that need no plan: INFRASTRUCTURE / TRANSIENT_DEPENDENCY -> DEFER (002 supervisor + CRE own the
     repair; AFO only retries after them, bounded); SPECIFICATION_GAP / SECURITY / UNKNOWN -> CLOSE_BLOCKED;
     FACTORY_CODE_DEFECT -> WAITING_EXTERNAL_CHANGE (a source change is the maintainer/CAPA path, M5).
  2. PRODUCT_QUALITY, deterministic rules first (no model call when a rule applies):
       a. an OPEN upstream defect the blocked phase reported -> RETURN_TO_OWNING_UPSTREAM_PHASE (owner = target);
       b. a lesson VALIDATED after the failed attempt started and matching the failure -> REWORK_LOCAL + lesson ids;
       c. a pre-approved model profile not yet used on this order -> SWITCH_PREAPPROVED_MODEL_PROFILE;
       d. only then the afo-recovery-planner (if enabled by policy) proposes a plan;
       e. otherwise CLOSE_BLOCKED - no materially different strategy exists.
  3. Every plan, rule-made or proposed, passes `validate`: schema; strategy legal for the class; model profile
     pre-approved by policy AND by the signed authorization's scope; artifact scope inside the owning phase's paths
     and never a protected path; no gate/threshold/policy/oracle-weakening wording; budgets (attempts, variants per
     phase, planner calls, wall time) left; and a plan fingerprint never used before on this order (anti-loop - a
     plan that only reworded or reseeded the same thing has the same fingerprint and is refused).
Plans are recorded (afo_recovery_plans) with the decision; execution always opens a NEW attempt (checkpoints).
A DEFER_TRANSIENT_DEPENDENCY retry is numbered (its own fingerprint), bounded by budgets.max_retries_per_transient_
operation and launched only after TRANSIENT_BACKOFF_SECONDS x its number; it is not a strategy variant (F015: Codex
refused every turn 2026-10-25 23:03 to at least 03:42; the orders were dead-lettered instead of retried).
"""
from __future__ import annotations

import hashlib
import json
import re
import time

from ..common import canonical_json, utc_now
from . import contracts
from .queue import QueueError, Store

PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
STRATEGIES_FOR = {
    "PRODUCT_QUALITY": {"REWORK_LOCAL", "RESTART_FROM_LAST_VALID_CHECKPOINT", "RETURN_TO_OWNING_UPSTREAM_PHASE",
                        "SWITCH_PREAPPROVED_MODEL_PROFILE", "CLOSE_BLOCKED"},
    "INFRASTRUCTURE": {"DEFER_TRANSIENT_DEPENDENCY", "CLOSE_BLOCKED"},
    "TRANSIENT_DEPENDENCY": {"DEFER_TRANSIENT_DEPENDENCY", "CLOSE_BLOCKED"},
    "FACTORY_CODE_DEFECT": {"CLOSE_BLOCKED"}, "SPECIFICATION_GAP": {"CLOSE_BLOCKED"}, "SECURITY": {"CLOSE_BLOCKED"},
    "UNKNOWN": {"CLOSE_BLOCKED"},
}
PROTECTED = re.compile(r"^(tests/reliability|evidence|config/factory|factory/release-manager|factory/checklists|"
                       r"\.specify|specs|inputs|configuration/baselines|inspection)(/|$)|CLAUDE\.md$")
DENY = re.compile(r"(?i)\b(disable|skip|bypass|weaken|relax|lower|raise)\b.{0,40}\b(gate|threshold|check|inspection|"
                  r"policy|oracle|holdout|coverage|requirement)s?\b|\bauto[_ -]?merge\b|\bforce[_ -]?push\b")
# one new attempt: the factory's own per-run bounds (author max_turns, run timeout); real token use is reported by
# DeepSeek runs and UNKNOWN for Codex/ACP runs - an estimate, never read as consumption
ATTEMPT_ESTIMATE = {"tokens_max": 120000, "wall_seconds_max": 21600, "turns_max": 35}
TRANSIENT_BACKOFF_SECONDS = 900
MIGRATION = """
CREATE TABLE IF NOT EXISTS afo_recovery_plans (
  plan_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, attempt_id TEXT NOT NULL, failure_fingerprint TEXT NOT NULL,
  strategy TEXT NOT NULL, plan_fingerprint TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
  reasons TEXT NOT NULL, record TEXT NOT NULL, budget_snapshot TEXT NOT NULL, decided_utc TEXT NOT NULL,
  UNIQUE (order_id, plan_fingerprint))
"""


def _ensure(store: Store) -> None:
    with store.tx() as c:
        c.execute(MIGRATION)


def plan_fingerprint(p: dict) -> str:
    return hashlib.sha256(canonical_json({k: p.get(k) for k in ("strategy", "affected_phase", "owner_phase",
                                                                "model_profile", "material_difference_ref")}
                                         | {"scope": sorted(p.get("artifact_scope") or []),
                                            "lessons": sorted(p.get("lesson_ids") or [])})).hexdigest()


def plans(store: Store, order_id: str) -> list[dict]:
    _ensure(store)
    with store.tx() as c:
        return [{**dict(r), "record": json.loads(r["record"])} for r in
                c.execute("SELECT * FROM afo_recovery_plans WHERE order_id=? ORDER BY decided_utc", (order_id,))]


def budget_snapshot(store: Store, order: dict, eff, now: float | None = None) -> dict:
    ps = plans(store, order["order_id"])
    return {"attempts": len(store.attempts(order["order_id"])), "max_attempts": int(eff.get("budgets.max_order_attempts")),
            "variants_by_phase": {ph: sum(1 for p in ps if p["record"]["affected_phase"] == ph and p["status"] != "REJECTED"
                                          and p["strategy"] != "DEFER_TRANSIENT_DEPENDENCY") for ph in PHASES},
            "transient_retries": sum(1 for p in ps if p["strategy"] == "DEFER_TRANSIENT_DEPENDENCY"
                                     and p["status"] == "EXECUTED"),
            "max_transient_retries": int(eff.get("budgets.max_retries_per_transient_operation") or 0),
            "max_variants_per_phase": int(eff.get("budgets.max_strategy_variants_per_phase")),
            "planner_calls": sum(1 for p in ps if p["source"] == "PLANNER"),
            "max_planner_calls": int(eff.get("budgets.max_recovery_model_calls_per_order")),
            "wall_seconds": round((now or time.time()) - order["created_epoch"], 1),
            "max_wall_seconds": int(eff.get("budgets.max_order_wall_seconds")),
            "tokens": "UNKNOWN (ACP/Codex usage is not reported to the factory; never read as zero)"}


def _base(bundle: dict, strategy: str, phase: str, rationale: str, **kw) -> dict:
    p = {"schema_version": "1.0", "order_id": bundle["order_id"], "attempt_id": bundle["attempt_id"],
         "failure_fingerprint": bundle["fingerprint"], "strategy": strategy, "affected_phase": phase,
         "material_difference_ref": kw.pop("material_difference_ref", f"strategy:{strategy}"),
         "artifact_scope": kw.pop("artifact_scope", []), "validation_tests": [f"gate:{phase}:route=PASS"],
         "budget_estimate": dict(ATTEMPT_ESTIMATE), "rationale_code": rationale, **kw}
    p["plan_id"] = "afo-plan-" + plan_fingerprint(p)[:16]
    return p


def _phase_paths(phase: str) -> list[str]:
    from ..inspection.engine import PHASE_PATHS

    return list(PHASE_PATHS.get(phase, []))


def rule_plan(bundle: dict, *, ws, order_env: dict, tried_models: set[str], eff, attempt_started_utc: str,
              allowed_models: list[str]) -> dict | None:
    cls, ph = bundle["failure_class"], bundle["phase"]
    if cls in ("INFRASTRUCTURE", "TRANSIENT_DEPENDENCY"):
        return _base(bundle, "DEFER_TRANSIENT_DEPENDENCY", ph, "DEPENDENCY_OWNED_BY_002_CRE")
    if cls == "FACTORY_CODE_DEFECT":
        return _base(bundle, "CLOSE_BLOCKED", ph, "FACTORY_DEFECT_NEEDS_EXTERNAL_CHANGE")
    if cls != "PRODUCT_QUALITY":
        return _base(bundle, "CLOSE_BLOCKED", ph, f"{cls}_NOT_RECOVERABLE_BY_AFO")
    from ..inspection import defects

    up = defects.open_from(ws, ph) if ws is not None else []
    if up:
        owner = min((d["target_phase"] for d in up), key=PHASES.index)
        return _base(bundle, "RETURN_TO_OWNING_UPSTREAM_PHASE", owner, "OPEN_UPSTREAM_DEFECT", owner_phase=owner,
                     artifact_scope=_phase_paths(owner), upstream_invalidation=list(PHASES[PHASES.index(owner) + 1:]),
                     material_difference_ref="defects:" + ",".join(sorted(d["id"] for d in up)))
    lessons = _new_lessons(bundle, attempt_started_utc)
    if lessons:
        return _base(bundle, "REWORK_LOCAL", ph, "LESSON_VALIDATED_AFTER_ATTEMPT", lesson_ids=lessons,
                     artifact_scope=_phase_paths(ph), material_difference_ref="lessons:" + ",".join(lessons))
    for m in allowed_models:
        if m not in tried_models:
            return _base(bundle, "SWITCH_PREAPPROVED_MODEL_PROFILE", ph, "UNTRIED_PREAPPROVED_MODEL", model_profile=m,
                         artifact_scope=_phase_paths(ph), material_difference_ref=f"model:{m}")
    return None


def _new_lessons(bundle: dict, since_utc: str) -> list[str]:
    try:
        from ..knowledge.store import LessonStore

        out = LessonStore().find(bundle["error_code"], bundle["attempt_id"], None, bundle["phase"], 3)
    except Exception:  # noqa: BLE001 - no lesson store: no lesson rule
        return []
    return sorted(x["lesson_id"] for x in out.get("lessons", []) if str(x.get("validated_at", "")) > since_utc)


def validate(plan: dict, bundle: dict, *, store: Store, order: dict, eff, auth_models: list[str] | None) -> list[str]:
    issues = contracts.errors("recovery-plan", plan)
    if issues:
        return issues
    if plan["strategy"] not in STRATEGIES_FOR.get(bundle["failure_class"], set()):
        issues.append(f"STRATEGY_NOT_LEGAL_FOR_CLASS:{plan['strategy']}:{bundle['failure_class']}")
    m = plan.get("model_profile")
    if plan["strategy"] == "SWITCH_PREAPPROVED_MODEL_PROFILE" and not m:  # F015 planner trial: a "switch" naming no
        issues.append("MODEL_PROFILE_REQUIRED")                          # model would rerun the same one
    if m and (m not in (eff.get("engineering.allowed_model_profiles") or []) or
              (auth_models is not None and auth_models and m not in auth_models)):
        issues.append(f"MODEL_NOT_PREAPPROVED:{m}")
    owner = plan.get("owner_phase") or plan["affected_phase"]
    allowed = _phase_paths(owner)
    for path in plan.get("artifact_scope") or []:
        if PROTECTED.search(path):
            issues.append(f"PROTECTED_PATH:{path}")
        elif not any(path == a or path.startswith(a.rstrip("/") + "/") for a in allowed):
            issues.append(f"OUT_OF_OWNER_PHASE_SCOPE:{path}")
    text = " ".join(str(plan.get(k, "")) for k in ("notes", "rationale_code", "material_difference_ref"))
    if DENY.search(text):
        issues.append("PLAN_WEAKENS_A_GATE_OR_POLICY")
    if plan["strategy"] != "CLOSE_BLOCKED":
        b = budget_snapshot(store, order, eff)
        if b["attempts"] >= b["max_attempts"]:
            issues.append("BUDGET_ATTEMPTS_EXHAUSTED")
        if b["variants_by_phase"].get(plan["affected_phase"], 0) >= b["max_variants_per_phase"]:
            issues.append("BUDGET_VARIANTS_EXHAUSTED")
        if b["wall_seconds"] >= b["max_wall_seconds"]:
            issues.append("BUDGET_WALL_TIME_EXHAUSTED")
        fp = plan_fingerprint(plan)
        prior = plans(store, order["order_id"])
        if any(p["plan_fingerprint"] == fp for p in prior):
            issues.append("PLAN_ALREADY_TRIED")  # anti-loop: same plan, same fingerprint, never twice
        if plan["strategy"] == "DEFER_TRANSIENT_DEPENDENCY" and b["transient_retries"] >= b["max_transient_retries"]:
            issues.append("BUDGET_TRANSIENT_RETRIES_EXHAUSTED")
        if any(p["failure_fingerprint"] == bundle["fingerprint"] and p["strategy"] == plan["strategy"]
               and p["status"] == "EXECUTED" and plan["strategy"] not in ("SWITCH_PREAPPROVED_MODEL_PROFILE",
                                                                          "DEFER_TRANSIENT_DEPENDENCY") for p in prior):
            issues.append("SAME_FAILURE_SAME_STRATEGY_AGAIN")
    return issues


def record_plan(store: Store, plan: dict, *, source: str, status: str, reasons: list[str], budget: dict) -> None:
    _ensure(store)
    with store.tx() as c:
        c.execute("INSERT OR IGNORE INTO afo_recovery_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (plan["plan_id"], plan["order_id"], plan["attempt_id"], plan["failure_fingerprint"], plan["strategy"],
                   plan_fingerprint(plan), source, status, json.dumps(reasons), json.dumps(plan), json.dumps(budget),
                   utc_now()))
        store._event(c, f"plan_{status.lower()}", plan["order_id"], plan["attempt_id"],
                     {"plan_id": plan["plan_id"], "strategy": plan["strategy"], "reasons": reasons[:5]})


def decide(store: Store, order: dict, bundle: dict, *, ws, eff, auth_models: list[str] | None,
           planner=None) -> dict:
    """Choose and validate a plan for this blocked attempt. Returns {plan, status, reasons}."""
    env = json.loads(order["envelope"])
    atts = store.attempts(order["order_id"])
    tried = {env["model_profile"]} | {p["record"].get("model_profile") for p in plans(store, order["order_id"])
                                      if p["status"] == "EXECUTED" and p["record"].get("model_profile")}
    allowed = [m for m in (eff.get("engineering.allowed_model_profiles") or []) if not auth_models or m in auth_models]
    plan = rule_plan(bundle, ws=ws, order_env=env, tried_models=tried, eff=eff,
                     attempt_started_utc=atts[-1]["created_utc"] if atts else "", allowed_models=allowed)
    source = "RULE"
    if plan is not None and plan["strategy"] == "DEFER_TRANSIENT_DEPENDENCY":  # retry n+1: its own fingerprint
        n = budget_snapshot(store, order, eff)["transient_retries"] + 1
        plan = _base(bundle, plan["strategy"], plan["affected_phase"], plan["rationale_code"],
                     material_difference_ref=f"transient_retry:{n}")
    if plan is None and planner is not None and eff.get("engineering.enable_recovery_planner"):
        b = budget_snapshot(store, order, eff)
        if b["planner_calls"] < b["max_planner_calls"]:
            plan, source = planner(bundle, b, ws), "PLANNER"
            if plan == "PENDING":  # the planner run is asynchronous (planner_run): the Conductor polls again
                return {"plan": None, "status": "PENDING", "source": source, "reasons": []}
    if plan is None:
        plan = _base(bundle, "CLOSE_BLOCKED", bundle["phase"], "NO_MATERIALLY_DIFFERENT_STRATEGY")
    reasons = validate(plan, bundle, store=store, order=order, eff=eff, auth_models=auth_models)
    if reasons and plan["strategy"] != "CLOSE_BLOCKED":
        record_plan(store, plan, source=source, status="REJECTED", reasons=reasons,
                    budget=budget_snapshot(store, order, eff))
        plan = _base(bundle, "CLOSE_BLOCKED", bundle["phase"], "PLAN_REJECTED:" + reasons[0][:60])
        source, reasons = "RULE", []
    status = "VALIDATED" if not reasons else "REJECTED"
    record_plan(store, plan, source=source, status=status, reasons=reasons, budget=budget_snapshot(store, order, eff))
    return {"plan": plan, "status": status, "source": source, "reasons": reasons}


def execute(store: Store, order: dict, decision: dict, *, epoch: int, eff, previous_wo: str) -> dict:
    """Apply a VALIDATED plan: a new attempt (never a re-run of the old one), a wait, or BLOCKED."""
    from .checkpoints import new_attempt

    plan, oid = decision["plan"], order["order_id"]
    if plan["strategy"] == "CLOSE_BLOCKED":
        to = "WAITING_EXTERNAL_CHANGE" if plan["rationale_code"] == "FACTORY_DEFECT_NEEDS_EXTERNAL_CHANGE" else "BLOCKED"
        store.transition(oid, to, plan["rationale_code"], terminal_reason=plan["rationale_code"][:200])
        return {"order_id": oid, "action": to.lower()}
    store.transition(oid, "WAITING_RECOVERY", f"plan {plan['plan_id']} {plan['strategy']}")
    try:
        aid = new_attempt(store, oid, plan_id=plan["plan_id"], epoch=epoch,
                          max_attempts=int(eff.get("budgets.max_order_attempts")), source_wo=previous_wo)
    except QueueError as e:
        store.transition(oid, "BLOCKED", e.code, terminal_reason=e.code)
        return {"order_id": oid, "action": "blocked", "code": e.code}
    owner = plan.get("owner_phase") or plan["affected_phase"]
    with store.tx() as c:  # the launch payload carries what makes this attempt materially different
        row = c.execute("SELECT command_id, payload FROM afo_commands_outbox WHERE idempotency_key=?",
                        (f"launch:{aid}",)).fetchone()
        payload = {**json.loads(row["payload"]), "resume_upto": owner,
                   **({"model_profile": plan["model_profile"]} if plan.get("model_profile") else {}),
                   **({"lesson_ids": plan["lesson_ids"]} if plan.get("lesson_ids") else {})}
        c.execute("UPDATE afo_commands_outbox SET payload=? WHERE command_id=?", (json.dumps(payload), row["command_id"]))
        if plan["strategy"] == "DEFER_TRANSIENT_DEPENDENCY":  # give the dependency time to come back
            n = int(plan["material_difference_ref"].rsplit(":", 1)[-1])
            c.execute("UPDATE afo_commands_outbox SET retry_not_before_epoch=? WHERE command_id=?",
                      (time.time() + TRANSIENT_BACKOFF_SECONDS * n, row["command_id"]))
        c.execute("UPDATE afo_recovery_plans SET status='EXECUTED' WHERE plan_id=?", (plan["plan_id"],))
    return {"order_id": oid, "action": "new_attempt", "attempt_id": aid, "strategy": plan["strategy"]}


def poll_waiting(store: Store, recover) -> list[dict]:
    """WAITING_RECOVERY orders whose latest attempt already ended (a planner run in progress, not a prepared new
    attempt or a transient retry in backoff): ask `recover` again; it decides once the planner has replied."""
    out = []
    for o in store.orders(("WAITING_RECOVERY",)):
        att = (store.attempts(o["order_id"]) or [None])[-1]
        if att is not None and att["state"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            out.append({"order_id": o["order_id"], **(recover(o, att) or {"action": "no_bundle"})})
    return out


def make_recover(store: Store, eff, owner: str, workspace_of, planner=None):
    """Conductor hook for dispatch.reconcile_running: a terminal attempt whose SWE phase BLOCKED gets a bundle,
    a decision and its execution; an attempt that reached its package returns None (validation decides)."""
    from . import authz, bundle

    def recover(order: dict, attempt: dict) -> dict | None:
        ws = workspace_of(attempt)
        b = bundle.build(ws, order["order_id"], attempt["attempt_id"],
                         run_failed=attempt["state"] == "FAILED") if ws.is_dir() else None
        if b is None:
            return None
        auth = authz.find(eff.mode, eff.sha256 or "", ref=eff.get("authorization_ref"), action="recover_workorder")
        if not auth.allow:  # recovery itself needs the owner's authorization; without it the order is BLOCKED
            store.transition(order["order_id"], "BLOCKED", f"recovery not authorized: {auth.code}",
                             terminal_reason=f"RECOVERY_NOT_AUTHORIZED:{auth.code}")
            return {"action": "blocked", "code": auth.code}
        scope = json.loads((authz.AUTH_DIR / f"{eff.get('authorization_ref')}.json").read_text()).get("scope") or {}
        d = decide(store, order, b, ws=ws, eff=eff, auth_models=scope.get("models"), planner=planner)
        if d["status"] == "PENDING":
            store.transition(order["order_id"], "WAITING_RECOVERY", "recovery planner run in progress")
            return {"bundle_id": b["bundle_id"], "failure_class": b["failure_class"], "action": "planner_pending"}
        epoch = store.acquire_lease("scheduler", owner, float(eff.get("queue.lease_seconds", 120)))
        if epoch is None:
            return None
        prev = attempt["record"]["workspace_ref"].removeprefix("workorder:")
        return {"bundle_id": b["bundle_id"], "failure_class": b["failure_class"],
                **execute(store, order, d, epoch=epoch, eff=eff, previous_wo=prev)}
    return recover
