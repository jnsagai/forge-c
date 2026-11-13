"""Owner 2026-11-13 ("go ahead with 1, 2 and 3", autonomy item 3): a recovery planner the GATEWAY refuses is a factory
defect for the maintainer, not a dead end.

L49 (2026-11-13 07:23Z): the UART order's SWE.1 failed, the line asked its recovery planner, and the gateway refused the
packet the factory had built (GATEWAY_HTTP_400:CAPABILITY_LIMIT, 241 requirements). recovery.decide closed the order
(LOCAL_DIAGNOSIS_FAILED) and the maintainer - which is only dispatched for a FACTORY_CODE_DEFECT failure bundle - never
heard of it. The packet is factory code (afo/planner*, the diagnosis packet), inside the maintainer's ALLOW list.

Now: recovery.decide records such a refusal in the order's workspace (.forge-run/recovery/planner-refusal.json, once per
attempt) and returns STATUS; the REPLAN worker rebuilds the failure bundle, which reads the record (bundle.build ->
`apply`) and becomes FACTORY_CODE_DEFECT with error_code PLANNER_REFUSED:<code>; the existing maintenance branch runs.
The maintenance preparation rebuilds the bundle from the same workspace (anti-tamper digest check), so the evidence
lives in the workspace, never in a caller argument. Admission-time refusals (role_capability, before any HTTP call) keep
their designed advisory path: only a refusal the gateway returned for a request the factory sent is routed here."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now

STATUS = "FACTORY_DEFECT_IN_PLANNER"
REL = ".forge-run/recovery/planner-refusal.json"
# the gateway refused a request the factory built (too large / beyond the model's capability for the role)
GATEWAY_REFUSAL = re.compile(r"^GATEWAY_HTTP_4\d\d:(CAPABILITY_LIMIT|PACKET_TOO_LARGE|CONTEXT_LENGTH_EXCEEDED|"
                             r"PROMPT_TOO_LONG)\b")


def _read(ws: Path) -> dict:
    try:
        d = json.loads((Path(ws) / REL).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def code_of(agent_error: str) -> str | None:
    m = GATEWAY_REFUSAL.match(str(agent_error or ""))
    return m.group(0) if m else None


def record(ws: Path, bundle: dict, agent_error: str, job_id: str | None) -> bool:
    """Record a gateway refusal of the planner for this attempt; True only the first time (then the caller routes
    it to the maintainer). False: not a gateway refusal, or already recorded for this attempt."""
    code = code_of(agent_error)
    if code is None or not bundle.get("attempt_id"):
        return False
    doc = _read(ws)
    att = bundle["attempt_id"]
    if att in doc.get("attempts", {}):
        return False
    doc.setdefault("schema", "forge-c/planner-refusal/1")
    doc.setdefault("attempts", {})[att] = {
        "code": code, "job_id": job_id, "at": utc_now(), "phase": bundle.get("phase"),
        "order_id": bundle.get("order_id"), "source_bundle_id": bundle.get("bundle_id"),
        "source_failure_class": bundle.get("failure_class"), "source_error_code": bundle.get("error_code"),
        "fingerprint": "afo-planner-refusal-" + sha256_bytes(f"{code}|{bundle.get('phase')}".encode())[:24]}
    p = Path(ws) / REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return True


def of(ws: Path, attempt_id: str) -> dict | None:
    return _read(ws).get("attempts", {}).get(attempt_id)


def apply(ws: Path, attempt_id: str, cls: str, fingerprint: str, error_code: str, summary: str) -> tuple:
    """(class, fingerprint, error_code, summary) of a failure bundle, with a recorded planner refusal of this attempt
    making it the factory defect it is."""
    r = of(ws, attempt_id)
    if r is None:
        return cls, fingerprint, error_code, summary
    note = (f"factory defect: the recovery planner packet for this failure was refused by the gateway ({r['code']}); "
            f"the run itself failed with {r.get('source_failure_class')}:{r.get('source_error_code')}")
    return "FACTORY_CODE_DEFECT", r["fingerprint"], f"PLANNER_REFUSED:{r['code']}"[:200], f"{note}; {summary}"
