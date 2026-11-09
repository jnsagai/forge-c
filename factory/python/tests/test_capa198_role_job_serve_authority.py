"""CAPA-198 (WO-F014-SWE1-GPIOL-20261107-L40J): the local diagnosis never started.

The product run ended with the inspector (qwen3.8) loaded. The recovery planner (Ornith) launch ran `stack serve` with
no line stack payload; under managed serving lrtx.stack.serve swaps only through the line stack lifecycle, so it was
refused MODEL_SWAP_REFUSED_MANAGED_SERVING -> LINE_RECOVERY_MODEL_SERVE_FAILED, and the ledger kept only
"BindingRefused". The role launcher now passes its own serve authority (job, nonce, model), fenced like a product
execution and limited to a pre-launch serve; the typed refusal code reaches the evidence.
"""
import hashlib
import json
from pathlib import Path

import pytest
from forge_factory.afo import line_recovery_runtime as R
from forge_factory.afo import line_stack_lifecycle as A
from forge_factory.afo import local_agent as L
from forge_factory.afo.durable import Refused, canonical
from forge_factory.afo.line_recovery import BindingRefused
from forge_factory.afo.local_agent import LaunchNotStarted
from forge_factory.afo.queue import Store
from test_line_recovery_runtime import fixture, launch  # noqa: F401

JOB = "afo-agent-" + "b" * 24
MODEL = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"


def test_the_role_launch_serves_with_its_own_job_bound_serve_authority(fixture):  # noqa: F811
    assert launch(fixture) == "RUN-1"
    _, job, host = fixture
    (env,) = [e for args, e in zip(host.calls, host.environments, strict=True) if "serve" in args]
    raw = Path(env[A.FILE]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == env[A.SHA]
    assert json.loads(raw) == {"schema": A.AGENT_SCHEMA, "job_id": job["job_id"], "order_id": job["order_id"],
                               "nonce": job["nonce"], "model": job["model"]}
    native = [e for args, e in zip(host.calls, host.environments, strict=True) if "native-job" in args]
    assert native and all(A.FILE not in e and A.SHA not in e for e in native)


def test_a_binding_refusal_keeps_its_typed_code_in_the_launch_evidence():
    job = {"job_id": JOB, "nonce": "n"}
    assert LaunchNotStarted(job, BindingRefused("LINE_RECOVERY_MODEL_SERVE_FAILED")).failure_type == \
        "LINE_RECOVERY_MODEL_SERVE_FAILED"
    assert LaunchNotStarted(job, BindingRefused("free text: no")).failure_type == "BindingRefused"


@pytest.fixture
def agent(tmp_path, monkeypatch):
    from forge_factory.afo import host

    monkeypatch.setattr(host, "preflight", lambda *a, **kw: {"ok": True})
    root = (tmp_path / "lrtx").resolve()
    (root / "state/supervisor").mkdir(parents=True)
    (root / "run").mkdir()
    store = Store(root / "state/supervisor/line-queue.sqlite3")
    intent = tmp_path / "operations-intent.json"
    job = {"job_id": JOB, "order_id": "order-1", "nonce": "nonce-1", "role": "afo-recovery-planner", "model": MODEL,
           "profile": "prof", "profile_sha256": "p" * 64, "mission_id": "mission", "operations_epoch": 1,
           "state": "LAUNCHING", "native_context": {"FORGE_OPERATIONS_INTENT": str(intent)}}
    with store.tx() as c:
        c.execute(L.SCHEMA)
        c.execute("INSERT INTO afo_local_agent_jobs VALUES (?,?,?,?,?,?)",
                  (JOB, "order-1", "order-1-a1", job["role"], job["state"], json.dumps(job)))
    execution = {"job_id": JOB, "mission_id": "mission", "launch_nonce": "nonce-1", "lease_epoch": 7,
                 "resource_lease": "HELD", "authorization_state": "VALID", "admission_state": "DISPATCH_INTENT_RECORDED",
                 "native_run_ids": [], "task_outcome": "ACTIVE"}
    with store.tx() as c:
        c.execute("INSERT INTO afo_execution_liveness VALUES (?,?,?,?)",
                  ("execution-1", JOB, "mission", canonical(execution).decode()))
        c.execute("INSERT INTO afo_resource_ownership VALUES ('inference',?,?,?)", (JOB, 7, "{}"))
    allowed = {"value": True}
    monkeypatch.setattr(R, "authorize", lambda j, s=None: allowed["value"])
    for key, value in {"FORGE_DURABLE_AUTONOMY": "1", "FORGE_AFO_QUEUE_SCOPE": "line-local",
                       "FORGE_STATE_DIR": str(root / "state"), "FORGE_LINE_STACK_ROOT": str(root),
                       "FORGE_OPERATIONS_INTENT": str(intent), "FORGE_DATA_ROOT": str(tmp_path)}.items():
        monkeypatch.setenv(key, value)
    path, sha = A.write_agent_payload(job, tmp_path)
    monkeypatch.setenv(A.FILE, str(path))
    monkeypatch.setenv(A.SHA, sha)
    s = {"root": root, "profile": {"id": "prof", "_sha256": "p" * 64, "models": {"allowed": {MODEL: {}}}}}
    return {"s": s, "store": store, "job": job, "allowed": allowed, "path": path, "root": root}


def test_the_agent_payload_selects_the_line_lifecycle_and_binds_its_own_job(agent):
    assert A.selected() and A.agent_payload()["job_id"] == JOB
    _, _, job, execution, intent, guard = A._bound(agent["s"])
    assert job["job_id"] == JOB and execution["lease_epoch"] == 7 and str(intent.path).endswith("operations-intent.json")
    assert guard.startup_binding == {"job_id": JOB, "nonce": "nonce-1", "mission_id": "mission",
                                     "operations_epoch": 1, "lease_epoch": 7}
    guard()
    agent["allowed"]["value"] = False  # revoked between the fence and a physical effect
    with pytest.raises(Refused, match="LINE_STACK_EFFECT_AUTHORITY_EXPIRED_OR_CHANGED"):
        guard()


@pytest.mark.parametrize("change, code", [
    ("payload_sha", "LINE_STACK_AGENT_PAYLOAD_INVALID"),
    ("other_model", "LINE_STACK_AGENT_AUTHORITY_OR_EXECUTION_FENCED"),
    ("unauthorized", "LINE_STACK_AGENT_AUTHORITY_OR_EXECUTION_FENCED"),
    ("other_profile", "LINE_STACK_AGENT_AUTHORITY_OR_EXECUTION_FENCED"),
    ("foreign_owner", "LINE_STACK_RESOURCE_OR_REQUEST_NOT_QUIESCENT"),
    ("live_request", "LINE_STACK_RESOURCE_OR_REQUEST_NOT_QUIESCENT"),
    ("other_scope", "LINE_STACK_SCOPE_MISMATCH"),
])
def test_the_agent_fence_refuses_anything_but_its_own_quiescent_authorized_job(agent, monkeypatch, change, code):
    if change == "payload_sha":
        monkeypatch.setenv(A.SHA, "0" * 64)
    elif change == "other_model":
        value = json.loads(agent["path"].read_bytes()) | {"model": "qwen3.8:27b-q8_0"}
        agent["path"].write_bytes(canonical(value))
        monkeypatch.setenv(A.SHA, hashlib.sha256(canonical(value)).hexdigest())
    elif change == "unauthorized":
        agent["allowed"]["value"] = False
    elif change == "other_profile":
        agent["s"]["profile"]["_sha256"] = "q" * 64
    elif change == "foreign_owner":
        with agent["store"].tx() as c:
            c.execute("UPDATE afo_resource_ownership SET holder='afo-product-x' WHERE resource='inference'")
    elif change == "live_request":
        with agent["store"].tx() as c:
            c.execute("INSERT INTO afo_request_ledger VALUES ('r','mission',?, 'RESERVED','{}')", (JOB,))
    elif change == "other_scope":
        monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "other")
    with pytest.raises(Refused, match=code):
        A._bound(agent["s"])


@pytest.mark.parametrize("action, workspace", [("stop", None), ("start", None), ("serve", "/ws")])
def test_a_role_job_authority_is_only_a_pre_launch_serve(agent, action, workspace):
    with pytest.raises(Refused, match="LINE_STACK_AGENT_ACTION_UNDECLARED"):
        with A.fenced(agent["s"], action, model=MODEL, workspace=workspace):
            pass


def test_serving_the_model_already_served_needs_no_fence(agent, monkeypatch):
    (agent["root"] / "run/services.json").write_text(json.dumps({"processes": {"llama_server": {"model": MODEL}}}))
    agent["allowed"]["value"] = False  # would refuse if the fence were entered
    assert A.serve(agent["s"], MODEL) == {"model_swap": "NOT_NEEDED", "model": MODEL}
