"""A host intake route is not the native controller's network namespace endpoint."""
# ruff: noqa: F811

import json
import os

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.lrtx.profile import load
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401

PROFILE = "local-rtx-v2-omniverse2-q38-quality"


@pytest.fixture
def bound(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    (root / "run").mkdir(parents=True)
    profile = load(PROFILE)
    storage = str(root / "fabro/storage")
    job = {
        "profile": PROFILE,
        "fabro_url": "http://127.0.0.1:32491/api/v1",
        "fabro_storage": storage,
        "native_context": {"FORGE_DATA_ROOT": str(root)},
        "profile_initial_reservation": {"profile_sha256": profile["_sha256"]},
    }
    services = {
        "root": str(root),
        "profile": PROFILE,
        "profile_sha256": profile["_sha256"],
        "netns": os.readlink("/proc/self/ns/net"),
    }
    (root / "run/services.json").write_text(json.dumps(services))
    (root / "run/services.json").chmod(0o600)
    for k, v in {
        "FORGE_LRTX_PROFILE": PROFILE,
        "FORGE_LRTX_ROOT": str(root),
        "FORGE_FABRO_URL": "http://127.0.0.1:32391/api/v1",
        "FORGE_FABRO_STORAGE": storage,
    }.items():
        monkeypatch.setenv(k, v)
    return job, root, services


def test_host_prepared_job_uses_verified_current_native_endpoint_without_mutating_job(bound):
    job, _, _ = bound
    before = json.dumps(job, sort_keys=True)
    assert L.endpoint_for(job) == "http://127.0.0.1:32391/api/v1"
    assert json.dumps(job, sort_keys=True) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("root", "/some/other/runtime"),
        ("profile", "other-profile"),
        ("profile_sha256", "0" * 64),
        ("netns", "net:[not-the-current-runtime]"),
    ],
)
def test_other_runtime_or_namespace_cannot_redirect_reconciliation(bound, field, value):
    job, root, services = bound
    services[field] = value
    (root / "run/services.json").write_text(json.dumps(services))
    assert L.endpoint_for(job) == job["fabro_url"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("FORGE_LRTX_PROFILE", "other-profile"),
        ("FORGE_LRTX_ROOT", "/other"),
        ("FORGE_FABRO_STORAGE", "/other/storage"),
        ("FORGE_FABRO_URL", "https://cloud.example/api/v1"),
        ("FORGE_FABRO_URL", "http://127.0.0.1:9999/api/v1"),
        ("FORGE_FABRO_URL", "http://secret@127.0.0.1:32391/api/v1"),
    ],
)
def test_environment_alone_cannot_select_a_new_server(bound, monkeypatch, key, value):
    job, _, _ = bound
    monkeypatch.setenv(key, value)
    assert L.endpoint_for(job) == job["fabro_url"]


@pytest.mark.parametrize("invalid", ["missing", "symlink", "writable", "bad-json", "unbound-data-root", "unbound-profile"])
def test_incomplete_or_mutable_context_keeps_original_hint(bound, tmp_path, invalid):
    job, root, _ = bound
    path = root / "run/services.json"
    if invalid == "missing":
        path.unlink()
    elif invalid == "symlink":
        outside = tmp_path / "services.json"
        path.rename(outside)
        path.symlink_to(outside)
    elif invalid == "writable":
        path.chmod(0o666)
    elif invalid == "bad-json":
        path.write_text("{")
    elif invalid == "unbound-data-root":
        job["native_context"].pop("FORGE_DATA_ROOT")
    else:
        job.pop("profile_initial_reservation")
    assert L.endpoint_for(job) == job["fabro_url"]


def test_new_jobs_with_explicit_profile_digest_use_the_same_native_binding(bound):
    job, _, _ = bound
    job["profile_sha256"] = job.pop("profile_initial_reservation")["profile_sha256"]
    assert L.endpoint_for(job) == "http://127.0.0.1:32391/api/v1"


def test_unmanaged_legacy_job_keeps_its_original_endpoint(monkeypatch):
    monkeypatch.delenv("FORGE_LRTX_PROFILE", raising=False)
    assert L.endpoint_for({"fabro_url": "http://127.0.0.1:32290"}) == "http://127.0.0.1:32290"
    assert L.endpoint_for({}) is None


def test_client_observation_identity_binds_route_and_network_namespace(monkeypatch):
    import httpx
    from forge_factory.fabro.client import FabroClient

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    with FabroClient("http://127.0.0.1:32391", transport=transport) as a:
        with FabroClient("http://127.0.0.1:32491", transport=transport) as b:
            assert a.observation_identity != b.observation_identity
        with FabroClient("http://127.0.0.1:32391/api/v1", transport=transport) as b:
            assert a.observation_identity == b.observation_identity
        monkeypatch.setattr(os, "readlink", lambda _: "net:[different]")
        with FabroClient("http://127.0.0.1:32391", transport=transport) as b:
            assert a.observation_identity != b.observation_identity


def test_different_endpoint_cannot_reuse_cached_native_failure(protocol, monkeypatch):
    import httpx
    from forge_factory.afo.execution_lifecycle import Executions
    from forge_factory.fabro.client import FabroClient

    p = protocol
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    ex.adopt(p.ctx.job_id, ["native-route-bound"])
    calls = []

    def failed(request):
        calls.append("host-only")
        raise httpx.ConnectError("unreachable private bridge", request=request)

    def actual(request):
        calls.append("native")
        return httpx.Response(200, json={"lifecycle": {"status": {"kind": "SUCCEEDED"}}})

    before = p.ledger.snapshot("mission-test")
    with FabroClient("http://127.0.0.1:32491", transport=httpx.MockTransport(failed)) as client:
        assert ex.reconcile(p.ctx.job_id, client)["resource_lease"] == "HELD"
        ex.reconcile(p.ctx.job_id, client)
    assert calls == ["host-only"]  # original durable backoff is preserved
    with FabroClient("http://127.0.0.1:32391", transport=httpx.MockTransport(actual)) as client:
        result = ex.reconcile(p.ctx.job_id, client)
    assert calls == ["host-only", "native"]
    assert result["resource_lease"] == "RELEASED" and result["task_outcome"] == "ACTIVE"
    assert p.ledger.snapshot("mission-test") == before
    with p.store.tx() as c:
        waits = c.execute("SELECT record FROM afo_dependency_waits WHERE scope=?", ("native:" + p.ctx.job_id,)).fetchall()
    assert len(waits) == 2 and {json.loads(r[0])["healthy"] for r in waits} == {True, False}
