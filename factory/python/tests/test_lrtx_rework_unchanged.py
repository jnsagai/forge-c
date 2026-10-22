"""lrtxq1 (2026-10-21): an unchanged answer to rework findings re-froze the inspected baseline, and the inspection
reused its verdicts, so two rework cycles were spent in seconds. The answer must now address the findings or record
why one does not apply; the cross-cutting task is told where failure handling belongs."""
import json

from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1
from forge_factory.lrtx import visit as V
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - shared prepared IWDG LL work order and skip marker

DOC = {"requirements": [{"key": "startup", "statement": "s"}], "not_covered": [], "open_points": []}


def _build(_findings, _previous):
    return S.packet(phase="SWE.1", task="requirements:crosscutting", role="swe1-author", with_skill=False, model="m",
                    instructions="x", sources=[], criteria=[], output_schema=S.PROBE_SCHEMA, output_reserve=64)


def _setup(tmp_path, monkeypatch, answers):
    root = tmp_path / "root"
    ck = V._ckpt(root, "SWE.1", "requirements:crosscutting")
    ck.parent.mkdir(parents=True)
    ck.write_text(json.dumps({"task": "requirements:crosscutting", "status": "VALID", "doc": DOC, "errors": [],
                              "base_hash": _build(None, None)["input_hash"], "attempts": []}))
    seen = []

    def call(p, **_kw):
        seen.append(p)
        return {"doc": answers[len(seen) - 1], "errors": [], "usage": None, "wall_ms": 1.0, "raw_chars": 1,
                "finish_reason": "stop", "format_note": None}

    monkeypatch.setattr(S, "call", call)
    return root, {"calls": 0, "max_calls": 10, "state": None, "deadline": None, "schema_mode": "json_schema"}, seen


def test_an_unchanged_answer_to_findings_is_not_accepted(tmp_path, monkeypatch):
    disputed = {**DOC, "open_points": ["SWE1-03: the driver has no failure mode of its own; the caller bounds polling"]}
    root, budget, seen = _setup(tmp_path, monkeypatch, [DOC, disputed])
    rec = V.run_task(root, "SWE.1", "requirements:crosscutting", _build, lambda _d: [], budget,
                     ["SWE1-03: no failure handling specified"])
    assert rec["status"] == "VALID" and rec["doc"] == disputed and budget["calls"] == 2
    assert rec["attempts"][0]["errors"][0].startswith("LRTX_FINDING_NOT_ADDRESSED")
    assert len(seen) == 2


def test_a_task_that_never_changes_its_answer_stays_invalid(tmp_path, monkeypatch):
    root, budget, _seen = _setup(tmp_path, monkeypatch, [DOC, DOC, DOC])
    rec = V.run_task(root, "SWE.1", "requirements:crosscutting", _build, lambda _d: [], budget,
                     ["SWE1-03: no failure handling specified"])
    assert rec["status"] == "INVALID" and rec["errors"][0].startswith("LRTX_FINDING_NOT_ADDRESSED")


def test_a_valid_checkpoint_without_findings_is_still_reused(tmp_path, monkeypatch):
    root, budget, seen = _setup(tmp_path, monkeypatch, [])
    rec = V.run_task(root, "SWE.1", "requirements:crosscutting", _build, lambda _d: [], budget)
    assert rec["reused"] and not seen and budget["calls"] == 0


def test_crosscutting_task_is_told_where_failure_handling_belongs(ws):  # noqa: F811
    p = swe1.crosscut_packet(ws, [], "m")
    assert "failure handling the work-order scope states" in p["instructions"] and "SWE1-03" in p["instructions"]
    assert "caller bounds its polling" in " ".join(json.load(open(ws / ".forge-run/manifest.json"))["scope"])
