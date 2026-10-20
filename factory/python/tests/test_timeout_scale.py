"""Opt-in node timeout scaling for slower models (owner local Qwen trial 2026-10-20)."""
import re

import pytest
from forge_factory import workorder as W
from forge_factory.workflow.builder import build, scale_timeouts


def test_scale_multiplies_every_node_timeout():
    g, _ = build("WO-T", layer="LL", trace=True, chunk_lines=40)
    before = [int(x) for x in re.findall(r'timeout="(\d+)s"', g)]
    after = [int(x) for x in re.findall(r'timeout="(\d+)s"', scale_timeouts(g, 4))]
    assert before and after == [4 * x for x in before]
    assert scale_timeouts(g, 1) == g


def test_scale_out_of_range_refused():
    with pytest.raises(ValueError, match="TIMEOUT_SCALE_OUT_OF_RANGE"):
        W.run(W.REPO_ROOT / "examples/0009a-iwdg-ll", "WO-X", model="qwen3:8b", provider="ollama", timeout_scale=20)
