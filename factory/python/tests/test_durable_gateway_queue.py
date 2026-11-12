"""A new stage waits for the prior provider request without releasing uncertain capacity."""

# ruff: noqa: F811
import asyncio
import json

import httpx
import pytest
from forge_factory import llm_gateway as G
from forge_factory.afo import policy
from forge_factory.afo import request_admission as A
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.operations import Intent
from forge_factory.lrtx import role_capability
from forge_factory.lrtx.admission import Admission
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_integration import ready
from test_da014_protocol import protocol  # noqa: F401


@pytest.mark.parametrize("outcome", ["complete", "stop", "revoke", "unknown", "wait_timeout"])
def test_next_stage_uses_existing_bounded_queue_then_rechecks_authority(protocol, monkeypatch, tmp_path, outcome):
    p = protocol
    job = ready(p, monkeypatch)
    execution = Executions(p.store)
    execution.reserve(job["job_id"], "mission-test", job["nonce"])
    execution.dispatch_intent(job["job_id"])
    execution.adopt(job["job_id"], ["native-queue-fixture"])
    monkeypatch.setattr(policy, "load", lambda *args, **kwargs: p.eff)
    monkeypatch.setattr(role_capability, "admit_job", lambda *args, **kwargs: {"synthetic_fixture": True})
    reserve, start = A.reserve, A.start
    monkeypatch.setattr(A, "reserve", lambda store, binding, body: reserve(p.store, binding, body, eff=p.eff))
    monkeypatch.setattr(A, "start", lambda store, rec, body: start(p.store, rec, body))
    intent_dir = tmp_path / "operator"
    intent_dir.mkdir(mode=0o700)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent_dir / "intent.json"))
    intent = Intent()
    intent.set("RUNNING", actor="fixture", reason="Synthetic request admission", initialize=True)
    before = p.ledger.snapshot("mission-test")

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls, active, peak = [], 0, 0
        admission = Admission(1, 1, max_wait_s=0.03 if outcome == "wait_timeout" else 1, poll_s=0.002)

        async def provider(request):
            nonlocal active, peak
            calls.append(1)
            active += 1
            peak = max(peak, active)
            try:
                if len(calls) == 1:
                    entered.set()
                    await release.wait()
                    if outcome == "unknown":
                        raise httpx.ReadTimeout("Synthetic unknown generation outcome", request=request)
                return httpx.Response(200, json={"choices": [{"message": {"content": "fixture"}, "finish_reason": "stop"}],
                                                "usage": {"prompt_tokens": 10, "completion_tokens": 1}})
            finally:
                active -= 1

        app = G.create_app("http://provider", tmp_path / "meter.jsonl", transport=httpx.MockTransport(provider), admission=admission)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gateway") as client:
            def body(rid):
                return {"model": "qwen-fixture", "messages": [{"role": "user", "content": "fixture"}], "max_tokens": 32,
                        "forge_execution": {"job_id": job["job_id"], "nonce": job["nonce"], "request_id": rid}}

            first = asyncio.create_task(client.post("/v1/chat/completions", json=body("first")))
            await asyncio.wait_for(entered.wait(), timeout=2)
            second = asyncio.create_task(client.post("/v1/chat/completions", json=body("next-stage")))
            try:
                for _ in range(100):
                    if second.done() or admission.waiting:
                        break
                    await asyncio.sleep(0.002)
                waited = admission.waiting
                if outcome == "stop":
                    intent.set("STOPPED", actor="fixture-owner", reason="Stop while next stage is queued")
                elif outcome == "revoke":
                    execution.revoke(job["job_id"])
                elif outcome == "wait_timeout":
                    await asyncio.wait_for(asyncio.shield(second), timeout=1)
            finally:
                release.set()
                responses = await asyncio.wait_for(asyncio.gather(first, second), timeout=3)
        assert waited == 1, "Prior stage still owns inference: next stage must wait, not fail its rapid retries"
        assert responses[0].status_code == (502 if outcome == "unknown" else 200)
        assert responses[1].status_code == (200 if outcome == "complete" else 429)
        assert len(calls) == (2 if outcome == "complete" else 1) and peak == 1
        assert admission.waiting == admission.inflight == 0
        if outcome == "wait_timeout":
            assert responses[1].json()["error"]["type"] == "admission_wait_timeout"

    asyncio.run(scenario())
    assert execution.get(job["job_id"])["resource_lease"] == "HELD"
    after = p.ledger.snapshot("mission-test")
    assert after["attempts"] == before["attempts"] and after["jobs"] == before["jobs"]
    assert after["charged_tokens"] >= before["charged_tokens"]
    with p.store.tx() as c:
        states = [json.loads(r[0])["state"] for r in c.execute("SELECT record FROM afo_request_ledger")]
    assert "UNKNOWN" in states if outcome == "unknown" else all(s == "QUIESCENT" for s in states)
