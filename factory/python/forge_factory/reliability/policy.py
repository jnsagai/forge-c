"""CRE-T004 — versioned reliability policy: schema + hard invariants that no edit can weaken.

* Structural contract: specs/004-continuous-reliability-engineering/contracts/reliability-policy.schema.json.
* Hard invariants (INV-01, INV-05, INV-06, INV-08, INV-09): auto code promotion, AI safety approval, safety-rule
  mutation, oracle edits, model calls on healthy polls, "unknown is success" etc. have exactly one permitted value.
* Mandatory floors: the non-replayable operation classes, the protected path globs and the audit capture level are
  supersets/minimums - a policy may add to them, never remove.
* CRE budgets must not exceed the authoritative 002 supervisor-policy repair budgets (no second, looser budget).
* PILOT/ACTIVE need an `authorization` block (runbook, approver, date); automatic operational actions are allowed
  only in ACTIVE and only from the reversible catalogue. OBSERVE_ONLY is the default.
* Live reload keeps the last good policy when an edit is invalid; every accept/reject is an audit event.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common import CONFIG_DIR, REPO_ROOT, canonical_json, load_yaml, sha256_bytes

CRE_CONTRACTS_DIR = REPO_ROOT / "specs" / "004-continuous-reliability-engineering" / "contracts"
POLICY_PATH = CONFIG_DIR / "reliability-policy.yaml"
SUPERVISOR_POLICY = CONFIG_DIR / "supervisor-policy.yaml"

HARD_INVARIANTS: dict[str, Any] = {
    "integration.reuse_existing_supervisor": True,
    "integration.reuse_existing_incident_store": True,
    "integration.reuse_existing_kpi_catalog": True,
    "integration.do_not_create_parallel_control_plane": True,
    "supervisor.invoke_model_on_healthy_poll": False,
    "supervisor.health_unknown_is_healthy": False,
    "recovery.retry_only_idempotent_operations": True,
    "recovery.fail_closed_on_unknown_side_effect": True,
    "capa.root_cause_requires_reproduction": True,
    "capa.preventive_regression_required": True,
    "promotion.auto_promote_persistent_code": False,
    "promotion.allow_auto_mutation_of_safety_rules": False,
    "promotion.forbid_test_oracle_edits": True,
    "promotion.require_independent_runner": True,
    "promotion.require_frozen_baseline": True,
    "promotion.require_reproducer_and_regression": True,
    "promotion.require_security_and_policy_integrity": True,
    "promotion.require_authorized_offline_change_control": True,
    "benchmark.freeze_fixture_manifest": True,
    "benchmark.keep_holdout_outside_candidate_permissions": True,
    "benchmark.include_failed_first_attempts": True,
    "benchmark.include_all_retry_tokens_in_cost": True,
    "statistics.unknown_is_success": False,
    "statistics.baseline_measurement_only": True,
    "security.deny_agent_direct_shell": True,
    "security.deny_agent_editing_gate_results": True,
    "security.redact_secrets_before_persistence": True,
    "telemetry.preserve_existing_capture_view_separation": True,
    "telemetry.raw_logs_outside_model_context": True,
    "readiness.offline_safety_signoff_required": True,
    "readiness.safety_approval_by_ai": False,
    "readiness.block_missing_p0_evidence": True,
}
MANDATORY_NON_REPLAYABLE = {"hardware_flash", "safety_approval", "baselined_evidence_mutation", "release_signing"}
MANDATORY_PROTECTED = {
    ".specify/memory/constitution.md",
    "config/factory/*safety*",
    "config/factory/*release*",
    "config/factory/reliability-policy.yaml",
    "evidence/**",
    "specs/001-factory/**",
    "specs/002-self-healing-factory/**",
    "specs/003-manufacturing-kpis/**",
    "specs/004-continuous-reliability-engineering/contracts/**",
    "tests/reliability/**",
    "factory/checklists/**",
    "factory/release-manager/**",
}
LEVEL_RANK = {"OFF": 0, "ERROR": 1, "WARN": 2, "INFO": 3, "DEBUG": 4, "TRACE": 5}
# Reversible, pre-authorizable operational actions (ACTIVE only). Persistent code promotion is never in this list.
REVERSIBLE_ACTIONS = {
    "restart_dashboard",
    "restart_mcp_server",
    "restart_llm_gateway",
    "drain_queue",
    "restart_collector",
    "restart_conductor",
    "restart_local_stack",
}


class PolicyInvalid(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues[:8]))
        self.issues = issues


def _get(d: dict, dotted: str) -> Any:
    cur: Any = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return KeyError
        cur = cur[k]
    return cur


def schema() -> dict:
    return json.loads((CRE_CONTRACTS_DIR / "reliability-policy.schema.json").read_text(encoding="utf-8"))


def issues_of(pol: Any, supervisor_policy: dict | None = None) -> list[str]:
    """Every reason this policy is not acceptable (empty list = valid). Deterministic, model-free."""
    from jsonschema import Draft202012Validator

    if not isinstance(pol, dict):
        return ["POLICY_NOT_A_MAPPING"]
    out = [
        f"SCHEMA:{'/'.join(map(str, e.path)) or '<root>'}:{e.message}"[:200]
        for e in Draft202012Validator(schema()).iter_errors(pol)
    ]
    for path, want in HARD_INVARIANTS.items():
        got = _get(pol, path)
        if got is not KeyError and got != want:
            out.append(f"HARD_INVARIANT_WEAKENED:{path}={got!r} (required {want!r})")
    rec = pol.get("recovery") or {}
    missing = MANDATORY_NON_REPLAYABLE - set(rec.get("non_replayable_operation_classes") or [])
    if missing:
        out.append(f"NON_REPLAYABLE_FLOOR_REMOVED:{','.join(sorted(missing))}")
    if (
        isinstance(rec.get("initial_backoff_seconds"), (int, float))
        and isinstance(rec.get("max_backoff_seconds"), (int, float))
        and rec["initial_backoff_seconds"] > rec["max_backoff_seconds"]
    ):
        out.append("BACKOFF_INITIAL_EXCEEDS_MAX")
    sec = pol.get("security") or {}
    gone = MANDATORY_PROTECTED - set(sec.get("protected_path_globs") or [])
    if gone:
        out.append(f"PROTECTED_PATH_FLOOR_REMOVED:{','.join(sorted(gone))}")
    lvl = sec.get("audit_channel_min_level")
    if lvl in LEVEL_RANK and LEVEL_RANK[lvl] < LEVEL_RANK["INFO"]:
        out.append(f"AUDIT_CAPTURE_WEAKENED:{lvl}")
    mode = pol.get("mode")
    auth = pol.get("authorization")
    if mode in ("PILOT", "ACTIVE") and not auth:
        out.append(f"MODE_{mode}_REQUIRES_AUTHORIZATION")
    if isinstance(auth, dict) and any(
        "TODO" in str(v).upper() or "PLACEHOLDER" in str(v).upper() or "<" in str(v) for v in auth.values()
    ):
        out.append("AUTHORIZATION_PLACEHOLDER")
    actions = set((pol.get("promotion") or {}).get("allowed_automatic_operational_actions") or [])
    if actions and mode != "ACTIVE":
        out.append("AUTOMATIC_ACTIONS_REQUIRE_ACTIVE_MODE")
    if actions - REVERSIBLE_ACTIONS:
        out.append(f"ACTION_NOT_REVERSIBLE_CATALOGUE:{','.join(sorted(actions - REVERSIBLE_ACTIONS))}")
    sup = (
        supervisor_policy
        if supervisor_policy is not None
        else (load_yaml(SUPERVISOR_POLICY) if SUPERVISOR_POLICY.is_file() else {})
    )
    rep = (sup or {}).get("repair") or {}
    for mine, theirs in (
        ("max_repair_attempts_per_incident", "max_attempts_per_incident"),
        ("max_repairs_per_hour", "max_attempts_per_hour"),
    ):
        if isinstance(rec.get(mine), int) and isinstance(rep.get(theirs), int) and rec[mine] > rep[theirs]:
            out.append(f"EXCEEDS_SUPERVISOR_BUDGET:recovery.{mine}={rec[mine]}>{rep[theirs]}")
    return out


@dataclass(frozen=True)
class Policy:
    data: dict
    sha256: str
    path: str

    @property
    def mode(self) -> str:
        return self.data["mode"]

    def get(self, dotted: str) -> Any:
        v = _get(self.data, dotted)
        if v is KeyError:
            raise KeyError(dotted)
        return v

    def automatic_action_allowed(self, action: str) -> bool:
        """Only reversible, pre-authorized operational actions in ACTIVE mode; never persistent code."""
        return self.mode == "ACTIVE" and action in set(self.get("promotion.allowed_automatic_operational_actions"))


def load(path: Path | None = None, supervisor_policy: dict | None = None) -> Policy:
    p = path or POLICY_PATH
    data = load_yaml(p)
    errs = issues_of(data, supervisor_policy)
    if errs:
        raise PolicyInvalid(errs)
    return Policy(data=data, sha256=sha256_bytes(canonical_json(data)), path=str(p))


class PolicyHolder:
    """Live reload by mtime; an invalid edit is rejected (audit event) and the last good policy stays active."""

    def __init__(self, path: Path | None = None):
        self.path = path or POLICY_PATH
        self.policy = load(self.path)
        self.mtime = self.path.stat().st_mtime
        self.rejections: list[list[str]] = []

    def current(self) -> Policy:
        from ..events.emit import emit

        try:
            m = self.path.stat().st_mtime
        except OSError:
            return self.policy
        if m != self.mtime:
            self.mtime = m
            try:
                self.policy = load(self.path)
                emit("audit", "INFO", f"cre policy reloaded sha256={self.policy.sha256[:12]} mode={self.policy.mode}")
            except (PolicyInvalid, OSError, ValueError) as exc:
                issues = exc.issues if isinstance(exc, PolicyInvalid) else [str(exc)[:160]]
                self.rejections.append(issues)
                emit(
                    "audit", "WARN", f"cre policy edit rejected ({len(issues)} issues); last good policy kept: {issues[0][:120]}"
                )
        return self.policy
