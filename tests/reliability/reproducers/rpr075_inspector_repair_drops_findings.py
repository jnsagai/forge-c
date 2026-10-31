"""RPR-075 (standalone SWE.1 run on Omniverse2, 2026-10-31, SWE1-01/SWE1-03): an inspector answer "PASS with findings"
is rejected by validate_verdict and the localized repair returns "PASS" with no findings. The checkpoint kept only the
errors of the rejected attempt, so the findings the model had stated were lost without a trace (owner option A:
keep them auditable)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "inspector findings dropped in repair are not kept in the task checkpoint"
FINDING = "SWR-001 states the write but not that the other CRC registers are preserved."


def main() -> int:
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import visit as V

    def build(findings, previous):
        return {"phase": "SWE.1", "task": "inspect:rpr075:SWE1-01", "role": "swe1-inspector", "model": "fixture",
                "findings": findings or [], "input_hash": "rpr075-" + ("repair" if findings else "base"),
                "accounting": {}, "output_schema": {"type": "object"}, "_messages": []}

    def check(doc):
        return ["a PASS verdict carries no findings (use FAIL when a finding exists)"] \
            if doc["verdict"] == "PASS" and doc["findings"] else []

    def call(packet, **_):
        doc = {"verdict": "PASS", "findings": [] if packet["findings"] else [FINDING], "evidence_checked": ["x"]}
        return {"doc": doc, "errors": [], "usage": None, "wall_ms": 0, "finish_reason": "stop"}

    S.call = call
    S.schema_mode_for = lambda model, digest=None: ("json_schema", "fixture")
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "ws"
        (ws / ".forge-run").mkdir(parents=True)
        rec = V.run_task(ws, "SWE.1", "inspect:rpr075:SWE1-01", build, check, {"calls": 0, "max_calls": 10})
        stored = json.loads(V._ckpt(ws, "SWE.1", "inspect:rpr075:SWE1-01").read_text())
    if rec["status"] != "VALID" or rec["doc"]["findings"] or len(stored["attempts"]) < 2:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED")
        return 2
    kept = [f for a in stored["attempts"] for f in a.get("rejected_findings") or []]
    if FINDING not in kept:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
