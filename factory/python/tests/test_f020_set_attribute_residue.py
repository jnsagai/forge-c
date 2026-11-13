"""CAPA-248 (cloud control run WO-F014-CMP-SWE1-UARTM-20261113-C03): the SWE.1 inspection sources of a functional order
carried the requirement set twice (software_requirements.md and its machine view requirement_attributes.json), and the
273-requirement set packet was refused PACKET_TOO_LARGE (309,529 + 4,096 > 262,144 tokens) before any judgement.

The attributes now reach the inspector as a residue index: a value is left out only when the markdown bullet of that SWR
states it exactly under its label; everything else (task, key, a trace-link rationale, an unrendered or changed value,
an attribute without a label) stays in. A register-level order keeps its sources unchanged."""
from __future__ import annotations

import json

import pytest
from f020_swe1 import author, prepared
from forge_factory.lrtx import review

ATTRS = review.FUNCTIONAL_ATTRS
REQS = review.FUNCTIONAL_REQS


@pytest.fixture()
def frozen(tmp_path, monkeypatch):
    import io
    import sys

    from forge_factory.inspection import gate

    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))
    ws = prepared(tmp_path, monkeypatch)
    rep, _ = author(ws, monkeypatch)
    assert rep["status"] == "PASS", rep
    monkeypatch.setattr(sys, "stdin", io.StringIO((ws / ".forge-run/lrtx/SWE.1/reply.json").read_text()))
    assert gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "author"]) == 0
    return ws


def _residue(srcs):
    by = {s["path"]: s for s in srcs}
    assert ATTRS not in by, "the full attributes file is no inspection source of a functional order"
    assert REQS in by
    return json.loads(by[f"{ATTRS}#residue"]["text"])


def test_the_inspection_sources_carry_the_attributes_once_and_lose_nothing(frozen):
    from forge_factory.common import sha256_bytes

    _bl, srcs = review.evidence(frozen, "SWE.1")
    res = _residue(srcs)
    full = json.loads((frozen / ATTRS).read_text())
    assert res["sha256"] == sha256_bytes((frozen / ATTRS).read_bytes()) and res["template"] == full["template"]
    blocks = review._md_blocks((frozen / REQS).read_text())
    rows = {r["id"]: r for r in res["requirements"]}
    assert [r["id"] for r in full["requirements"]] == list(rows)
    for r in full["requirements"]:
        kept = rows[r["id"]]
        assert kept["task"] == r["task"] and kept["key"] == r["key"]
        for k, v in r.items():
            if k in kept:
                assert kept[k] == v
            else:  # left out only when the markdown states exactly this value under its label
                assert review._rendered(k, v, blocks[r["id"]]), (r["id"], k)
    assert len(json.dumps(res)) < len((frozen / ATTRS).read_text())


def test_an_unrendered_or_changed_value_stays_in_the_residue(frozen):
    doc = json.loads((frozen / ATTRS).read_text())
    r0, r1 = doc["requirements"][0], doc["requirements"][1]
    r0["links"] = [{"kind": "trace", "input_id": "IN-02", "locator": "1.1", "rationale": "not rendered for trace"}]
    r0["new_attribute"] = "no label in the markdown"
    r1["title"] = r1["title"] + " (changed after rendering)"
    (frozen / ATTRS).write_text(json.dumps(doc, indent=1) + "\n")
    rows = {r["id"]: r for r in json.loads(review.attribute_index(frozen)["text"])["requirements"]}
    assert rows[r0["id"]]["links"] == r0["links"] and rows[r0["id"]]["new_attribute"] == "no label in the markdown"
    assert rows[r1["id"]]["title"] == r1["title"]
    assert "statement" not in rows[r1["id"]]


def test_a_requirement_the_markdown_lacks_keeps_every_attribute(frozen):
    md = (frozen / REQS).read_text()
    doc = json.loads((frozen / ATTRS).read_text())
    last = doc["requirements"][-1]["id"]
    (frozen / REQS).write_text(md.replace(f"- **{last}**", f"- **{last}X**"))
    rows = {r["id"]: r for r in json.loads(review.attribute_index(frozen)["text"])["requirements"]}
    assert rows[last] == doc["requirements"][-1]


def test_a_register_level_order_keeps_its_sources(frozen):
    m = json.loads((frozen / ".forge-run/manifest.json").read_text())
    m.pop("swe1_level", None)
    (frozen / ".forge-run/manifest.json").write_text(json.dumps(m, indent=1))
    from forge_factory.lrtx.swe1_quality import _functional

    if _functional(frozen) is not None:
        pytest.skip("the level is not read from the manifest key alone")
    _bl, srcs = review.evidence(frozen, "SWE.1")
    paths = [s["path"] for s in srcs]
    assert ATTRS in paths and f"{ATTRS}#residue" not in paths
