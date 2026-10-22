"""RPR-072 (feature 010 lrtx trials, LRTX-TRIAL README; F011-T037): the route gate computes a progress extension for a
phase whose failed cycles are INSPECTIONS, records progress: true, and still BLOCKS - Store.gate already returned
BLOCKED at the checklist maximum and step_route never revisits that decision, so the owner's extension (2026-10-18)
only ever applied to author-gate rejections."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "progress extension granted for inspection cycles but the route still BLOCKS"


def _ins(ws: Path, n: int, findings: list[tuple[str, str]]) -> None:
    d = ws / "inspection/SWE.4"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"INS-SWE.4-{n:03d}.json").write_text(json.dumps({
        "inspection_id": f"INS-SWE.4-{n:03d}", "verdict": "FAIL", "recorded_at": f"2026-10-18T11:0{n}:00Z",
        "baseline_hash": "x", "findings": [{"id": c, "severity": "major", "detail": t} for c, t in findings]}))


def main() -> int:
    from forge_factory.inspection import gate as G
    from forge_factory.inspection.engine import Store

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "ws"
        (ws / ".forge-run/gates").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "created_at": "2026-10-18T00:00:00Z"}))
        _ins(ws, 1, [("SWE4-02", "UT-007 expects the wrong value"), ("SWE4-06", "UT-006 bound")])
        _ins(ws, 2, [("SWE4-02", "UT-007 expects the wrong value"), ("SWE4-06", "UT-006 bound")])
        _ins(ws, 3, [("SWE4-06", "UT-006 bound")])  # UT-007 resolved: 2 -> 1 findings, measurable progress
        if G.extra_cycles() < 1:
            print("REPRODUCER_ERROR:NO_EXTENSION_POLICY")
            return 2
        rc = G.step_route(Store(ws), "SWE.4")
        last = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()][-1]["gate"]
    ext = last.get("progress_extension") or {}
    if ext.get("progress") is not True:
        print("REPRODUCER_ERROR:NO_PROGRESS_COMPUTED")
        return 2
    if rc != 0 or last["decision"] == "BLOCKED":
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
