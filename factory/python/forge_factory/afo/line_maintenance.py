"""M7 line provenance into the existing isolated Maintainer case, without inference or source promotion.

Only a terminal attempt with an authoritative factory-defect bundle is eligible. Preparing a case creates
no agent job and grants no capability: the existing role admission, isolated tests, CRE and offline broker
remain mandatory after this boundary. No raw incident text becomes a trusted instruction.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from ..common import REPO_ROOT, canonical_json, sha256_bytes
from . import bundle, line_recovery, local_agent, maintainer
from .mission_ledger import MissionLedger
from .queue import QueueError


def prepare(store, order_id, attempt_id, workspace, origin, *, eff=None, repo=REPO_ROOT):
    from .policy import load
    from ..reliability import isolation

    eff = eff or load()
    order = store.order(order_id)
    if not order or not local_agent.enabled("afo-factory-maintainer", eff) or not local_agent.authorized(order, eff):
        raise QueueError("LINE_MAINTENANCE_NOT_AUTHORIZED")
    context = line_recovery.context(store, order_id, attempt_id, workspace, origin)
    source = Path(workspace).resolve()
    model = line_recovery._read(source / ".forge-run/model-profile.json", "SOURCE_MODEL_PROFILE_INVALID").get("default")
    if not model or not local_agent.authorized(order, eff, model):
        raise QueueError("LINE_MAINTENANCE_MODEL_NOT_AUTHORIZED")
    attempts = store.attempts(order_id)
    selected = [a for a in attempts if a["attempt_id"] == attempt_id]
    if len(selected) != 1 or selected[0]["state"] not in ("FAILED", "SUCCEEDED"):
        raise QueueError("LINE_MAINTENANCE_REQUIRES_TERMINAL_SOURCE")
    incident = bundle.build(source, order_id, attempt_id, run_failed=selected[0]["state"] == "FAILED")
    if not incident or incident.get("failure_class") != "FACTORY_CODE_DEFECT":
        raise QueueError("LINE_MAINTENANCE_REQUIRES_FACTORY_DEFECT")
    mission = MissionLedger(store).for_order(order_id)
    if time.time() >= MissionLedger(store).snapshot(mission)["limits"]["deadline"]:
        raise QueueError("LINE_MAINTENANCE_MISSION_EXPIRED")
    if not isolation.available():
        raise QueueError("MAINTAINER_SANDBOX_UNAVAILABLE")
    binding = {"schema": "forge-c/line-maintenance-origin/1", "workspace": str(source),
               "context_sha256": sha256_bytes(canonical_json(context)), "mission_id": mission,
               "order_id": order_id, "attempt_id": attempt_id, "source_revision": context["source_revision"]}
    pid = f"mnt-{order_id.removeprefix('afo-')[:16]}-a{selected[0]['seq']}"
    path = maintainer.case_dir(pid) / "case.json"
    if path.exists():
        prior = maintainer.load_case(pid)
        if prior.get("line_binding") != binding or prior.get("base") != context["source_revision"]:
            raise QueueError("LINE_MAINTENANCE_CASE_REBOUND")
        return prior
    # Preserve the original broker's source, path, credential, protected-oracle and publication boundaries.
    compact = {k: incident[k] for k in ("order_id", "attempt_id", "bundle_id", "failure_class", "fingerprint", "error_code")}
    dom = {"error_code": incident["error_code"]}
    return maintainer.prepare(pid, context["source_revision"], compact, Path(repo), line_binding=binding,
                              line_failure_bundle=incident,
                              run_evidence=bundle.run_evidence(source, incident["phase"], dom))  # CAPA-222
