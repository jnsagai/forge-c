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


NODE = re.compile(r"^  (\w+) \[", re.M)
ALL = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]


@pytest.mark.parametrize("structured", [None, {"phases": ALL, "inspect_phases": ALL, "model": "qwen3.8:27b-q8_0"}])
def test_stop_after_swe1_graph_holds_only_swe1(structured):
    dot, nodes = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured=structured, stop_after="SWE.1")
    defined = set(NODE.findall(dot)) - {"graph"}
    assert not [n for n in defined if re.match(r"(swe[2-6]_|upstream_swe[2-6]|return_swe)", n)], defined
    assert {r.get("phase") for r in nodes.values()} <= {"SWE.1", None}  # role bindings: SWE.1 + release manager
    es = edges(dot)
    assert not [(a, b) for a, b, _c in es if not {a, b} <= defined]  # no edge to a node that is not in the graph
    assert ("swe1_inspect_gate", "release_manager", "outcome=succeeded") in es
    assert ("upstream_swe1", "finalize", "") in es and ("swe1_triage_gate", "finalize", "") in es
    assert reachable(dot) == defined  # every node is reachable from start; none is dead
    full, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured=structured)
    for n in ("swe1_author", "swe1_author_gate", "swe1_inspector", "swe1_inspect_gate", "swe1_route"):
        stmt = lambda d: next(x for x in d.splitlines() if x.startswith(f"  {n} ["))  # noqa: E731
        assert stmt(dot) == stmt(full)  # the SWE.1 nodes themselves are unchanged


def test_stop_after_later_phase_keeps_the_phases_up_to_it():
    dot, nodes = build("WO-X", layer="LL", trace=True, peripheral="iwdg", stop_after="SWE.3")
    phases = {r.get("phase") for r in nodes.values()} - {None}
    assert phases == {"SWE.1", "SWE.2", "SWE.3"}
    assert ("swe3_inspect_gate", "release_manager", "outcome=succeeded") in edges(dot)
    assert reachable(dot) == set(NODE.findall(dot)) - {"graph"}


def test_stop_after_refuses_delivery_first():
    with pytest.raises(ValueError, match="STOP_AFTER_DELIVERY_FIRST_UNSUPPORTED"):
        build("WO-X", layer="LL", peripheral="iwdg", stop_after="SWE.1", assessment_manifest={"delivery_first": {"schema": "forge-c/delivery-first/1"}})


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
