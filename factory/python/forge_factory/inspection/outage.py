"""CAPA-122 (Fabro run WO-F014-CMP-SWE1-CRCL-20261102-10, cloud comparison line, loop10, 2026-11-03): a model-call
outage is an infrastructure outcome, never an author attempt or a product rejection.

The owner's Claude account refused every call for ~12 minutes (usage limit). Every structured SWE.1 author task got
CALL_REFUSED:bridge_upstream_failed, the visit ended FAILED, the author gate recorded two identical REJECTED attempts
and the route's STUCK rule (CAPA-014) ended the phase "BLOCKED STUCK: repeated rejection without changed evidence".
The local line has the same exposure: an unreachable gateway is CALL_FAILED:<transport error>, a gateway whose
llama-server/Ollama upstream is down answers HTTP 500 (non-admission path) or PROVIDER_REQUEST_OUTCOME_UNKNOWN (502).

Here: which call errors are an outage, the bounded wait schedule of the structured visit, and the route outcome.
Deterministic and model-free. Admission/budget refusals (MISSION_*, JOB_TOKEN_*, admission_*, cost_cap) and 4xx
contract errors are NOT outages: they keep their existing handling."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

CODE = "MODEL_CALLS_REFUSED"
INFRA = "INFRA_UNAVAILABLE"
PREFIX = f"{INFRA}:{CODE}"  # the task/visit issue that replaces a refused call's raw error after the bounded wait

# Typed refusals that mean "the model service did not answer", by producer:
#   cloud bridge (lrtx/cloud_bridge.py): bridge_upstream_failed (502, upstream CLI/API failed)
#   forge gateway (llm_gateway.py, durable path): PROVIDER_REQUEST_OUTCOME_UNKNOWN, PROVIDER_<kind>_TIMEOUT_OUTCOME_UNKNOWN
#   llama-server: unavailable_error (503 while loading / overloaded)
#   any HTTP 5xx without a typed body (an uncaught upstream connect error in the gateway is a plain HTTP 500)
_REFUSED = re.compile(r"^CALL_REFUSED:(?:bridge_upstream_failed|unavailable_error|server_error|"
                      r"PROVIDER_REQUEST_OUTCOME_UNKNOWN|PROVIDER_[A-Z]+_TIMEOUT_OUTCOME_UNKNOWN|HTTP_5\d\d)$")
_TRANSPORT = re.compile(r"^CALL_FAILED:")  # structured.call: URLError/OSError/broken stream - nothing was answered
_ISSUE = re.compile(rf"\b{INFRA}:{CODE}\b")


def call_outage(errors: list[str] | None) -> str | None:
    """The outage code of a structured call result's errors (structured.call returns exactly one error when no
    answer came back), else None."""
    errs = [str(e) for e in errors or []]
    if len(errs) != 1:
        return None
    e = errs[0]
    return e if _REFUSED.match(e) or _TRANSPORT.match(e) else None


def outage_error(code: str, waited_s: float) -> str:
    return f"{PREFIX} ({code[:120]}; retried for {int(waited_s)} s)"


def is_outage_issue(issue: str) -> bool:
    """A visit/gate issue that reports a model-call outage (optionally prefixed by LRTX_TASK_INVALID:<task>:)."""
    return bool(_ISSUE.search(str(issue)))


def all_outage(issues: list[str] | None) -> bool:
    iss = [str(i) for i in issues or []]
    return bool(iss) and all(is_outage_issue(i) for i in iss)


def any_outage(issues: list[str] | None) -> bool:
    return any(is_outage_issue(str(i)) for i in issues or [])


DEFAULT_WAIT_S = 600.0
_STEPS = (30.0, 60.0, 120.0, 180.0, 210.0)


def wait_steps() -> list[float]:
    """The bounded wait-and-retry schedule of one visit (total FORGE_LRTX_OUTAGE_WAIT_S, default 600 s; 0 disables
    waiting). Each step is followed by one retry of the refused call."""
    try:
        total = max(0.0, min(3600.0, float(os.environ.get("FORGE_LRTX_OUTAGE_WAIT_S", DEFAULT_WAIT_S))))
    except ValueError:
        total = DEFAULT_WAIT_S
    out, left = [], total
    for s in _STEPS:
        if left <= 0:
            break
        out.append(min(s, left))
        left -= out[-1]
    while left > 0:  # a larger configured total repeats the longest step
        out.append(min(_STEPS[-1], left))
        left -= out[-1]
    return out


# ---- gate side ------------------------------------------------------------------------------------------------------
def _rows(ws: Path, phase: str, since: str) -> list[dict]:
    log = Path(ws) / ".forge-run" / "gates" / "gate-log.jsonl"
    if not log.is_file():
        return []
    out = []
    for x in log.read_text().splitlines():
        if f'"phase": "{phase}"' in x:
            d = json.loads(x)
            if d.get("ts", "") >= since:
                out.append(d)
    return out


def is_infra_row(d: dict) -> bool:
    return d.get("result") == INFRA or bool(d.get("infra_outcome"))


def pending(ws: Path, phase: str, since: str = "") -> dict | None:
    """The phase's latest author/inspect gate record of this epoch, when it is an infrastructure outcome (the route
    decides on it), else None."""
    rows = [d for d in _rows(ws, phase, since) if d.get("step") in ("author", "inspect")]
    return rows[-1] if rows and rows[-1].get("result") == INFRA else None


def route_decision(g: dict, row: dict) -> dict:
    step = row.get("step")
    return {**g, "decision": "BLOCKED",
            "reason": f"{INFRA}: {CODE} during the {step} visit (model calls refused or unreachable after the bounded "
                      "wait-and-retry); retryable infrastructure outcome, not a product rejection - resume the phase "
                      "when the model service answers",
            "infra_outcome": {"code": CODE, "step": step, "retryable": True, "at": row.get("ts"),
                              "issues": list(row.get("issues") or [])[:5]}}


def package_findings(ws: Path) -> list[dict]:
    """Phases whose route ended on an infrastructure outcome: one explicit package finding each (the package states
    the outage instead of only the last product verdict)."""
    out = []
    for phase in [f"SWE.{n}" for n in range(1, 7)]:
        routes = [d for d in _rows(ws, phase, "") if d.get("step") == "route"]
        g = (routes[-1].get("gate") or {}) if routes else {}
        if g.get("infra_outcome"):
            out.append({"id": f"{phase}:{INFRA}", "severity": "major", "detail": str(g.get("reason", ""))[:160]})
    return out
