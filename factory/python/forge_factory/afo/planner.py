"""AFO-T038 (AFO-FR-041/048; AT-030/036) - the afo-recovery-planner case and its typed, bounded output parser.

`case(...)` freezes one recovery case (bundle, workspace, requirements hash, budget, allowed strategies) under
<state>/afo/cases/<bundle_id>/ for forge-afo-mcp. `parse(reply, case_dir)` accepts only the compact agent-output JSON
(002 contract) whose `recovery_plan_ref` names the plan the broker stored for THIS case; anything else - prose,
malformed JSON, a plan for another case, a schema violation - yields None (no plan), never a partial plan. The plan is
still only PROPOSED: recovery.validate decides. `make(invoke)` adapts a planner runner (a Fabro single-node run of the
role, enabled by policy engineering.enable_recovery_planner) to recovery.decide.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_file, state_dir
from . import contracts

ALLOWED = ["REWORK_LOCAL", "RESTART_FROM_LAST_VALID_CHECKPOINT", "RETURN_TO_OWNING_UPSTREAM_PHASE",
           "SWITCH_PREAPPROVED_MODEL_PROFILE", "CLOSE_BLOCKED"]
MAX_REPLY = 2000


class Pending(Exception):
    """A durable planner run is in progress; keep the order under recovery supervision."""


class Failed(Exception):
    """Diagnosis itself failed; preserve its reason instead of claiming no different strategy exists."""


def case(bundle: dict, workspace: Path, budget: dict) -> Path:
    d = state_dir() / "afo/cases" / bundle["bundle_id"]
    d.mkdir(parents=True, exist_ok=True)
    req = Path(workspace) / "workproducts/SWE.1/software_requirements.md"
    p = d / "case.json"
    doc = {"bundle": bundle, "workspace": str(workspace),
                             "requirements_sha256": sha256_file(req) if req.is_file() else None,
                             "budget": budget, "allowed_strategies": ALLOWED}
    if not p.exists():
        with p.open("x") as f:
            f.write(json.dumps(doc, sort_keys=True))
        p.chmod(0o400)
    else:
        old = json.loads(p.read_text())
        if any(old.get(k) != doc[k] for k in ("bundle", "workspace", "requirements_sha256")):
            raise ValueError("FROZEN_RECOVERY_CASE_CHANGED")
    return p


def parse(reply: str, case_dir: Path) -> dict | None:
    if not isinstance(reply, str) or len(reply) > MAX_REPLY:
        return None
    m = re.fullmatch(r"\s*(\{.*\})\s*", reply, re.S)  # the reply is ONLY the JSON object (no prose around it)
    if not m:
        return None
    try:
        out = json.loads(m.group(1))
    except ValueError:
        return None
    refs = [x for x in out.get("artifacts", []) if isinstance(x, str) and x.startswith("afo-plan:")]
    ref = str(out.get("recovery_plan_ref") or (refs[0] if len(refs) == 1 else ""))
    if out.get("status") not in ("PASS", "BLOCKED") or not ref.startswith("afo-plan:"):
        return None
    p = Path(case_dir) / "proposed-plan.json"
    try:
        plan = json.loads(p.read_text())
        case_doc = json.loads((Path(case_dir) / "case.json").read_text())
    except (OSError, ValueError):
        return None
    if plan.get("plan_id") != ref.split(":", 1)[1] or contracts.errors("recovery-plan", plan):
        return None
    b = case_doc["bundle"]
    if plan.get("order_id") != b["order_id"] or plan.get("attempt_id") != b["attempt_id"]:
        return None
    return plan


def make(invoke):
    """recovery.decide planner hook: freeze the case, run the planner (`invoke(case_path) -> reply text`), parse."""
    def planner(bundle: dict, budget: dict, workspace: Path | None = None) -> dict | None:
        try:
            p = case(bundle, workspace or Path("."), budget)
            reply = invoke(p)
        except (Pending, Failed):
            raise
        except Exception as exc:  # noqa: BLE001 - an explicit failed diagnosis, never a fabricated plan
            raise Failed(type(exc).__name__) from exc
        return parse(reply, p.parent)
    return planner
