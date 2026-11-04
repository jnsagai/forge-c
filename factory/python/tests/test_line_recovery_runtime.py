"""Host interlocks and native launch uncertainty, zero inference or production side effects."""
import json
from pathlib import Path

import pytest
from forge_factory.afo import line_recovery_runtime as R
from forge_factory.afo import line_launcher as LL
from forge_factory.afo.local_agent import LaunchNotStarted


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    root = tmp_path / "runtime"
    (root / "run").mkdir(parents=True)
    cfg = LL.LineConfig(stack_root=root, gpu_lock=tmp_path / "gpu.lock", guard=())
    job = {"job_id": "afo-agent-" + "a" * 24, "order_id": "order", "nonce": "nonce", "profile": "fixture",
           "model": "local-model", "factory_revision": {"commit": "a" * 40}}
    from forge_factory.lrtx import profile
    monkeypatch.setattr(profile, "load", lambda _: {"deployment": {"ports": {"llama": 11457}}})
    monkeypatch.setattr(LL, "live_runs", lambda *a: {})
    monkeypatch.setattr(LL, "_guard", lambda *a: None)

    class Host:
        def __init__(self):
            self.calls = []
            self.revision = {"commit": "a" * 40, "dirty": False}
            self.models = [{"id": "local-model", "metadata": "provider metadata is permitted"}]
            self.native_rc = 0
            self.environments = []
            self.native = {"job_id": job["job_id"], "nonce": "nonce", "run_id": "RUN-1"}
        def stack(self, args, **kwargs):
            self.calls.append(args)
            self.environments.append(kwargs["env"])
            if args == ["status"]:
                return 0, json.dumps({"status": "UP", "health": {"fabro": True, "gateway": True}})
            if "factory_revision;print" in "".join(args):
                return 0, json.dumps(self.revision)
            if "curl" in args:
                return 0, json.dumps({"data": self.models})
            if "native-job" in args:
                return self.native_rc, json.dumps(self.native)
            return 0, "{}"
    return cfg, job, Host()


def launch(fixture, **kwargs):
    cfg, job, host = fixture
    return R.launch(job, cfg=cfg, host=host, authorization=kwargs.pop("authorization", lambda _: True), **kwargs)


def test_success_is_receipted_with_original_job_nonce_under_existing_locks(fixture):
    assert launch(fixture) == "RUN-1"
    _, _, host = fixture
    assert len([x for x in host.calls if "native-job" in x]) == 1
    assert not any("start" in x or "stop" in x for x in host.calls)


def test_native_runtime_retains_the_already_bound_operator_stop_fence(fixture):
    _, job, host = fixture
    job["native_context"] = {"FORGE_OPERATIONS_INTENT": "/fixture-private-control/intent.json"}
    job["durable_protocol"] = "1.0"
    assert launch(fixture) == "RUN-1"
    assert all(env["FORGE_OPERATIONS_INTENT"] == "/fixture-private-control/intent.json" for env in host.environments)
    assert all(env["FORGE_DURABLE_AUTONOMY"] == "1" for env in host.environments)


def test_revoked_authority_and_live_driver_never_serve_or_launch(fixture, monkeypatch):
    with pytest.raises(LaunchNotStarted, match="NOT_AUTHORIZED"):
        launch(fixture, authorization=lambda _: False)
    assert fixture[2].calls == []
    def busy(*a):
        raise LL.LaunchError("RUN_LIVE")
    monkeypatch.setattr(LL, "live_runs", busy)
    with pytest.raises(LaunchNotStarted, match="RUN_LIVE"):
        launch(fixture)
    assert fixture[2].calls == []


def test_real_gpu_lock_prevents_second_launch(fixture):
    cfg, _, host = fixture
    with LL.gpu_lock(cfg.gpu_lock):
        with pytest.raises(LaunchNotStarted, match="GPU_LOCK_HELD"):
            launch(fixture)
    assert host.calls == []


def test_different_or_dirty_runtime_refuses_before_model_serve(fixture):
    _, _, host = fixture
    for revision in [{"commit": "b" * 40, "dirty": False}, {"commit": "a" * 40, "dirty": True}]:
        host.revision = revision
        with pytest.raises(LaunchNotStarted, match="RUNTIME_REVISION_MISMATCH"):
            launch(fixture)
    assert not any("serve" in x or "native-job" in x for x in host.calls)


@pytest.mark.parametrize("models", [[], [{"id": "other"}], [{"id": "local-model"}, 3]])
def test_model_identity_mismatch_is_never_native_launch_uncertainty(fixture, models):
    _, _, host = fixture
    host.models = models
    with pytest.raises(LaunchNotStarted, match="SERVED_MODEL_MISMATCH"):
        launch(fixture)
    assert not any("native-job" in x for x in host.calls)


def test_revocation_after_serving_prevents_native_submit(fixture):
    _, _, host = fixture
    def allowed(_):
        return not any("serve" in x for x in host.calls)
    with pytest.raises(LaunchNotStarted, match="NOT_AUTHORIZED"):
        launch(fixture, authorization=allowed)
    assert not any("native-job" in x for x in host.calls)


def test_unreceipted_native_call_retains_uncertainty(fixture):
    _, _, host = fixture
    host.native_rc = 1
    with pytest.raises(RuntimeError, match="NATIVE_LAUNCH_UNCERTAIN") as e:
        launch(fixture)
    assert not isinstance(e.value, LaunchNotStarted)
