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

ALLOWED = [
    "REWORK_LOCAL",
    "RESTART_FROM_LAST_VALID_CHECKPOINT",
    "RETURN_TO_OWNING_UPSTREAM_PHASE",
    "SWITCH_PREAPPROVED_MODEL_PROFILE",
    "CLOSE_BLOCKED",
]
MAX_REPLY = 2000


class Pending(Exception):
    """A durable planner run is in progress; keep the order under recovery supervision."""


class Failed(Exception):
    """Diagnosis itself failed; preserve its reason instead of claiming no different strategy exists."""


def case(bundle: dict, workspace: Path, budget: dict, *, mission_id: str | None = None, prior_strategies=()) -> Path:
    d = state_dir() / "afo/cases" / (bundle["bundle_id"] + ("-da014" if mission_id else ""))
    d.mkdir(parents=True, exist_ok=True)
    req = Path(workspace) / "workproducts/SWE.1/software_requirements.md"
    p = d / "case.json"
    doc = {
        "bundle": bundle,
        "workspace": str(workspace),
        "requirements_sha256": sha256_file(req) if req.is_file() else None,
        "budget": budget,
        "allowed_strategies": ALLOWED,
    }
    if mission_id:
        from .diagnosis_packet import build
        from .durable import immutable_json

        doc.update(mission_id=mission_id, packet_ref=build(workspace, bundle, prior_strategies=prior_strategies))
        if p.is_file():
            # Polls observe a changing remaining budget; they must adopt the
            # original case allowance, never rewrite or replenish it.
            old = json.loads(p.read_text())
            if {k: v for k, v in old.items() if k != "budget"} != {k: v for k, v in doc.items() if k != "budget"}:
                raise ValueError("FROZEN_RECOVERY_CASE_CHANGED")
            return p
        immutable_json(p, doc)
        return p
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


PENDING = "PENDING"


def make(invoke, *, freeze=None):
    """recovery.decide planner hook: freeze the case, run the planner (`invoke(case_path)` -> reply text, None, or
    PENDING while an asynchronous Fabro run is still going - planner_run), parse.

    Pending and Failed are explicit outcomes and always propagate (Feature 014 local agent). Without `freeze` the case
    is frozen once and later conductor cycles poll the same case (Feature 015 planner_run), and a failed run proposes
    nothing; with the local agent's `freeze`, any other error is an explicit failed diagnosis, never a fabricated plan."""

    def planner(bundle: dict, budget: dict, workspace: Path | None = None) -> dict | str | None:
        try:
            if freeze is not None:
                p = freeze(bundle, workspace or Path("."), budget)
            else:
                p = state_dir() / "afo/cases" / bundle["bundle_id"] / "case.json"
                if not p.is_file():  # frozen once (read-only)
                    p = case(bundle, workspace or Path("."), budget)
            reply = invoke(p)
        except (Pending, Failed):
            raise
        except Exception as exc:  # noqa: BLE001
            if freeze is not None:
                raise Failed(str(getattr(exc, "code", type(exc).__name__))) from exc
            return None
        if reply == PENDING:
            return PENDING
        return parse(reply, p.parent) if reply is not None else None
    return planner
