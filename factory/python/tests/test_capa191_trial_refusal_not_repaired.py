"""CAPA-191 prevention: a trial-binding refusal is deterministic, so a task stops at the first refused call.

WO-F014-SWE1-SPIL-20261107-L41C: each of the six inspector items sent its refused request three times per visit
(calls 18), 160 visits. The visit now ends the task on the first such refusal, like the other admission refusals."""
from __future__ import annotations

import pytest
from forge_factory.lrtx import visit as V
from test_capa122_call_outage import _budget, _build, _script, _sleeps, ws  # noqa: F401 - helpers and fixture


@pytest.mark.parametrize("code", ["PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED", "PRODUCT_ROLE_TRIAL_BINDING_CHANGED"])
def test_capa191_a_trial_refusal_is_sent_once_and_not_repaired(ws, monkeypatch, code):  # noqa: F811
    calls = _script(monkeypatch, ["CALL_REFUSED:" + code] * 10)
    slept = _sleeps(monkeypatch)
    b = _budget(ws)
    rec = V.run_task(ws, "SWE.1", "requirements:A", _build("requirements:A"), lambda _d: [], b)
    assert rec["status"] == "INVALID" and rec["errors"] == ["CALL_REFUSED:" + code]
    assert len(calls) == 1 and b["calls"] == 1 and slept == [] and not b.get("outage")


def test_capa191_other_answers_keep_their_repairs(ws, monkeypatch):  # noqa: F811
    calls = _script(monkeypatch, ["NOT_JSON:x", "NOT_JSON:x", {"ok": True}])
    _sleeps(monkeypatch)
    rec = V.run_task(ws, "SWE.1", "requirements:A", _build("requirements:A"), lambda _d: [], _budget(ws))
    assert rec["status"] == "VALID" and len(calls) == 3
