"""CAPA-217 (TIM LL L43M..L43Q, 2026-11-10): five launches failed GUARD_FAIL and every controller case was
CONTROLLER_FAILURE_UNDIAGNOSED: the launch transcript export keeps only whitelisted step fields, and the guard's verdict
(its typed result, e.g. FAIL:GUARD_WORKER_ARGUMENT_INVALID) is the step's `result`, which was dropped. The guard step now
exports its result when it is the guard's typed form (OK or FAIL:<codes>); anything else is a gap, never a body."""
from __future__ import annotations

import json
from pathlib import Path

from test_controller_escalation import drain, settled  # noqa: F401 - the settled controller case fixture
from test_line_recovery_product_bridge import product  # noqa: F401 - the fixture settled builds on


def _case(p, result):
    base = p.cfg.runs_root / ".launch" / p.spec["wo"]
    base.mkdir(parents=True)
    (base / "attempt-1.json").write_text(json.dumps(dict(
        schema="forge-c/line-launch-attempt/1", work_order=p.spec["wo"], revision="a" * 40, fabro_run_id=None,
        outcome="GUARD_FAIL", steps=[dict(step="gpu_lock", outcome="OK"),
                                     dict(step="guard", outcome="GUARD_FAIL", result=result, own_llama_server=None)])))
    out = drain(p)
    return json.loads(Path(out["exports"][0]["case"]).read_text())


def test_the_typed_guard_verdict_is_exported(settled):  # noqa: F811
    verdict = "FAIL:GUARD_WORKER_ARGUMENT_INVALID FOREIGN_GPU_PROCESS:1234"
    case = _case(settled, verdict)
    guard = [s for s in case["records"]["launcher"]["steps"] if s.get("step") == "guard"]
    assert guard and guard[0]["result"] == verdict
    assert "GUARD_RESULT_UNTYPED" not in case["gaps"]


def test_an_untyped_guard_result_is_a_gap_not_a_body(settled):  # noqa: F811
    case = _case(settled, "FAIL: see /home/x token=NEVER_SECRET")
    guard = [s for s in case["records"]["launcher"]["steps"] if s.get("step") == "guard"]
    assert guard and "result" not in guard[0]
    assert "GUARD_RESULT_UNTYPED" in case["gaps"]
    assert "NEVER_SECRET" not in json.dumps(case)
