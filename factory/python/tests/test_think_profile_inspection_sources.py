"""CAPA-088 (run WO-F014-SWE1-RCC-20261101-03): the Ornith thinking profile kept the inherited 40 000-character
per-source bound, so the inspector refused the frozen RCC register_effects.json (107 kB) before any model call."""
from __future__ import annotations

import json

from forge_factory.lrtx import profile, review
from forge_factory.lrtx import structured as S

THINK = "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"


def test_the_thinking_profile_loads_large_frozen_sources_whole(tmp_path):
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {"id": THINK}}))
    assert review.source_char_limit(tmp_path) == 1048576
    rel = "workproducts/SWE.1/register_effects.json"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_text("x" * 107046)
    assert len(S.source(tmp_path, rel, max_chars=review.source_char_limit(tmp_path))["text"]) == 107046


def test_the_bound_matches_the_other_omniverse2_profiles():
    other = profile.load("local-rtx-v2-omniverse2-q38-delivery-first")["structured"]["inspection_max_source_chars"]
    assert profile.load(THINK)["structured"]["inspection_max_source_chars"] == other
