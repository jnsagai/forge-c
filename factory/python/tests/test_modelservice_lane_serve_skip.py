"""017 T048/T049: the qualification lane (mode external) adds no in-run serve nodes; every other lane keeps them."""
from __future__ import annotations

import pytest

from forge_factory.modelservice import lane, lane_run
from forge_factory.workflow import builder

DOT = """digraph g {
  start -> swe1_author
  swe1_author [shape=box, script="python -m forge_factory.lrtx.runner author SWE.1"]
  swe1_author -> swe1_inspect [condition="outcome=succeeded"]
  swe1_inspect [shape=box, script="python -m forge_factory.lrtx.runner inspect SWE.1"]
  swe1_inspect -> finalize
}
"""
ST = {"model": "m", "author_model": "author-m", "inspector_model": "insp-m"}


def _root(tmp_path, text):
    r = tmp_path / "lane"
    r.mkdir()
    if text is not None:
        (r / "model-service.yaml").write_text(text)
    return r


def test_external_lane_adds_no_serve_nodes(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(_root(tmp_path, "mode: external\n")))
    out = builder.serve_swaps(DOT, ST, {})
    assert "_serve" not in out and "lrtx.stack serve" not in out and out == DOT


@pytest.mark.parametrize("text", [None, "mode: owned\n", "not: [valid\n"])
def test_other_lanes_keep_their_serve_nodes(tmp_path, monkeypatch, text):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(_root(tmp_path, text)))
    out = builder.serve_swaps(DOT, ST, {})
    assert "swe1_author_serve" in out and "swe1_inspect_serve" in out and "lrtx.stack serve" in out


def test_a_stray_file_in_a_taken_root_never_removes_swaps(tmp_path, monkeypatch):
    r = _root(tmp_path, "mode: external\n")
    monkeypatch.setattr(lane_run, "TAKEN_ROOTS", (r,))
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(r / "sub"))
    (r / "sub").mkdir()
    (r / "sub" / "model-service.yaml").write_text("mode: external\n")
    assert builder.external_model_service(str(r)) is False
    assert builder.external_model_service(str(r / "sub")) is False
    assert "swe1_author_serve" in builder.serve_swaps(DOT, ST, {})


def test_the_owner_lane_root_is_refused():
    assert builder.external_model_service("/mnt/data/forge-c/swe1-fabro-20261031/lrtx") is False
