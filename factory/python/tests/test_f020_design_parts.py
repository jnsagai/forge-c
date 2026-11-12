"""Feature 020 T027 / D24: the HAL design-constraint task of the functional SWE.1 author is bounded.

A guideline input larger than the design part bound (`swe1_functional.DESIGN_PART_CHARS`) is partitioned into
consecutive line ranges, cut at numbered section headings where possible and never truncated (every line is in exactly
one part); each part is its own design task (`requirements:design_constraints_p<n>`) whose packet carries only that
slice (`<input>#lines-<a>-<b>`), for the author and for the phase-1 inspector. A guideline within the bound keeps the
single task `requirements:design_constraints` with the whole file, as before. Model calls are scripted."""
from __future__ import annotations

import pytest
from f020_swe1 import MODEL, answers, author, prepared
from forge_factory.lrtx import structured as S

GUIDE = "inputs/hal_guideline.md"


def test_guideline_parts_partition_the_text_at_headings_within_the_bound():
    from forge_factory.lrtx import swe1_functional as F

    text = "".join(f"{n} Section {n}\n" + "".join(f"rule text {n}.{k} " * 4 + "\n" for k in range(12))
                   for n in range(1, 9))
    lines = text.splitlines(keepends=True)
    parts = F.guideline_parts(text, 1000)
    assert parts[0][0] == 0 and parts[-1][1] == len(lines)
    assert all(a < b for a, b in parts) and all(p[1] == q[0] for p, q in zip(parts, parts[1:]))  # no gap, no overlap
    assert all(sum(len(x) for x in lines[a:b]) <= 1000 for a, b in parts)
    assert all(lines[a][0].isdigit() for a, _b in parts)  # cut at a numbered heading
    assert F.guideline_parts(text, len(text)) == [(0, len(lines))]
    long = "x" * 50 + "\n" + "y" * 3000 + "\n" + "z" * 10 + "\n"  # one line over the bound stays whole
    assert F.guideline_parts(long, 100) == [(0, 1), (1, 2), (2, 3)]


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    return prepared(tmp_path, monkeypatch)


def test_a_guideline_within_the_bound_keeps_the_single_design_task(ws):
    from forge_factory.lrtx import swe1_functional as F

    design = [t for t in F.plan(ws) if t["kind"] == "design"]
    assert [t["id"] for t in design] == ["requirements:design_constraints"] and "part" not in design[0]
    assert GUIDE in [s["path"] for s in F.task_packet(ws, design[0], MODEL)["sources"]]


def test_a_large_guideline_becomes_bounded_design_tasks(ws, monkeypatch):
    from forge_factory.lrtx import swe1_functional as F

    monkeypatch.setattr(F, "DESIGN_PART_CHARS", 120)  # the 295-byte fixture guideline is "large" here
    design = [t for t in F.plan(ws) if t["kind"] == "design"]
    assert len(design) >= 2 and [t["id"] for t in design] == [f"requirements:design_constraints_p{n}"
                                                             for n in range(1, len(design) + 1)]
    assert all(t["guideline"] == ["IN-05"] and t["heading"] == "HAL design constraints" for t in design)
    full = (ws / GUIDE).read_text()
    slices = []
    for t in design:
        p = F.task_packet(ws, t, MODEL)
        src = [s for s in p["sources"] if s["path"].startswith(GUIDE)]
        assert [s["path"] for s in src] == [f"{GUIDE}#lines-{t['part']['lines'][0]}-{t['part']['lines'][1]}"]
        assert GUIDE not in [s["path"] for s in p["sources"]]  # never the whole file
        text = "\n".join(m["content"] for m in p["_messages"])
        assert f"part {t['part']['n']} of {len(design)}" in text
        slices.append((F.task_sources(ws, t)[-1]["text"]))
        assert F.contexts(ws)[t["id"]] == F.task_sources(ws, t)  # the phase-1 inspector gets the same slice
    assert "".join(slices) == full  # complete, in order, nothing dropped


def test_the_parts_are_authored_and_assembled_as_one_design_section(ws, monkeypatch):
    from forge_factory.lrtx import swe1_functional as F

    monkeypatch.setattr(F, "DESIGN_PART_CHARS", 120)
    design = [t["id"] for t in F.plan(ws) if t["kind"] == "design"]
    base = answers()
    reqs = base.pop("requirements:design_constraints")["requirements"]
    by_task = dict(base)
    for n, tid in enumerate(design):
        r = dict(reqs[n % len(reqs)])
        if n >= len(reqs):
            r.update(key=f"dc_part_{n}", statement=f"The SER HAL driver shall document its rule set {n} in its "
                     "interface description.")
        by_task[tid] = {"requirements": [r], "open_points": []}
    rep, calls = author(ws, monkeypatch, by_task)
    assert rep["status"] == "PASS", rep
    assert {p["task"] for p in calls} >= set(design)
    md = (ws / F.REQS).read_text()
    assert md.count("## HAL design constraints") == 1
