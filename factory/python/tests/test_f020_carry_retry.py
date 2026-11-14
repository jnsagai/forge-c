"""CAPA (run WO-F014-SWE1-SPIM-20261113-L51 -> L51B): the line's automatic retry of a functional SWE.1 order carries
from the earlier attempts of its own series (owner rule D36), without a `swe1.carry_from` in the work order."""
from __future__ import annotations

import json

from f020_fixtures import ser_spec
from f020_swe1 import author, prepared
from forge_factory.lrtx import swe1_carry as C

BASE = "WO-F014-SWE1-SERM-20261114-L9"


def test_attempt_names_and_their_predecessors():
    assert C.predecessors(BASE) == [] and C.predecessors(None) == []
    assert C.predecessors(BASE + "B") == [BASE]
    assert C.predecessors(BASE + "D") == [BASE + "C", BASE + "B", BASE]
    assert C.predecessors(BASE + "AA")[:2] == [BASE + "Z", BASE + "Y"] and len(C.predecessors(BASE + "AA")) == 26
    assert C.predecessors("WO-F014-CMP-SWE1-UARTM-20261113-C03") == []  # not a line series
    assert C.predecessors("WO-F014-SWE2-SERM-20261114-L9B") == []  # SWE.1 only


def test_the_retry_carries_from_the_failed_attempt(tmp_path, monkeypatch):
    src = prepared(tmp_path, monkeypatch, wo=BASE)
    rep, _ = author(src, monkeypatch)
    assert rep["status"] == "PASS", rep
    dst = prepared(tmp_path, monkeypatch, spec=ser_spec(), wo=BASE + "C")  # attempt B never ran
    man = json.loads((dst / ".forge-run/manifest.json").read_text())
    assert "swe1_carry_from" not in man and C.wanted(dst)
    p, meta = C.source(dst)
    assert p == src and meta["source_work_order"] == BASE


def test_named_sources_come_first_and_a_first_attempt_carries_nothing(tmp_path, monkeypatch):
    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": "swe1-functional-v2", "carry_from": ["WO-F020-NAMED", BASE]}
    dst = prepared(tmp_path, monkeypatch, spec=spec, wo=BASE + "B")
    assert C.candidates(dst) == ["WO-F020-NAMED", BASE]
    first = prepared(tmp_path, monkeypatch, wo=BASE)
    assert C.candidates(first) == [] and not C.wanted(first)


def test_a_register_level_order_is_left_alone(tmp_path):
    ws = tmp_path / "w"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": BASE + "B"}))
    assert C.candidates(ws) == [] and not C.wanted(ws)
