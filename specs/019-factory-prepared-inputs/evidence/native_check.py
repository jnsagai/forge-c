"""Feature 019 native acceptance checker (read-only): the line walked the SWE.1 stage of the driver ladder by itself.

T025: WWDG LL SWE.1 PASS -> WWDG HAL SWE.1 PASS on the provided LL order L29 -> SPI LL SWE.1 PASS -> TIM LL SWE.1 PASS,
each created by the line after the previous step passed; the guardian reports every ladder step DONE; the live deploy
derived its campaign from the source ladder (generation report campaign_source DERIVED).
Usage: python native_check.py t025   (exit 0 = all checks hold; prints one line per check)"""
import json
import sqlite3
import sys
from pathlib import Path

Q = "/mnt/data/forge-c/swe1-fabro-20261031/lrtx/state/supervisor/line-queue.sqlite3"
WO = Path("/mnt/data/forge-c/swe1-fabro-20261031/lrtx/state/workorders")
QUAL = Path("/mnt/data/forge-c/swe1-fabro-20261031/qualification")
AUDIT = Path.home() / ".config/forge-c/line-local/owner-supervised-development"
STATE = Path("/mnt/data/forge-c/owner-autodeploy/deployer/state.json")
STEPS = [("wwdg-ll", "WO-F014-SWE1-WWDGL-20261109-L44F"), ("wwdg-hal", "WO-F014-SWE1-WWDGH-20261109-L45"),
         ("spi-ll", "WO-F014-SWE1-SPIL-20261107-L41P"), ("tim-ll", "WO-F014-SWE1-TIML-20261107-L43T")]
L29 = "WO-F014-SWE6-WWDGL-20261103-L29"


def main() -> int:
    q = sqlite3.connect(f"file:{Q}?mode=ro", uri=True)
    rows = {r[0]: r for r in q.execute("SELECT request_id, state, terminal_reason, created_epoch, order_id FROM afo_work_orders")}
    passed_at = {}
    ok = True

    def check(cond, text):
        nonlocal ok
        ok = ok and bool(cond)
        print(("PASS " if cond else "FAIL ") + text)

    prev_pass = None
    for lineage, wo in STEPS:
        r = rows.get(wo)
        check(r is not None and r[2] == "PHASE_VERDICT:PASS:SWE.1", f"{lineage} {wo} terminal {r[2] if r else None}")
        if r is None:
            continue
        ev = q.execute("SELECT occurred_utc FROM afo_lifecycle_events WHERE order_id=? AND type='afo.state_blocked'",
                       (r[4],)).fetchone()
        passed_at[wo] = ev[0] if ev else None
        if prev_pass:
            created = q.execute("SELECT occurred_utc FROM afo_lifecycle_events WHERE order_id=? AND type='afo.submitted'",
                                (r[4],)).fetchone()
            check(created and created[0] >= prev_pass, f"{wo} created {created[0] if created else None} after previous pass {prev_pass}")
        prev_pass = passed_at[wo]
    man = json.loads((WO / STEPS[1][1] / "workspace/.forge-run/manifest.json").read_text())
    check(L29 in json.dumps(man), f"WWDG HAL manifest names the provided LL order {L29}")
    audits = sorted(AUDIT.glob("*.audit.jsonl"), key=lambda p: p.stat().st_mtime)
    last = json.loads(audits[-1].read_text().strip().splitlines()[-1]) if audits else {}
    states = {str(x.get("lineage", "")).split("/")[-1]: x.get("state") for x in (last.get("placement") or {}).get("lineages", [])}
    for lineage, _ in STEPS:
        check(states.get(lineage) == "DONE", f"guardian ladder {lineage} state {states.get(lineage)}")
    live = json.loads(STATE.read_text())["live"]["commit"][:8]
    rep = QUAL / f"owner-allowance-{live}-main-20261107/development-inputs/generation-report.json"
    src = json.loads(rep.read_text()).get("campaign_source") if rep.is_file() else None
    check(src == "DERIVED", f"live deploy {live} generation report campaign_source {src}")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1:] != ["t025"]:
        sys.exit("usage: native_check.py t025")
    sys.exit(main())
