"""CAPA-086 (run WO-F014-SWE1-RCC-20261101-02, Omniverse2, 2026-11-01): the Ornith thinking profile asked for a 21600 s
structured time box, so the SWE.1 author node ran 30 min without exiting and Fabro's 1800 s stall watchdog ended the
run. The time box is capped below the watchdog; the continuation node resumes the work."""
from __future__ import annotations

import re

from forge_factory.workflow.builder import build
from forge_factory.workorder import MAX_VISIT_TIME_S, local_profile_structured

THINK = "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"


def test_a_profile_time_box_above_the_watchdog_margin_is_capped_and_recorded(monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", "/x/lrtx")
    st = local_profile_structured({"id": THINK}, {"layer": "LL"}, "qwen3.8:27b-q8_0")
    assert st["visit_time_s"] == MAX_VISIT_TIME_S == 1200 and st["visit_time_requested_s"] == 21600
    dot, _nodes = build("WO-X", layer="LL", trace=True, peripheral="crc", structured=st, stop_after="SWE.1")
    budgets = {n: re.search(rf"^  {n} \[.*?--time-budget (\d+)", dot, re.M).group(1)
               for n in ("swe1_author", "swe1_author_more", "swe1_inspector", "swe1_inspector_more")}
    assert set(budgets.values()) == {"1200"}, budgets


def test_a_time_box_inside_the_margin_is_unchanged():
    st = local_profile_structured({"id": "local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector"},
                                  {"layer": "LL"}, "m")
    assert st["visit_time_s"] == 600 and "visit_time_requested_s" not in st
