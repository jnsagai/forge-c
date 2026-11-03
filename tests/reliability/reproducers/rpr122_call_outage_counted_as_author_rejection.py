"""RPR-122 (Fabro run WO-F014-CMP-SWE1-CRCL-20261102-10, cloud comparison line, loop10, 2026-11-03): the owner's Claude
account refused every call for ~12 minutes (usage limit). Every structured SWE.1 author task of the two rework visits
got CALL_REFUSED:bridge_upstream_failed, each visit ended FAILED, the author gate recorded the visits as REJECTED
attempts and the route's STUCK rule ended the phase "BLOCKED STUCK: repeated rejection without changed evidence;
external diagnosis required" - a model-call outage concluded as a product rejection.

Scenario: a scratch structured SWE.1 work order (high-allowance development policy, local profile) whose author visit
runs the real lrtx.visit task machinery against a model call that is always refused (structured.call stubbed with the
bridge's refusal); the visit reply goes through the real author gate twice, then the real route gate.
Symptom: an outage visit is recorded as a REJECTED author attempt, or the route ends the phase as STUCK / product
rejection instead of an explicit infrastructure outcome."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "a model-call outage visit is recorded as a rejected author attempt and the route ends the phase as STUCK"
REFUSAL = "CALL_REFUSED:bridge_upstream_failed"


def _workspace(ws: Path) -> None:
    from forge_factory import development_execution as D

    (ws / ".forge-run").mkdir(parents=True)
    manifest = {"work_order": "WO-RPR-122", "layer": "LL", "created_at": "2026-11-03T00:00:00Z",
                "purpose": "ASPICE_ONLY", "local_profile": {"id": "cloud-bridge-claude-author-claude-inspector"},
                "development_execution": D.binding(D.HIGH, "ASPICE_ONLY"), "scope": [], "target": {}, "budgets": {}}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest, indent=1))


def _visit(ws: Path) -> str:
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import visit as V

    calls = []

    def refused(p, **_k):
        calls.append(p["task"])
        return {"doc": None, "errors": [REFUSAL], "usage": None, "wall_ms": 1.0, "raw_chars": 0,
                "finish_reason": None}

    S.call = refused
    budget, _f = V.open_visit(ws, "SWE.1", False, list, 256, None)
    budget["schema_mode"], budget["schema_mode_basis"] = "json_schema", "rpr"
    issues = []
    for task in ("requirements:CRC_DR", "requirements:CRC_IDR", "requirements:crosscutting"):
        def build(_fi, _pr, task=task):
            return {"task": task, "role": "swe1-author", "phase": "SWE.1", "model": "m", "input_hash": "h-" + task,
                    "accounting": {"estimated_prompt_tokens": 100}, "output_schema": {"type": "object"}}
        rec = V.run_task(ws, "SWE.1", task, build, lambda _d: [], budget)
        if rec["status"] == "VALID":
            raise LookupError("a refused call produced a valid task")
        issues += [f"{task}: {e}" for e in rec["errors"][:5]]
    if not calls:
        raise LookupError("the model call was never attempted")
    return json.dumps(V.reply(ws, "SWE.1", "FAILED", issues, budget))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ.update(FORGE_STATE_DIR=str(root / "state"), FORGE_EVENTS_DIR=str(root / "events"),
                          FORGE_LRTX_OUTAGE_WAIT_S="0")
        ws = root / "ws"
        _workspace(ws)
        import contextlib
        import io

        from forge_factory.inspection import gate
        from forge_factory.inspection.engine import Store

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                for _ in range(2):  # the incident: two rework visits during the outage, each through the author gate
                    reply = _visit(ws)
                    gate.step_author(Store(ws), "SWE.1", reply)
                rc = gate.step_route(Store(ws), "SWE.1")
        except Exception as exc:  # noqa: BLE001
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
            return 2
        rows = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    authors = [r for r in rows if r.get("step") == "author"]
    routes = [r for r in rows if r.get("step") == "route"]
    if len(authors) != 2 or not routes:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:author/route gates did not record the visits")
        return 2
    g = routes[-1].get("gate") or {}
    rejected = [r for r in authors if r.get("result") == "REJECTED"]
    if rejected or str(g.get("reason", "")).startswith("STUCK") or not g.get("infra_outcome"):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if rc == 1 and g.get("decision") == "BLOCKED" and g["infra_outcome"].get("retryable") is True:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:unexpected route {json.dumps(g)[:120]}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
