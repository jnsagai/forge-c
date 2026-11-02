"""RPR-100 (Fabro run WO-F014-SWE3-IWDG-20261101-L3, Omniverse2, 2026-11-01): IWDG LL greenfield SWE.3 resumed from
WO-F014-SWE2-IWDG-20261101-02 on the think profile v5 (time box 240 s). The code visit ended its time box (CONTINUE at
code:SWU-LL-05); the continuation check of the code step read inspect-reply.json, found it MISSING and the workflow went
on to the design node (FAILED: code:SWU-LL-05 has no valid code task) and the author gate (REJECTED).

Scenario: a SWE.3 workspace whose structured code visit answered CONTINUE, through the real lrtx.runner continue-check
of the code step. Symptom: the check does not continue the visit."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the continuation check of the SWE.3 code step does not continue a visit that answered CONTINUE"


def main() -> int:
    from forge_factory.lrtx import runner
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        d = ws / ".forge-run/lrtx/SWE.3"
        d.mkdir(parents=True)
        (d / "reply.json").write_text(json.dumps({"status": "CONTINUE", "issues": ["time box used"]}))
        rc = runner.main(["continue-check", "--phase", "SWE.3", "--workspace", str(ws), "--of", "code"])
    if rc == 0:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
