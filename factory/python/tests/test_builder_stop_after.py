"""Phase-scoped runs (owner 2026-10-31: "I want a fabro run by now just for SWE.1"): `stop_after` sends the run from
that phase's inspection gate to the Release Manager and the finalizer; without it the graph is byte-identical."""
from __future__ import annotations

import re

import pytest
from forge_factory.workflow.builder import build

EDGE = re.compile(r"^  (\w+) -> (\w+)(?: \[condition=\"([^\"]+)\"\])?$", re.M)


def edges(dot: str) -> list[tuple[str, str, str | None]]:
    return [(a, b, c) for a, b, c in EDGE.findall(dot)]


def reachable(dot: str) -> set[str]:
    adj: dict[str, set[str]] = {}
    for a, b, _c in edges(dot):
        adj.setdefault(a, set()).add(b)
    seen, todo = {"start"}, ["start"]
    while todo:
        for n in adj.get(todo.pop(), ()):
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return seen


def test_default_graph_is_unchanged():
    assert build("WO-X", layer="LL", trace=True, peripheral="iwdg") == \
        build("WO-X", layer="LL", trace=True, peripheral="iwdg", stop_after=None)


@pytest.mark.parametrize("structured", [None, {"phases": ["SWE.1"], "model": "qwen3.8:27b-q8_0"}])
def test_stop_after_swe1_finalizes_after_the_swe1_inspection(structured):
    full, n_full = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured=structured)
    dot, nodes = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured=structured, stop_after="SWE.1")
    assert nodes == n_full  # same nodes and role bindings: only the forward route changes
    es = edges(dot)
    assert ("swe1_inspect_gate", "release_manager", "outcome=succeeded") in es
    assert not any(a == "swe1_inspect_gate" and b.startswith("swe2") for a, b, _c in es)
    assert not any(a == "swe6_inspect_gate" and b == "release_manager" for a, b, _c in es)
    # SWE.2..SWE.6 are entered only through the ADR-0008 chains: the return chain and the upstream defect triage (both
    # gated scripts that fall through to the finalizer when those phases never ran)
    into_later = {(a, b) for a, b, _c in es if re.match(r"swe[2-6]_", b) and not re.match(r"swe[2-6]_", a)}
    assert into_later == ({(f"return_swe{n}", "swe3_fix_author" if n == 3 else f"swe{n}_author") for n in range(2, 7)}
                          | {("upstream_swe2", "swe2_triage"), ("upstream_swe3", "swe3_triage")})
    removed = set(full.splitlines()) - set(dot.splitlines())
    # every forward link after SWE.1 is gone, so a return into a later phase cannot run on into the phases after it
    assert removed == {'  swe1_inspect_gate -> swe2_author [condition="outcome=succeeded"]',
                       '  swe2_inspect_gate -> swe3_regmap [condition="outcome=succeeded"]',
                       '  swe3_inspect_gate -> swe4_scaffold [condition="outcome=succeeded"]',
                       '  swe4_inspect_gate -> swe5_target_author [condition="outcome=succeeded"]',
                       '  swe5_inspect_gate -> swe6_scaffold [condition="outcome=succeeded"]',
                       '  swe6_inspect_gate -> release_manager [condition="outcome=succeeded"]'}
    assert {"swe1_author", "swe1_inspector", "release_manager", "finalize", "exit"} <= reachable(dot)


def test_stop_after_must_be_a_phase_not_before_the_entry_phase():
    with pytest.raises(ValueError, match="STOP_AFTER_INVALID"):
        build("WO-X", layer="LL", peripheral="iwdg", stop_after="SWE.9")
    with pytest.raises(ValueError, match="STOP_AFTER_INVALID"):
        build("WO-X", layer="LL", peripheral="iwdg", phases=["SWE.2", "SWE.3"], stop_after="SWE.1")


def test_cli_passes_stop_after(monkeypatch, tmp_path):
    from forge_factory import workorder

    seen = {}
    monkeypatch.setattr(workorder, "run", lambda *a, **k: seen.update(k) or {"work_order": "WO-X"})
    workorder.main(["--example", str(tmp_path), "--wo", "WO-X", "--stop-after", "SWE.1"])
    assert seen["stop_after"] == "SWE.1"
    workorder.main(["--example", str(tmp_path), "--wo", "WO-X"])
    assert seen["stop_after"] is None
