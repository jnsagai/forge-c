"""Recover lost gateway replies using real PID namespaces and durable ledgers.

No Qwen, GPU, service manager or installed stack is used.
"""

import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from forge_factory.afo import operations, provider_recovery
from forge_factory.afo.completion_receipt import Receipts
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.lrtx import provider_process as P, stack
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401
from test_da014_provider_process import provider


def dispatched(p, instance=None, *, sent=True):
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    ex.adopt(p.ctx.job_id, ["native-A"])
    p.ledger.reserve_request(
        "mission-test",
        p.ctx.job_id,
        "lost-reply",
        body_sha256="a" * 64,
        input_tokens=100,
        output_cap=10,
        authorize=lambda: True,
        provider_instance=instance,
    )
    if sent:
        p.ledger.start_request("lost-reply", authorize=lambda: True)
        p.ledger.reconcile_request("lost-reply", quiescent=False)
    return ex


def managed(p, instance, tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    intent = operations.Intent(tmp_path / "intent.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", "fixture")
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    intent.set("RUNNING", actor="owner", reason="kernel fixture", initialize=True)
    monkeypatch.setattr(operations, "operational_authorized", lambda *a: True)
    monkeypatch.setattr(stack, "settings", lambda _: {"root": tmp_path})
    monkeypatch.setattr(stack, "serving_instance", lambda _: instance)
    calls = []
    monkeypatch.setattr(stack, "_start", lambda *a, **kw: calls.append(kw) or {"health": {"fabro": True}})
    return intent, calls


def test_lost_gateway_reply_retirement_preserves_receipt_spend_and_native_lease(protocol, tmp_path):
    p = protocol
    with provider(tmp_path, "serving") as instance, provider(tmp_path, "benchmark") as other:
        ex = dispatched(p, instance)
        receipt = Receipts(p.store).submit(p.ctx, p.proposal)
        before = p.ledger.snapshot("mission-test")
        proof = provider_recovery.reconcile(p.store, p.ctx.job_id, instance, retire=True, fenced_effect=lambda f: f())
        assert proof["ok"] and P.quiet(instance) and P.quiet(other) is None
        assert ex.get(p.ctx.job_id)["resource_lease"] == "HELD"
        assert Receipts(p.store).latest(receipt["receipt_id"]) == receipt
        after = p.ledger.snapshot("mission-test")
        assert after["charged_tokens"] == before["charged_tokens"] and after["usage_unknown"]
        with p.store.tx() as c:
            request = json.loads(c.execute("SELECT record FROM afo_request_ledger WHERE request_id='lost-reply'").fetchone()[0])
        assert request["state"] == "QUIESCENT" and request["reported_tokens"] is None
        with pytest.raises(Refused, match="GENERATION_RETIREMENT_FENCED"):
            p.ledger.reserve_request(
                "mission-test",
                p.ctx.job_id,
                "late-retry",
                body_sha256="b" * 64,
                input_tokens=1,
                output_cap=1,
                authorize=lambda: True,
            )
        active = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "RUNNING"}}})
        assert ex.reconcile(p.ctx.job_id, active)["resource_lease"] == "HELD"
        terminal = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}})
        assert ex.reconcile(p.ctx.job_id, terminal)["resource_lease"] == "RELEASED"


def test_reserved_gateway_send_is_fenced_before_provider_retirement(protocol, tmp_path):
    p = protocol
    with provider(tmp_path, "queued") as instance:
        dispatched(p, instance, sent=False)

        def fence_before_signal(effect):
            with pytest.raises(Refused, match="GENERATION_RETIREMENT_FENCED"):
                p.ledger.start_request("lost-reply", authorize=lambda: True)
            effect()

        assert provider_recovery.reconcile(p.store, p.ctx.job_id, instance, retire=True, fenced_effect=fence_before_signal)["ok"]


def test_legacy_request_is_not_retroactively_bound_or_signaled(protocol, tmp_path):
    p = protocol
    with provider(tmp_path, "legacy") as instance:
        dispatched(p)
        result = provider_recovery.reconcile(
            p.store, p.ctx.job_id, instance, retire=True, fenced_effect=lambda _: pytest.fail("legacy request reached signal")
        )
        assert result["code"] == "REQUEST_PROVIDER_LIFETIME_UNPROVEN" and P.quiet(instance) is None
        assert Executions(p.store)._evidence(p.ctx.job_id, "GENERATION_FENCE") is None


def test_watchdog_preserves_active_request_and_defers_inside_namespace(protocol, tmp_path, monkeypatch):
    p = protocol
    with provider(tmp_path, "active") as instance:
        dispatched(p, instance)
        _, calls = managed(p, instance, tmp_path, monkeypatch)
        assert operations.recover_profile(p.store)["action"] == "WAIT_FOR_EXTERNAL_WATCHDOG"
        result = operations.recover_profile(p.store, external=True)
        assert result["result"]["code"] == "ACTIVE_PROVIDER_PRESERVED"
        assert P.quiet(instance) is None and calls == [{"recovery": True, "control_only": True}]


def test_native_terminal_recovers_only_fabro_until_lease_reconciliation(protocol, tmp_path, monkeypatch):
    p = protocol
    with provider(tmp_path, "terminal") as instance:
        ex = dispatched(p, instance)
        terminal = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}})
        assert ex.reconcile(p.ctx.job_id, terminal)["resource_lease"] == "HELD"
        _, calls = managed(p, instance, tmp_path, monkeypatch)
        result = operations.recover_profile(p.store, external=True)
        assert result["result"]["provider"]["ok"] and P.quiet(instance)
        assert calls == [{"recovery": True, "control_only": True}]
        assert ex.get(p.ctx.job_id)["resource_lease"] == "HELD"
        assert ex.reconcile(p.ctx.job_id, terminal)["resource_lease"] == "RELEASED"


def test_newer_stop_prevents_watchdog_signal_and_restart(protocol, tmp_path, monkeypatch):
    p = protocol
    with provider(tmp_path, "stop") as instance:
        ex = dispatched(p, instance)
        ex.outcome(p.ctx.job_id, "BLOCKED", "fixture timeout")
        intent, calls = managed(p, instance, tmp_path, monkeypatch)

        def stop_during_authorization(*args):
            intent.set("STOPPED", actor="owner", reason="newer stop")
            return True

        monkeypatch.setattr(operations, "operational_authorized", stop_during_authorization)
        result = operations.recover_profile(p.store, external=True)
        assert result["result"]["code"] == "OPERATIONS_START_FENCED"
        assert P.quiet(instance) is None and not calls


def test_authenticated_shutdown_retires_provider_without_restart(protocol, tmp_path, monkeypatch):
    p = protocol
    with provider(tmp_path, "shutdown") as instance:
        ex = dispatched(p, instance)
        intent, calls = managed(p, instance, tmp_path, monkeypatch)
        intent.set("STOPPED", actor="owner", reason="requested shutdown")
        active = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "RUNNING"}}}, cancel=lambda _: 202)
        assert operations.settle_shutdown(p.store, client=active)["code"] == "WAIT_FOR_EXTERNAL_WATCHDOG"
        assert P.quiet(instance) is None
        assert not operations.settle_shutdown(p.store, client=active, external=True)["settled"]
        assert P.quiet(instance) and not calls and ex.get(p.ctx.job_id)["resource_lease"] == "HELD"
        terminal = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "CANCELLED"}}})
        # Observe the next bounded native-status probe without sleeping.
        with p.store.tx() as c:
            c.execute("UPDATE afo_dependency_waits SET next_probe=0")
        assert operations.settle_shutdown(p.store, client=terminal, external=True)["settled"]
        assert operations.settle_shutdown(p.store)["settled"]
        assert intent.read()["effective_stop"] and not calls


def test_serving_reference_rejects_mutation_and_unsafe_permissions(tmp_path):
    with provider(tmp_path, "reference") as instance:
        root = tmp_path / "reference"
        (root / "run").mkdir()
        immutable_json(root / "run/provider-instances" / (digest(instance) + ".json"), instance)
        stack._save_services(root, {"serving_instance": instance})
        settings = {"root": root, "profile": {"id": "fixture", "_sha256": "a" * 64}}
        assert stack.serving_instance(settings) == instance
        (root / "run/services.json").chmod(0o666)
        with pytest.raises(Refused, match="SERVING_INSTANCE_REFERENCE_INVALID"):
            stack.serving_instance(settings)


def test_stack_gateway_entry_and_delayed_producer_share_retired_namespace(tmp_path):
    with provider(tmp_path, "topology", network=True) as instance:
        root = tmp_path / "topology"
        (root / "run").mkdir()
        immutable_json(root / "run/provider-instances" / (digest(instance) + ".json"), instance)
        stack._save_services(root, {"serving_instance": instance})
        ready, late = root / "gateway-ready.json", root / "late-send"
        # Enter through the production adapter, including user/net/mount/PID
        # namespaces. A queued producer must die with the same model island.
        code = (
            "import os,json,time; from pathlib import Path; "
            "from forge_factory.lrtx import stack; "
            "from forge_factory.afo.provider_recovery import current_instance; "
            f"stack.settings=lambda _:{{'root':Path({str(root)!r}),'profile':{{'id':'fixture','_sha256':{'a' * 64!r}}}}}; "
            f"Path({str(ready)!r}).write_text(json.dumps({{'instance':current_instance(),'namespace':os.readlink('/proc/self/ns/pid')}})); "
            f"time.sleep(30); Path({str(late)!r}).write_text('provider send')"
        )
        env = {
            **os.environ,
            "FORGE_OPERATIONS_INTENT": str(root / "intent.json"),
            "FORGE_OPERATIONS_PROFILE": "fixture",
            "FORGE_DURABLE_AUTONOMY": "1",
        }
        proc = stack._in_ns(
            instance["parent_pid"], [sys.executable, "-c", code], env, root / "gateway-entry.log", root, serving=instance
        )
        try:
            until = time.monotonic() + 3
            while not ready.exists() and proc.poll() is None and time.monotonic() < until:
                time.sleep(0.02)
            assert ready.exists(), (root / "gateway-entry.log").read_text()
            record = json.loads(ready.read_text())
            assert record["instance"] == instance and record["namespace"] == instance["init"]["pid_namespace"]
            assert P.stop(instance, fenced_effect=lambda effect: effect())
            proc.wait(timeout=3)
            assert proc.returncode != 0 and not late.exists()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)


def test_shutdown_effects_finish_before_newer_resume(protocol, tmp_path, monkeypatch):
    p = protocol
    dispatched(p)
    tmp_path.chmod(0o700)
    intent = operations.Intent(tmp_path / "race-intent.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    stopped = intent.set("STOPPED", actor="owner", reason="race fixture", initialize=True)
    entered, release, resuming = threading.Event(), threading.Event(), threading.Event()

    def observe(_):
        entered.set()
        assert release.wait(3)
        return {"lifecycle": {"status": {"kind": "FAILED"}}}

    def resume():
        resuming.set()
        return intent.set("RUNNING", actor="owner", reason="newer resume")

    with ThreadPoolExecutor(max_workers=2) as pool:
        shutdown = pool.submit(operations.settle_shutdown, p.store, client=SimpleNamespace(get_run=observe))
        try:
            assert entered.wait(3)
            resumed = pool.submit(resume)
            assert resuming.wait(3)
            assert not resumed.done()
        finally:
            release.set()
        assert not shutdown.result(timeout=3)["settled"]
        assert resumed.result(timeout=3)["epoch"] == stopped["epoch"] + 1
    assert intent.read()["mode"] == "RUNNING" and not intent.read()["effective_stop"]


def test_managed_stop_rejects_other_profile_before_effects(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(tmp_path / "intent.json"))
    monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", "approved-profile")
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    monkeypatch.setattr(operations, "synchronize", lambda *a: pytest.fail("scope mismatch reached intent write"))
    with pytest.raises(Refused, match="MANAGED_PROFILE_SCOPE_MISMATCH"):
        stack.stop({"root": tmp_path, "profile": {"id": "other-benchmark"}})


def test_external_watchdog_settles_stop_even_with_healthy_conductor(protocol, tmp_path, monkeypatch):
    from forge_factory.afo import watchdog, host, queue

    tmp_path.chmod(0o700)
    intent = operations.Intent(tmp_path / "healthy-stop.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    intent.set("STOPPED", actor="owner", reason="pending external stop", initialize=True)
    monkeypatch.setattr(watchdog, "check", lambda _: {"ok": True, "code": "HEALTHY"})
    monkeypatch.setattr(host, "preflight", lambda: {"ok": True})
    monkeypatch.setattr(queue, "Store", lambda: protocol.store)
    calls = []
    monkeypatch.setattr(operations, "recover", lambda: calls.append("settle") or {"action": "STOP_SETTLEMENT"})
    monkeypatch.setattr(operations, "recover_profile", lambda store, **kw: calls.append(kw) or {"action": "WAITING"})
    assert watchdog.main([]) == 0
    assert calls == ["settle", {"external": True}]


@pytest.mark.parametrize("reused", ["boot_id", "start_ticks"])
def test_recovery_forgets_ended_holder_without_signaling_reused_pid(tmp_path, monkeypatch, reused):
    (tmp_path / "venv/bin").mkdir(parents=True)
    (tmp_path / "venv/bin/python").touch()
    (tmp_path / "run").mkdir()
    pid = os.getpid()
    original = stack.process_identity(pid)
    old = {**original, reused: "old-boot" if reused == "boot_id" else "0"}
    (tmp_path / "run/holder.pid").write_text(str(pid))
    stack._save_services(tmp_path, {"holder_identity": old, "processes": {}})
    monkeypatch.setattr(stack, "_holder", lambda _: pid)
    monkeypatch.setattr(stack, "envmap", lambda _: {})
    monkeypatch.setattr(os, "kill", lambda *a: pytest.fail("recovery signaled a reused PID"))
    effects = []

    class FreshNamespaceRequested(Exception):
        pass

    def launch(argv, **kwargs):
        effects.append(argv)
        assert not (tmp_path / "run/holder.pid").exists()
        raise FreshNamespaceRequested

    monkeypatch.setattr(stack.subprocess, "Popen", launch)
    with pytest.raises(FreshNamespaceRequested):
        stack._start({"root": tmp_path, "ports": {}, "profile": {}}, recovery=True)
    assert len(effects) == 1 and effects[0][:2] == ["setsid", "unshare"]
    assert stack.process_identity(pid) == original


def test_same_process_with_changed_namespace_is_not_treated_as_ended():
    original = stack.process_identity(os.getpid())
    changed = {**original, "netns": "net:[different]"}
    assert not stack._pinned_process_ended(original, changed)
    assert not stack._pinned_process_ended(None, original)
