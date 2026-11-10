"""CAPA-210 (SPI LL L41O, 2026-11-09 23:39Z and 2026-11-10 01:45Z: set inspection REWORK SWE1-02 twice from SQ-04
"Coherent structure and priorities"): the factory's SWE.1 assembler wrote SWR-001..SWR-046 as one flat list under a
single title with no release scope. The finding is about the document the factory assembles, not about any author
task's requirements, yet it was routed to 15 author tasks that cannot change it - a third REWORK stops the order
(SAME_ITEM_FAILED_3X). The assembler now groups the requirements by the driver's hardware interface (one section per
register, in inventory order), then cross-cutting requirements, then budgets, and states the work-order release scope
and priority in the header. SWR numbering and every requirement line are unchanged."""
from __future__ import annotations

import json
import re

from test_lrtx_swe1 import ANSWERS, _gate, _scripted, ws  # noqa: F401 - the IWDG LL workspace fixture

from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1


def _visit(ws, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, []))
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS"
    return (ws / swe1.REQS).read_text()


def test_requirements_are_grouped_by_register_then_crosscutting_then_budgets(ws, monkeypatch):  # noqa: F811
    md = _visit(ws, monkeypatch)
    heads = re.findall(r"^## (.+)$", md, re.M)
    regs = [h.split(" ")[0] for h in heads if " register" in h]
    assert regs == ["IWDG_KR", "IWDG_PR", "IWDG_RLR", "IWDG_SR"]  # split IWDG_SR_1/_2 share one section
    assert heads[len(regs):len(regs) + 4] == ["Cross-cutting requirements", "Resource and timing budget requirements",
                                            "Budget feasibility", "Open points"]  # CAPA-212 adds the feasibility section
    kr, pr = md.index("## IWDG_KR register"), md.index("## IWDG_PR register")
    assert all(kr < md.index(f"**SWR-00{i}**") < pr for i in range(1, 5))
    assert md.index("## Cross-cutting requirements") < md.index("**SWR-010**") < md.index("## Resource and timing")
    assert md.index("## Resource and timing") < md.index("**SWR-011**") < md.index("## Open points")


def test_the_header_states_release_scope_and_priority(ws, monkeypatch):  # noqa: F811
    head = _visit(ws, monkeypatch).split("\n## ", 1)[0]
    assert "Release scope: work order WO-T-IWDG-LL" in head and "Priority: mandatory" in head


def test_requirement_lines_ids_and_the_unchanged_gate_are_kept(ws, monkeypatch):  # noqa: F811
    md = _visit(ws, monkeypatch)
    ids = re.findall(r"\*\*(SWR-\d{3})\*\*", md)
    assert len(ids) >= 11 and ids == [f"SWR-{i:03d}" for i in range(1, len(ids) + 1)]
    assert "- **SWR-011** The IWDG LL driver shall occupy at most 4096 bytes of flash." in md
    eff = json.loads((ws / swe1.EFFECTS).read_text())["effects"]
    assert {e["swr"] for e in eff} == {f"SWR-{i:03d}" for i in range(1, 10)}
    assert _gate(ws, monkeypatch) == 0
