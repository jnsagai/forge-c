"""CAPA-211 (SPI LL L41O, 2026-11-10): the set inspection's SQ-04 finding ("coherent structure and priorities": no
sections, no release scope) cited "SWR-001..SWR-046", so the rework routing reached all 15 author tasks. None of them
can change the document organisation, SWR identifiers or release header - the factory assembles them (CAPA-210) - yet
each re-authored requirements that had passed individual inspection; SPI_TXDR churned twice into new phase-1 defects
and once into a 108k-token draft of the whole driver. In the structured SWE.1 an SQ-04 finding is factory-owned: it
reopens no author task (rework or keep-fixed) and is recorded in the rework routing as such. Other findings route as
before (CAPA-108), including whole-set ranges of other criteria."""
import json

from forge_factory.lrtx import swe1
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - prepared IWDG LL work order, skip marker
from test_lrtx_swe1_rework_scope import _first_visit, _rework, _swr


def _sq04(ws_):
    ids = sorted(json.loads((ws_ / ".forge-run/lrtx/SWE.1/assembly.json").read_text())["swr"])
    return (f"SWE1-02: SQ-04 (set-quality): software_requirements.md presents {ids[0]}..{ids[-1]} as a flat numbered "
            "list with no by-function/register section headers and no release-scope identifier")


def test_an_sq04_finding_reopens_no_author_task(ws, monkeypatch):  # noqa: F811
    calls = []
    _first_visit(ws, monkeypatch, calls)
    rlr = _swr(ws, "requirements:IWDG_RLR")
    _rework(ws, [_sq04(ws), f"SWE1-03: Major - software_requirements.md, {rlr[0]}: failure behaviour is not established."])
    assert swe1.visit(ws, "m")["status"] == "PASS"
    assert {p["task"] for p in calls} == {"requirements:IWDG_RLR"}
    assert all("SQ-04" not in f for p in calls for f in p["findings"])
    routing = json.loads((ws / ".forge-run/lrtx/SWE.1/rework-routing.json").read_text())
    sq = [r for r in routing["findings"] if "SQ-04" in r["finding"]]
    assert len(sq) == 1 and sq[0]["tasks"] == [] and sq[0]["factory_owned"] == "SWE.1 assembly"
    assert routing["tasks"] == ["requirements:IWDG_RLR"]


def test_an_sq04_only_rework_makes_no_model_call(ws, monkeypatch):  # noqa: F811
    calls = []
    _first_visit(ws, monkeypatch, calls)
    _rework(ws, [_sq04(ws)])
    assert swe1.visit(ws, "m")["status"] == "PASS" and calls == []


def test_other_whole_set_findings_still_reach_every_named_task():
    amap = {"swr": {f"SWR-00{i}": {"task": f"requirements:R{i}", "key": f"k{i}"} for i in range(1, 4)}}
    f = "SWE1-05: SQ-01 (set-quality): SWR-001..SWR-003 verification criteria are not measurable"
    assert sorted(swe1.route_findings([f], amap)) == ["requirements:R1", "requirements:R2", "requirements:R3"]
    assert swe1.route_findings([f.replace("SQ-01", "SQ-04")], amap) == {}
