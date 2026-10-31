"""Owner-obligation coverage for SWE.1 (docs/designs/swe1-owner-obligation-coverage.md, owner 2026-10-31).

A work order that declares an `owner_obligations` input gets every obligation mapped to a requirement or recorded as an
obligation gap, checked deterministically by the structured author's self-check AND the SWE.1 author gate (any author
path). Work orders without the input keep their packets, schemas and work products.
"""
from __future__ import annotations

import copy
import json

import pytest
from forge_factory.assurance import owner_obligations as OO
from forge_factory.common import sha256_file
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1

from test_lrtx_swe1 import ANSWERS, DS, _gate, _scripted, ws  # noqa: F401  (fixture reuse)

pytestmark = pytest.mark.skipif(not DS.is_file(), reason="owner datasheet input (git-ignored) not present")

DOC = {"schema": "forge-c/owner-obligations/1", "status": "DRAFT_FOR_OWNER_REVIEW", "owner": "test owner",
       "source_inputs": [], "obligations": [
           {"id": "OBL-start-key", "statement": "Enable starts the watchdog by writing the start key.",
            "critical": True, "effects": [{"register": "IWDG_KR", "field": "KEY", "op": "write"}]},
           {"id": "OBL-no-startup-writes", "statement": "Nothing is written before the first driver call.",
            "critical": True},
           {"id": "OBL-no-polling", "statement": "The driver never waits on a status flag.", "critical": False}]}
REL = "inputs/owner-obligations.json"


def declare(ws_, doc=DOC, rel=REL):
    p = ws_ / rel
    p.write_text(json.dumps(doc, indent=1))
    mp = ws_ / ".forge-run/manifest.json"
    m = json.loads(mp.read_text())
    m["inputs"].append({"path": rel, "role": OO.ROLE, "sha256": sha256_file(p), "bytes": p.stat().st_size})
    mp.write_text(json.dumps(m, indent=1))


def answers(cites: dict[str, list[str]], gaps: list[dict] | None = None, cross=None) -> dict:
    out = copy.deepcopy(ANSWERS)
    for doc in out.values():
        for r in doc["requirements"]:
            r["obligations"] = list(cites.get(r["key"], []))
    out["requirements:crosscutting"]["obligation_gaps"] = list(gaps or [])
    if cross is not None:
        out["requirements:crosscutting"] = cross(out["requirements:crosscutting"])
    return out


COVERED = {"start": ["OBL-start-key"], "startup": ["OBL-no-startup-writes"]}
POLL_GAP = [{"id": "OBL-no-polling", "reason": "the scope states no flag is waited on; test cannot observe absence"}]


def test_covered_obligations_freeze_and_are_traced(ws, monkeypatch):
    declare(ws)
    calls = []
    monkeypatch.setattr(S, "call", _scripted(answers(COVERED, POLL_GAP), calls))
    rep = swe1.visit(ws, "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    md = (ws / swe1.REQS).read_text()
    assert "  - Obligations: OBL-start-key" in md and "## Obligation gaps" in md
    assert "- **OBL-no-polling**: the scope states" in md
    csv = (ws / OO.CSV).read_text().splitlines()
    assert csv[0] == "obligation_id,requirement_id,gap_reason" and any(r.startswith("OBL-start-key,SWR-") for r in csv)
    assert any(r.startswith('OBL-no-polling,,"') for r in csv)
    amap = json.loads((ws / ".forge-run/lrtx/SWE.1/assembly.json").read_text())
    assert amap["owner_obligations"]["status"] == "DECLARED" and OO.CSV in amap["files"]
    for p in calls:  # every packet carries the obligations source and the obligation-aware schema
        assert REL in [s["path"] for s in p["sources"]]
        req = p["output_schema"]["properties"]["requirements"]["items"]
        assert req["properties"]["obligations"]["items"]["enum"] == [o["id"] for o in DOC["obligations"]]
    cross = next(p for p in calls if p["task"] == "requirements:crosscutting")
    assert "obligation_gaps" in cross["output_schema"]["required"]
    assert OO.coverage_findings(ws) == []
    assert _gate(ws, monkeypatch) == 0
    from forge_factory.lrtx import review

    _bl, srcs = review.evidence(ws, "SWE.1")
    assert REL in [s["path"] for s in srcs]  # option 1: the inspector reads the owner obligations


def test_uncovered_obligation_is_repaired_by_the_crosscutting_task(ws, monkeypatch):
    declare(ws)
    calls = []
    base = answers(COVERED)  # OBL-no-polling: neither a requirement nor a gap

    def cross(p):
        if any("SWE1_OBLIGATION_UNCOVERED:OBL-no-polling" in f for f in p.get("findings") or []):
            return {**base["requirements:crosscutting"], "obligation_gaps": POLL_GAP}
        return base["requirements:crosscutting"]

    monkeypatch.setattr(S, "call", _scripted({**base, "requirements:crosscutting": cross}, calls))
    rep = swe1.visit(ws, "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    assert [p["task"] for p in calls].count("requirements:crosscutting") == 2
    assert _gate(ws, monkeypatch) == 0


def test_persistently_uncovered_obligation_fails_and_nothing_freezes(ws, monkeypatch):
    declare(ws)
    monkeypatch.setattr(S, "call", _scripted(answers(COVERED), []))
    rep = swe1.visit(ws, "qwen3-coder:30b")
    assert rep["status"] == "FAILED"  # the unchanged answer after the coverage finding is refused, never assembled
    assert any(i.startswith("requirements:crosscutting: LRTX_FINDING_NOT_ADDRESSED") for i in rep["issues"]), rep
    assert _gate(ws, monkeypatch) != 0  # the gate honours the failed reply and finds the uncovered obligation itself


def test_gate_refuses_an_uncovered_obligation_from_any_author_path(ws, monkeypatch):
    """The author gate holds every author (agent, semantic, structured) to the rule, not only the self-check."""
    declare(ws)
    monkeypatch.setattr(S, "call", _scripted(answers(COVERED), []))
    monkeypatch.setattr(swe1, "obligation_findings", lambda _ws: [])  # an author that does not self-check
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS"
    assert _gate(ws, monkeypatch) != 0
    log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    last = [e for e in log if e["phase"] == "SWE.1" and e.get("step") == "author"][-1]
    assert last["result"] == "REJECTED"
    assert any(str(i).startswith("SWE1_OBLIGATION_UNCOVERED:OBL-no-polling") for i in last["issues"]), last


def test_cited_obligation_needs_its_register_effect(ws, monkeypatch):
    declare(ws)
    cites = {"onf_set": ["OBL-start-key"], "startup": ["OBL-no-startup-writes"]}  # a status read cites the start key
    calls = []
    monkeypatch.setattr(S, "call", _scripted(answers(cites, POLL_GAP), calls))
    rep = swe1.visit(ws, "qwen3-coder:30b")
    assert rep["status"] == "FAILED"  # the citing task got the finding and answered unchanged
    assert any(i.startswith("requirements:IWDG_SR_1: LRTX_FINDING_NOT_ADDRESSED") for i in rep["issues"]), rep
    repair = [p for p in calls if p["task"] == "requirements:IWDG_SR_1" and p.get("findings")]
    assert repair and any("SWE1_OBLIGATION_EFFECT_MISSING:OBL-start-key:IWDG_KR.KEY.write" in f
                          for f in repair[0]["findings"])


def test_unknown_or_unreasoned_ids_in_the_artifacts_are_findings(ws):
    declare(ws)
    (ws / swe1.REQS).parent.mkdir(parents=True, exist_ok=True)
    (ws / swe1.REQS).write_text("# Software requirements\n\n- **SWR-001** The IWDG LL driver shall x.\n"
                                "  - Source: RM0486 p.1\n  - Verification: passes when x.\n"
                                "  - Obligations: OBL-start-key, OBL-made-up\n\n## Obligation gaps\n\n"
                                "- **OBL-no-polling**: short\n- **OBL-ghost**: a gap for an id nobody declared\n")
    found = OO.coverage_findings(ws)
    assert "SWE1_OBLIGATION_UNKNOWN:SWR-001:OBL-made-up" in found
    assert "SWE1_OBLIGATION_UNKNOWN:gap:OBL-ghost" in found
    assert "SWE1_OBLIGATION_GAP_REASON_MISSING:OBL-no-polling" in found
    assert any(f.startswith("SWE1_OBLIGATION_UNCOVERED:OBL-no-startup-writes") for f in found)
    assert any(f.startswith("SWE1_OBLIGATION_EFFECT_MISSING:OBL-start-key") for f in found)  # no effects file


def test_a_changed_or_invalid_declaration_refuses(ws):
    declare(ws)
    (ws / REL).write_text((ws / REL).read_text() + " ")
    assert OO.coverage_findings(ws) == ["SWE1_OWNER_OBLIGATIONS_INPUT_CHANGED"]
    bad = {**DOC, "obligations": [{"id": "bad id", "statement": "x" * 12, "critical": True}]}
    declare(ws, bad, "inputs/owner-obligations-2.json")
    assert OO.coverage_findings(ws) == ["SWE1_OWNER_OBLIGATIONS_DECLARED_TWICE"]


def test_orders_without_obligations_are_unchanged(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, calls))
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS"
    assert all(p["output_schema"] == swe1.GROUP_SCHEMA for p in calls)
    assert all("Owner obligations" not in p["instructions"] for p in calls)
    assert "Obligation" not in (ws / swe1.REQS).read_text() and not (ws / OO.CSV).exists()
    amap = json.loads((ws / ".forge-run/lrtx/SWE.1/assembly.json").read_text())
    assert amap["owner_obligations"] == {"status": "NOT_DECLARED"} and OO.CSV not in amap["files"]
    assert OO.coverage_findings(ws) == [] and OO.source_paths(ws) == []
    assert _gate(ws, monkeypatch) == 0


def test_a_critical_obligation_can_never_be_a_gap(ws, monkeypatch):
    """Owner 2026-10-31: run -02 recorded the critical OBL-preserve-other-registers as a gap with a false reason."""
    declare(ws)
    found_gap = [{"id": "OBL-no-startup-writes", "reason": "the register tasks already constrain every write"}]
    calls = []
    monkeypatch.setattr(S, "call", _scripted(answers({"start": ["OBL-start-key"]}, POLL_GAP + found_gap), calls))
    rep = swe1.visit(ws, "qwen3-coder:30b")
    assert rep["status"] == "FAILED"
    cross = [p for p in calls if p["task"] == "requirements:crosscutting"]
    gap_ids = cross[0]["output_schema"]["properties"]["obligation_gaps"]["items"]["properties"]["id"]["enum"]
    assert gap_ids == ["OBL-no-polling"]  # only the non-critical obligation may be offered as a gap
    assert "can never be obligation gaps: OBL-start-key, OBL-no-startup-writes" in cross[0]["instructions"]
    # first line of defence: the schema refuses the critical id as a gap, so nothing is assembled; the coverage
    # finding is the second line, for authors without the schema (test below, RPR-077)
    assert any(i.startswith("requirements:crosscutting:") and "obligation_gaps" in i for i in rep["issues"]), rep
    assert _gate(ws, monkeypatch) != 0


def test_critical_gap_in_the_artifacts_is_a_finding(ws):
    declare(ws)
    (ws / swe1.REQS).parent.mkdir(parents=True, exist_ok=True)
    (ws / swe1.REQS).write_text("# Software requirements\n\n## Obligation gaps\n\n"
                                "- **OBL-start-key**: the register task covers it implicitly\n"
                                "- **OBL-no-polling**: the inputs state no flag that could be polled\n"
                                "- **OBL-no-startup-writes**: covered elsewhere in the register tasks\n")
    found = OO.coverage_findings(ws)
    assert [f.split(":")[1] for f in found if f.startswith("SWE1_OBLIGATION_CRITICAL_GAP")] == \
        ["OBL-start-key", "OBL-no-startup-writes"]
    assert not any("OBL-no-polling" in f for f in found)  # a non-critical gap with a reason stays allowed
