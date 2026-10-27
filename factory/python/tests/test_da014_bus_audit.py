"""Native header provenance and finite bus visibility, not host qualification."""

import copy
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from types import SimpleNamespace

import pytest
from forge_factory.afo import bus_audit as B
from forge_factory.afo.durable import Refused


def line(kind="mc", *, at="100.000001", serial=2, sender=":1.2", destination=B.BUS,
         path="/org/freedesktop/DBus", interface=B.BUS, member="GetId", reply_serial=2):
    fields = [kind, at, str(serial), sender, destination]
    fields += [str(reply_serial)] if kind in ("mr", "err") else [path, interface, member]
    return ("\t".join(fields) + "\n").encode()


def proof_stream():
    out = B.Profile()
    out.feed(line("sig", sender=B.BUS, destination=":1.1", member="NameAcquired"))
    out.feed(line("sig", sender=B.BUS, destination=":1.1", member="NameLost", serial=3))
    out.feed(line())
    out.feed(line("mr", sender=B.BUS, destination=":1.2", serial=4))
    probe = {"returncode": 0, "destination": ":1.2", "serial": 4, "reply_serial": 2, "value": "a" * 32}
    return out, probe


def test_native_profile_headers_chunking_and_exact_digest():
    raw = b"#type\ttimestamp\tserial\tsender\tdestination\tpath\tinterface\tmember\n#\t\t\t\t\tin_reply_to\n" + line()
    profile = B.Profile()
    for byte in raw:
        profile.feed(bytes([byte]))
    profile.finish()
    assert profile.rows[0]["member"] == "GetId"
    assert profile.sha.hexdigest() == hashlib.sha256(raw).hexdigest()
    assert profile.size == len(raw)


@pytest.mark.parametrize("raw", [
    b"mc\t100.000001\t0\t:1.2\torg.freedesktop.DBus\t/\torg.freedesktop.DBus\tGetId\n",
    line(at="nan"), line(at="-1.000001"), line(serial=2**32), line(sender="spoofed"),
    line(destination="bad destination"), line(path="/has-dash"), line(interface="invalid"),
    line(member="private\nmc\t100"), line("mr", reply_serial=0), line("mr", reply_serial=2**32),
    b"   string \"DO-NOT-LOG\"\n", b"method call time=100 sender=:1.2\n", b"#unknown-header\n", b"\xff\n",
    line()[:-1], b"x" * 4097 + b"\n",
])
def test_malformed_headers_classic_bodies_and_unbounded_values_are_refused(raw):
    with pytest.raises(Refused):
        B.profile_line(raw)


def test_stream_bounds_and_truncation_never_establish_visibility(monkeypatch):
    p = B.Profile()
    p.feed(line()[:-1])
    with pytest.raises(Refused, match="TRUNCATION"):
        p.finish()
    monkeypatch.setattr(B.observer, "MAX_BYTES", 20)
    with pytest.raises(Refused, match="OUTPUT_BOUND"):
        B.Profile().feed(line())
    monkeypatch.setattr(B.observer, "MAX_BYTES", 99999)
    monkeypatch.setattr(B, "MAX_MESSAGES", 1)
    with pytest.raises(Refused, match="MESSAGE_BOUND"):
        B.Profile().feed(line() + line())


def test_monitor_name_loss_and_exact_third_party_call_reply_are_required():
    stream, probe = proof_stream()
    assert stream.monitor_identity() == ":1.1" and stream.proves(probe)
    for field, value in [("serial", 99), ("reply_serial", 99), ("destination", ":1.99"), ("returncode", 1)]:
        assert not stream.proves({**probe, field: value})
    stream.rows = [r for r in stream.rows if r.get("member") != "NameLost"]
    assert stream.monitor_identity() is None
    # Observing ordinary messages/eavesdropping without losing a unique name is insufficient.
    assert stream.proves(probe)


def test_spoofed_monitor_sender_missing_calls_duplicates_and_backward_clock_fail():
    stream, probe = proof_stream()
    stream.rows[1]["sender"] = ":1.50"
    assert stream.monitor_identity() is None
    stream.rows.pop(2)
    assert not stream.proves(probe)
    stream, probe = proof_stream()
    stream.rows.append(copy.deepcopy(stream.rows[-1]))
    assert not stream.proves(probe)
    stream, probe = proof_stream()
    stream.rows[-1]["at"] = 50
    assert not stream.proves(probe)


@pytest.mark.parametrize("seconds", [0, -1, 31, float("nan"), float("inf"), True, "1"])
def test_duration_is_bounded_before_processes_start(seconds):
    with pytest.raises(Refused, match="DURATION"):
        B.source(seconds=seconds)


def test_scope_and_local_address_validation_prevent_autolaunch_and_network(monkeypatch):
    with pytest.raises(Refused, match="SCOPE"):
        B.environment("other")
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    assert B.environment("user")["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path=/run/user/{os.getuid()}/bus"
    for address in ("autolaunch:", "tcp:host=remote", "unix:path=/x;tcp:host=y", "unix:path=/x\n"):
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", address)
        with pytest.raises(Refused, match="LOCAL_ADDRESS"):
            B.environment("user")
    assert set(B.environment("system")) == {"PATH", "LC_ALL"}


def test_tools_absence_never_becomes_empty_host_success(monkeypatch):
    monkeypatch.setattr(B.shutil, "which", lambda *a, **k: None)
    rec = B.source(seconds=0.1)
    assert rec["status"] == "BLOCKED" and "BUS_AUDIT_TOOLS_UNAVAILABLE" in rec["blockers"]
    assert rec["unexpected_interventions"] is None and rec["boundary_visibility"] == []


def test_query_allowlist_does_not_accept_service_commands():
    with pytest.raises(Refused, match="NOT_READ_ONLY"):
        B._query("/usr/bin/dbus-send", "user", {}, "RestartUnit")


@pytest.mark.parametrize("name", [":1.2", ":1.ABC", ":Upper_case.part-two", ":0._", ":" + "a" * 250 + ".xyz"])
def test_protocol_valid_unique_names_in_headers_and_native_query_replies(monkeypatch, name):
    assert B.profile_line(line(sender=name))["sender"] == name
    raw = (f'method return time=100.000001 sender=org.freedesktop.DBus -> destination={name} '
           f'serial=3 reply_serial=2\n   string "{name}"\n').encode()

    def run(argv, **kwargs):
        kwargs["stdout"].write(raw)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(B.subprocess, "run", run)
    result = B._query("/usr/bin/dbus-send", "user", B.environment("user"), "GetNameOwner")
    assert result["returncode"] == 0 and result["value"] == result["destination"] == name


@pytest.mark.parametrize("name", ["1.2", ":one", ":1..two", ":1./two", ":1.\ntwo", ":" + "a" * 251 + ".xyz"])
def test_malformed_and_oversized_unique_names_do_not_gain_visibility(name):
    with pytest.raises(Refused):
        B.profile_line(line(sender=name))


def test_bus_name_hyphens_are_not_interface_name_characters():
    assert B.profile_line(line(destination="-valid.name"))["destination"] == "-valid.name"
    with pytest.raises(Refused):
        B.profile_line(line(interface="invalid.hyphen-name"))


def test_name_grammar_matches_independent_native_libdbus_oracle():
    try:
        lib = ctypes.CDLL("libdbus-1.so.3")
    except OSError:
        pytest.skip("native libdbus name oracle unavailable")
    for function in (lib.dbus_validate_bus_name, lib.dbus_validate_interface):
        function.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        function.restype = ctypes.c_int
    names = [":1.ABC", ":Upper_case.part-two", ":0._", ":1..two", ":1./two", ":one", ":" + "a" * 250 + ".xyz",
             ":" + "a" * 251 + ".xyz", "-valid.name", "valid.Name", "invalid-name.part", "invalid.hyphen-name"]
    for name in names:
        assert bool(B.UNIQUE.fullmatch(name) or B.NAME.fullmatch(name)) == bool(lib.dbus_validate_bus_name(name.encode(), None))
        assert bool(B.INTERFACE.fullmatch(name)) == bool(lib.dbus_validate_interface(name.encode(), None))


@pytest.mark.parametrize("serial", [0, 2**32])
def test_query_reply_serials_are_uint32_not_unbounded_text(monkeypatch, serial):
    raw = (f'method return time=100.000001 sender=org.freedesktop.DBus -> destination=:1.2 '
           f'serial={serial} reply_serial=2\n   string "' + "a" * 32 + '"\n').encode()

    def run(argv, **kwargs):
        kwargs["stdout"].write(raw)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(B.subprocess, "run", run)
    assert B._query("/usr/bin/dbus-send", "user", B.environment("user"), "GetId")["error"]


@pytest.fixture
def native_bus(tmp_path, monkeypatch):
    if not all(shutil.which(t, path=B.PATH) for t in ("dbus-daemon", "dbus-monitor", "dbus-send")):
        pytest.skip("native D-Bus utilities unavailable")
    # Abstract Unix sockets avoid the 108-byte pathname limit and create no files.
    # Subprocess temporary files stay under the caller's approved basetemp.
    address = "unix:abstract=forge014-" + uuid.uuid4().hex
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--address=" + address, "--print-address=1"],
                              cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    import selectors

    with selectors.DefaultSelector() as poller:
        poller.register(daemon.stdout, selectors.EVENT_READ)
        assert poller.select(2), "isolated bus did not start"
        assert daemon.stdout.readline().startswith(address.encode())
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", address)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    try:
        yield tmp_path
    finally:
        daemon.terminate()
        daemon.wait(timeout=2)
        daemon.stdout.close()


def test_native_isolated_bus_proves_monitor_and_both_boundaries_without_systemd(native_bus):
    rec = B.source(seconds=0.1)
    assert rec["monitor_identity"] and rec["boundary_visibility"] == [True, True], rec
    assert rec["blockers"] == ["BUS_AUDIT_SYSTEMD_OWNER_UNKNOWN_OR_CHANGED"]
    assert rec["systemd_owners"] == [None, None] and rec["unexpected_interventions"] is None
    assert rec["coverage"] == "NOT_CONTINUOUS_OR_ACTOR_VERIFIED"
    assert not any("body" in r or "arguments" in r for r in rec["messages"])
    replay = B.Profile()
    replay.feed(rec["header_profile"].encode("ascii"))
    replay.finish()
    assert replay.rows == rec["messages"] and replay.sha.hexdigest() == rec["stream_sha256"]


def test_native_bus_denial_or_disconnect_is_blocked_not_zero(native_bus, monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=" + str(native_bus / "missing"))
    rec = B.source(seconds=0.1)
    assert rec["status"] == "BLOCKED" and rec["unexpected_interventions"] is None
    assert "BUS_AUDIT_BOUNDARY_VISIBILITY_NOT_PROVEN" in rec["blockers"]


@pytest.mark.parametrize("exit_early", [True, False])
def test_monitor_clean_exit_or_eavesdrop_fallback_is_blocked_and_private(native_bus, monkeypatch, exit_early):
    real_popen = subprocess.Popen
    children = []

    def popen(argv, **kwargs):
        if argv[0].endswith("dbus-monitor"):
            # Emulate a denied BecomeMonitor/fallback without touching bus policy.
            code = "import os,time;os.write(2,b'PRIVATE-FALLBACK-REASON');time.sleep(" + ("0.01" if exit_early else "10") + ")"
            child = real_popen([sys.executable, "-c", code], **kwargs)
            children.append(child)
            return child
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(B.subprocess, "Popen", popen)
    rec = B.source(seconds=0.1)
    assert rec["status"] == "BLOCKED" and rec["unexpected_interventions"] is None
    assert "BUS_AUDIT_MONITOR_DIAGNOSTIC_OR_FALLBACK" in rec["blockers"]
    assert "PRIVATE-FALLBACK-REASON" not in json.dumps(rec)
    assert all(child.poll() is not None for child in children)
    if exit_early:
        assert "BUS_AUDIT_MONITOR_EXITED" in rec["blockers"]


def test_native_service_manager_and_unit_calls_are_preserved_with_unknown_actor(native_bus):
    system_python = "/usr/bin/python3"
    check = subprocess.run([system_python, "-c", "import dbus.service; from gi.repository import GLib"],
                           capture_output=True, timeout=2)
    if check.returncode:
        pytest.skip("optional system Python D-Bus integration harness unavailable")
    script = r'''
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
name = dbus.service.BusName('org.freedesktop.systemd1', bus)
class Manager(dbus.service.Object):
 @dbus.service.method('org.freedesktop.systemd1.Manager', in_signature='s', out_signature='o')
 def GetUnit(self, unit): return '/org/freedesktop/systemd1/unit/fake_2eservice'
class Unit(dbus.service.Object):
 @dbus.service.method('org.freedesktop.systemd1.Unit', in_signature='', out_signature='s')
 def Start(self): return 'DO-NOT-EXPORT\nmc\t100.000001\t1\t:1.99'
manager = Manager(bus, '/org/freedesktop/systemd1')
unit = Unit(bus, '/org/freedesktop/systemd1/unit/fake_2eservice')
print('READY', flush=True)
GLib.MainLoop().run()
'''
    service = subprocess.Popen([system_python, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env={**os.environ, "DBUS_SESSION_BUS_ADDRESS": B.environment("user")["DBUS_SESSION_BUS_ADDRESS"]})
    calls = []
    errors = []
    try:
        # Fixed test service initialization, finite readiness deadline.
        import selectors

        with selectors.DefaultSelector() as poller:
            poller.register(service.stdout, selectors.EVENT_READ)
            assert poller.select(2), "fake service failed to initialize"
            assert service.stdout.readline() == b"READY\n"

        def invoke():
            try:
                time.sleep(0.25)
                for path, method, args in [
                    (B.ROOT, B.SYSTEMD + ".Manager.GetUnit", ["string:fake.service"]),
                    (B.ROOT + "/unit/fake_2eservice", B.SYSTEMD + ".Unit.Start", []),
                ]:
                    r = subprocess.run(["dbus-send", "--session", "--print-reply", "--reply-timeout=1000",
                                        "--dest=" + B.SYSTEMD, path, method, *args],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    calls.append(r.returncode)
            except Exception as exc:  # propagate worker failure into the parent assertion
                errors.append(type(exc).__name__)

        worker = threading.Thread(target=invoke)
        worker.start()
        try:
            rec = B.source(seconds=0.7)
        finally:
            worker.join(timeout=5)
        assert not worker.is_alive() and not errors and calls == [0, 0]
        assert rec["status"] == "BUS_VISIBILITY_AND_HEADERS_CAPTURED", rec
        assert {r["member"] for r in rec["service_requests"]} == {"GetUnit", "Start"}
        assert all(r["actor"] is None and r["effect"] == "UNKNOWN" for r in rec["service_requests"])
        assert "DO-NOT-EXPORT" not in json.dumps(rec) and ":1.99" not in json.dumps(rec)
        assert rec["unexpected_interventions"] is None
    finally:
        service.terminate()
        service.wait(timeout=2)
        service.stdout.close()
