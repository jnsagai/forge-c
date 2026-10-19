"""AFO-T064 (AFO-FR-067/070; AT-059/062/063) - readiness levels, separate from the configured mode.

IMPLEMENTED       - every implementation task of M0..M6 PASS in the evidence status (BLOCKED/PARTIAL listed)
PILOT_ELIGIBLE    - IMPLEMENTED + reboot/restart drills PASS (T015, T034, T069) + fault campaign PASS (T065) + a real
                    model READY and a deliberate BLOCKED order (T066) + a valid signed PILOT authorization
ACTIVE_ELIGIBLE   - PILOT_ELIGIBLE + a DEMONSTRATED 72 h soak (T068) + the signed operator readiness review (T070)
SLO_DEMONSTRATED  - ACTIVE_ELIGIBLE + a DEMONSTRATED 168 h soak and measured availability (AFO-M01)
Each level is DEMONSTRATED or NOT_DEMONSTRATED with the exact missing items; missing data is NOT_DEMONSTRATED,
never assumed. The configured mode (OBSERVE_ONLY/PILOT/ACTIVE) is reported beside it and is never changed here.
"""
from __future__ import annotations

import json

from ..common import REPO_ROOT, utc_now

IMPLEMENTATION_TASKS = [f"AFO-T{i:03d}" for i in range(1, 62) if i not in (15, 34)]  # reboot drills are pilot items


def assess(status: dict | None = None, *, soaks: list[dict] | None = None, pilot_authorized: bool | None = None) -> dict:
    from .policy import load

    status = status or json.loads((REPO_ROOT / "evidence/afo/status.json").read_text())
    t = {k: v["status"] for k, v in status["tasks"].items()}
    eff = load(log=False)
    if pilot_authorized is None:
        from . import authz

        pilot_authorized = bool(eff.authorization_id) and authz.find("PILOT", eff.sha256 or "", ref=eff.authorization_id
                                                                     ).allow if eff.authorization_id else False
    soaks = soaks or []
    best = {h: any(s["status"] == "DEMONSTRATED" and s["target_hours"] >= h for s in soaks) for h in (24, 72, 168)}
    levels, prev_ok = {}, True

    def level(name: str, need: dict[str, bool]) -> None:
        nonlocal prev_ok
        missing = [k for k, ok in need.items() if not ok]
        if not prev_ok:
            missing = ["previous level not demonstrated", *missing]
        levels[name] = {"status": "DEMONSTRATED" if not missing else "NOT_DEMONSTRATED", "missing": missing}
        prev_ok = not missing

    level("IMPLEMENTED", {f"{k} {t.get(k, 'NOT_RUN')}": t.get(k) == "PASS" for k in IMPLEMENTATION_TASKS})
    level("PILOT_ELIGIBLE", {"AFO-T015 reboot/mount drill PASS": t.get("AFO-T015") == "PASS",
                             "AFO-T034 reboot with in-flight run PASS": t.get("AFO-T034") == "PASS",
                             "AFO-T065 fault campaign PASS": t.get("AFO-T065") == "PASS",
                             "AFO-T066 real READY + deliberate BLOCKED PASS": t.get("AFO-T066") == "PASS",
                             "AFO-T069 restart drill matrix PASS": t.get("AFO-T069") == "PASS",
                             "signed PILOT authorization valid": bool(pilot_authorized)})
    level("ACTIVE_ELIGIBLE", {"72 h soak DEMONSTRATED": best[72],
                              "AFO-T070 signed operator readiness review PASS": t.get("AFO-T070") == "PASS"})
    level("SLO_DEMONSTRATED", {"168 h soak DEMONSTRATED": best[168]})
    top = next((n for n in reversed(list(levels)) if levels[n]["status"] == "DEMONSTRATED"), None)
    return {"schema": "forge-c/afo-readiness/0.1", "generated_utc": utc_now(), "configured_mode": eff.mode,
            "highest_demonstrated": top or "NONE", "levels": levels,
            "statement": "Readiness is evidence-derived and separate from the configured mode; it never switches a "
                         "mode, approves safety or certifies anything."}
