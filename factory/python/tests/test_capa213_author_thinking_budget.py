"""CAPA-213 (owner 2026-11-10 "if inspector confirms, apply the 16k budget"): about half of the Ornith author's tokens
and time went into SWE.1 drafts the checker rejected, and longer thinking was rejected more often (<8k 21 %, >64k 67 %).
Ornith's chat template has no effort level, so the profile's reasoning effort does not bound it. A replay of the 16 SPI LL
L41O first drafts (think-budget test, 2026-11-10) gave about 5.0 min per checker-accepted draft with a 16k thinking budget
against 8.1 min unbounded. The structured author request now carries the llama.cpp per-request thinking budget for
Ornith; inspector requests and other models are unchanged."""
from __future__ import annotations

from forge_factory.lrtx import structured as S

ORNITH = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"


def _p(role, model, sampling=None):
    return {"model": model, "role": role, "_messages": [{"role": "user", "content": "x"}], "output_reserve": 4096,
            "output_schema": {"type": "object"}, "sampling": sampling}


def test_an_ornith_author_request_carries_the_16k_thinking_budget():
    body = S.request_body(_p("swe1-author", ORNITH))
    assert body["thinking_budget_tokens"] == 16384
    assert body["max_tokens"] == 4096  # the answer reserve is unchanged


def test_inspector_requests_and_other_models_are_unchanged():
    assert "thinking_budget_tokens" not in S.request_body(_p("swe1-inspector", ORNITH, {"temperature": 0, "seed": 1}))
    assert "thinking_budget_tokens" not in S.request_body(_p("swe1-author", "qwen3.8:27b-q8_0"))


def test_the_body_keeps_its_shape():
    body = S.request_body(_p("swe1-inspector", "qwen3.8:27b-q8_0", {"temperature": 0, "seed": 1}), temperature=None)
    assert body["response_format"]["json_schema"]["strict"] is True and body["temperature"] == 0 and body["seed"] == 1
    assert body["stream"] is True and body["stream_options"] == {"include_usage": True}
