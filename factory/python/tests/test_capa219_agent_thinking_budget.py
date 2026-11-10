"""CAPA-219 (TIM LL L43R recovery, Omniverse2 owner lane, 2026-11-10 18:08-18:30Z): the line recovery planner's
diagnosis request on Ornith carried no thinking budget; the gateway's reasoning policy widened the output cap, the model
generated 133120 tokens of reasoning in 22 minutes and no answer: EMPTY_MODEL_OUTPUT, LOCAL_DIAGNOSIS_FAILED, order
BLOCKED. Every durable-agent request to a model without a template effort level now carries a per-request budget."""
import inspect

from forge_factory.afo import durable_agent as DA

ORNITH = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"
PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"


def _body(model=ORNITH):
    return {"model": model, "stream": False, "max_tokens": 2048, "temperature": 0,
            "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]}


def test_an_ornith_agent_request_has_a_thinking_budget():
    body = DA._bounded_thinking(_body())
    assert body["thinking_budget_tokens"] == DA.AGENT_THINKING_BUDGET[ORNITH] == 32768


def test_other_models_are_unchanged():
    assert "thinking_budget_tokens" not in DA._bounded_thinking(_body("qwen3.8:iq"))


def test_the_two_step_request_carries_it():
    body, measured = DA._finish({"profile": PROFILE, "role": "afo-recovery-planner"}, _body(), {})
    assert body["thinking_budget_tokens"] == 32768 and measured["wire_request_sha256"]


def test_both_request_builders_bound_thinking():
    assert "_bounded_thinking(body)" in inspect.getsource(DA._finish)
    assert "_bounded_thinking(body)" in inspect.getsource(DA.request_material)
