import copy
import json
import time
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz, policy, queue
from forge_factory.afo import product_role_trial as T
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.lrtx import role_capability as C


@pytest.fixture
def trial(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    identity = dict(
        role="swe1-author",
        model_digest="a" * 64,
        precision="Q4_K_M",
        reasoning="none",
        schema_mode="json_schema",
        adapter_revision="b" * 40,
        context_tokens=32768,
        sampling={"temperature": 0},
        task_class="PRODUCT_ROLE_EXPERIMENT",
    )
    job = dict(
        order_id="order",
        model="local",
        profile="profile",
        model_digest="a" * 64,
        precision="Q4_K_M",
        factory_revision={"commit": "b" * 40},
    )
    order = dict(envelope=json.dumps(dict(request_id="request", driver_class="LL", model_profile="local")))
    monkeypatch.setattr(queue, "Store", lambda: SimpleNamespace(order=lambda _: order))
    eff = SimpleNamespace(mode="PILOT", sha256="c" * 64)
    monkeypatch.setattr(policy, "load", lambda: eff)
    monkeypatch.setattr(authz, "AUTH_DIR", tmp_path)
    monkeypatch.setattr(authz, "find", lambda *a, **kw: SimpleNamespace(allow=True))
    doc = dict(
        schema="forge-c/product-role-trial/1",
        qualification_only=True,
        order_ids=["order"],
        source_revision="b" * 40,
        profile="profile",
        model="local",
        deadline_epoch=time.time() + 300,
        roles={"swe1-author": [identity]},
        authorization_ref="trial-grant",
    )

    def publish(value):
        sha = digest(value)
        ref = dict(path=f"afo/product-role-trials/{sha}.json", sha256=sha)
        immutable_json(tmp_path / ref["path"], value)
        (tmp_path / "trial-grant.json").write_text(json.dumps({"signed_runbook_ref": "qualification-product-014:" + sha}))
        return ref

    return SimpleNamespace(doc=doc, job=job, eff=eff, publish=publish, root=tmp_path)


def body():
    return dict(response_format={"type": "json_schema"}, reasoning_effort="none", temperature=0)


def test_separately_signed_experiment_does_not_claim_qualified_capability(trial):
    T.bind(trial.publish(trial.doc), trial.job, trial.eff)
    assert C.admit_job(trial.job, "swe1-author", input_tokens=100, output_tokens=50, body=body()) == {
        "qualification_only": True,
        "qualified": False,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("order_ids", ["other"]),
        ("qualification_only", False),
        ("source_revision", "d" * 40),
        ("profile", "other"),
        ("model", "other"),
        ("deadline_epoch", 0),
    ],
)
def test_changed_job_scope_refuses_before_generation(trial, field, value):
    doc = copy.deepcopy(trial.doc)
    doc[field] = value
    with pytest.raises(Refused, match="PRODUCT_ROLE_TRIAL_BINDING_CHANGED"):
        T.bind(trial.publish(doc), trial.job, trial.eff)


def test_request_configuration_and_context_remain_bounded(trial):
    T.bind(trial.publish(trial.doc), trial.job, trial.eff)
    changed = body()
    changed["temperature"] = 1
    with pytest.raises(Refused, match="CONFIGURATION_UNDECLARED"):
        C.admit_job(trial.job, "swe1-author", input_tokens=1, output_tokens=1, body=changed)
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        C.admit_job(trial.job, "swe1-author", input_tokens=32768, output_tokens=1, body=body())
    with pytest.raises(Refused, match="CONFIGURATION_UNDECLARED"):
        C.admit_job(trial.job, "swe1-inspector", input_tokens=1, output_tokens=1, body=body())


def test_signed_manifest_and_frozen_bytes_rechecked_at_every_request(trial, monkeypatch):
    T.bind(trial.publish(trial.doc), trial.job, trial.eff)
    (trial.root / "trial-grant.json").write_text(json.dumps({"signed_runbook_ref": "wrong"}))
    with pytest.raises(Refused, match="NOT_OWNER_SIGNED"):
        C.admit_job(trial.job, "swe1-author", input_tokens=1, output_tokens=1, body=body())
    path = trial.root / trial.job["product_role_trial"]["path"]
    path.chmod(0o600)  # simulate external tampering with the otherwise immutable fixture
    path.write_text("{}")
    with pytest.raises(Refused, match="TRIAL_CHANGED"):
        T.identity(trial.job, "swe1-author", body(), trial.eff)


def test_no_experiment_keeps_ordinary_capability_requirement(trial):
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        C.admit_job(trial.job, "swe1-author", input_tokens=1, output_tokens=1, body=body())


def test_signed_trial_covers_every_role_of_the_real_product_workflow(trial):
    from forge_factory.registry.agents import load_agents
    from forge_factory.workflow.builder import build

    _, nodes = build("WO-EXPERIMENT", goal="Native workflow admission", sections={}, layer="LL", brownfield="FROZEN")
    roles = {node["role"] for node in nodes.values()}
    assert "release-manager" in roles
    assert next(agent for agent in load_agents()[0] if agent.id == "release-manager").readonly
    identity = trial.doc["roles"]["swe1-author"][0]
    trial.doc["roles"] = {role: [{**identity, "role": role}] for role in roles}
    T.bind(trial.publish(trial.doc), trial.job, trial.eff)
    for role in roles:
        assert C.admit_job(trial.job, role, input_tokens=100, output_tokens=50, body=body()) == {
            "qualification_only": True,
            "qualified": False,
        }


@pytest.mark.parametrize("role", ["afo-conductor", "safety-authority", "operator"])
def test_product_experiment_cannot_add_administrative_authority(trial, role):
    identity = trial.doc["roles"]["swe1-author"][0]
    trial.doc["roles"][role] = [{**identity, "role": role}]
    with pytest.raises(Refused, match="PRODUCT_ROLE_TRIAL_ROLES_INVALID"):
        T.bind(trial.publish(trial.doc), trial.job, trial.eff)


def test_release_role_requires_its_own_signed_configuration_or_capability(trial):
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        C.admit_job(trial.job, "release-manager", input_tokens=1, output_tokens=1, body=body())
    T.bind(trial.publish(trial.doc), trial.job, trial.eff)
    with pytest.raises(Refused, match="CONFIGURATION_UNDECLARED"):
        C.admit_job(trial.job, "release-manager", input_tokens=1, output_tokens=1, body=body())
