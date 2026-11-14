"""Feature 021 T009 (FR-006): a non-PASS phase keeps its valid items. A line retry (attempt B, C, ...) inherits every
author task the earlier attempts of its own series validated, matched by the run-identity-free semantic key, so only
what changed is authored again; records without the key, changed inputs and answers the current checks refuse are
never carried. Applies to every phase's author tasks (inherited_task); no model call for a carried task."""
import json

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import visit as V

SERIES = "WO-F014-SWE2-SPIM-20261114-L30"
SCHEMA = {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}


def _base(wo, text_in="the interface inputs"):
    p = {"phase": "SWE.2", "task": "interfaces", "role": "swe2-author", "model": "m", "instructions": "write", "sources": [text_in],
         "output_schema": SCHEMA, "assessment_scope": {"work_order": wo}}
    p["input_hash"] = S.semantic_key({**p, "wo": wo})  # differs per order, like the real input_hash
    return p


def _ws(state, wo, record=None):
    ws = state / "workorders" / wo / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": wo}))
    if record is not None:
        ck = V._ckpt(ws, "SWE.2", "interfaces")
        ck.parent.mkdir(parents=True, exist_ok=True)
        ck.write_text(json.dumps(record))
    return ws


@pytest.fixture()
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path / "state"


def _valid(base, **kw):
    return {"task": "interfaces", "status": "VALID", "doc": {"text": "kept"}, "base_hash": base["input_hash"],
            "semantic_key": S.semantic_key(base), **kw}


def test_series_predecessors_newest_first():
    assert V.series_predecessors(SERIES) == [] and V.series_predecessors(None) == []
    assert V.series_predecessors(SERIES + "C") == [SERIES + "B", SERIES]
    assert V.series_predecessors("WO-F014-CMP-SWE2-X-20261114-C03") == []


def test_a_retry_inherits_the_validated_task_of_its_earlier_attempt(state):
    _ws(state, SERIES, _valid(_base(SERIES)))
    dst = _ws(state, SERIES + "C")
    base = _base(SERIES + "C")
    assert base["input_hash"] != _base(SERIES)["input_hash"]  # the run context differs: input_hash never matched
    rec = V.inherited_task(dst, "SWE.2", "interfaces", base, lambda d: [])
    assert rec["doc"] == {"text": "kept"} and rec["inherited_from"]["source_work_order"] == SERIES
    assert rec["inherited_from"]["match"] == "semantic_key" and rec["base_hash"] == base["input_hash"]


@pytest.mark.parametrize("why", ["inputs_changed", "no_semantic_key", "refused_by_current_check", "invalid"])
def test_nothing_is_carried_that_the_current_order_cannot_trust(state, why):
    src_base = _base(SERIES, "other inputs" if why == "inputs_changed" else "the interface inputs")
    rec = _valid(src_base)
    if why == "no_semantic_key":
        rec.pop("semantic_key")
    if why == "invalid":
        rec["status"] = "INVALID"
    _ws(state, SERIES, rec)
    dst = _ws(state, SERIES + "B")
    check = (lambda d: ["REFUSED"]) if why == "refused_by_current_check" else (lambda d: [])
    assert V.inherited_task(dst, "SWE.2", "interfaces", _base(SERIES + "B"), check) is None


def test_run_task_uses_the_inherited_task_without_a_model_call(state, monkeypatch):
    _ws(state, SERIES, _valid(_base(SERIES)))
    dst = _ws(state, SERIES + "B")
    monkeypatch.setattr(S, "call", lambda *a, **k: pytest.fail("no model call for a carried task"))
    budget = {"calls": 0, "max_calls": 5, "log": [], "schema_mode": "json_schema", "schema_mode_basis": "test"}
    rec = V.run_task(dst, "SWE.2", "interfaces", lambda fi, pr: _base(SERIES + "B"), lambda d: [], budget)
    assert rec["status"] == "VALID" and rec["doc"] == {"text": "kept"} and budget["calls"] == 0


def test_every_new_checkpoint_records_its_semantic_key(state):
    dst = _ws(state, SERIES)
    base = _base(SERIES)
    budget = {"calls": 0, "max_calls": 0, "log": [], "schema_mode": "json_schema", "schema_mode_basis": "test"}
    rec = V.run_task(dst, "SWE.2", "interfaces", lambda fi, pr: base, lambda d: [], budget)  # no call left: INVALID
    assert rec["status"] == "INVALID"
    assert json.loads(V._ckpt(dst, "SWE.2", "interfaces").read_text())["semantic_key"] == S.semantic_key(base)
