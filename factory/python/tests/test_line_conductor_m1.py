"""Autonomous line M1 (owner 2026-11-03): the Line Conductor in OBSERVE mode, the issues feed
forge-c/supervisor-issues/1, the read-only floor station and the audited owner ack CLI.

The fixtures mirror the Omniverse2 records of 2026-11-03 (gate-log lines, launch records, Fabro statuses); the
classification replay over a read-only copy of that line state runs when FORGE_M1_REPLAY_DIR names the copy."""
from __future__ import annotations

import json
import os
import shutil
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from forge_factory.afo import cli as afo_cli
from forge_factory.afo import line_conductor as LC
from forge_factory.common import REPO_ROOT

pytestmark = pytest.mark.skipif(not LC.SCHEMA_PATH.is_file(), reason="supervisor-issues contract not in this checkout")

T0 = time.time() - 3 * 3600
IWDG = "WO-F014-SWE{n}-IWDGHAL-20261103-L{l}"
STUCK_ISSUES = ["MISSING_REQUIRED_OUTPUT:workproducts/SWE.6/software_verification_report.md", "REQUIRED_TOOL_NOT_PASS:run_robot:FAIL",
                "VT:TEST_WITHOUT_TRACE:PERF", "VT:SWR_NOT_VERIFIED:SWR-007"]
PROSE = "MARKER-PROSE-7f3: I think the robot test was flaky so I skipped the report, please retry"


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime(t))


def mk_order(root: Path, wo: str, *, gates=(), package=False, rid=None, source=None, stop_after="SWE.1", created=T0,
             inspection=None):
    ws = root / "workorders" / wo / "workspace"
    run = ws / ".forge-run"
    (run / "gates").mkdir(parents=True)
    man = {"work_order": wo, "created_at": _iso(created), "driver": "STM32N6 IWDG HAL driver",
           "phase_scope": {"stop_after": stop_after}, "factory_revision": {"commit": "dcfec5b0", "basis": "recorded_at_launch"}}
    if source:
        man["resumed_from"] = {"source_work_order": source, "restart_phase": stop_after}
    (run / "manifest.json").write_text(json.dumps(man))
    (run / "gates/gate-log.jsonl").write_text("".join(json.dumps({**g, "ts": _iso(created + 60 * (i + 1))}) + "\n"
                                                      for i, g in enumerate(gates)))
    if package:
        (run / "package.json").write_text(json.dumps({"package_status": "BLOCKED", "gaps": ["run_not_completed:INCOMPLETE"]}))
    if rid:
        (run / "fabro_run_id").write_text(rid)
    if inspection:
        d = ws / "inspection" / stop_after
        d.mkdir(parents=True)
        (d / "INS-SWE.6-001.json").write_text(json.dumps(inspection))
    return ws


def passed(phase):
    return [{"phase": phase, "step": "author", "result": "FROZEN"}, {"phase": phase, "step": "inspect", "gate": {"decision": "PASS"}}]


STUCK = [{"phase": "SWE.6", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": STUCK_ISSUES},
         {"phase": "SWE.6", "step": "route", "gate": {"decision": "REWORK", "reason": "NO_BASELINE"}},
         {"phase": "SWE.6", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": STUCK_ISSUES},
         {"phase": "SWE.6", "step": "route", "gate": {"decision": "BLOCKED", "reason": "STUCK: identical deterministic rejection "
                                                                                    "twice (MISSING_REQUIRED_OUTPUT); stopped early"}}]


def launch_log(d: Path, wo: str, lines: list[str], workorder_log: str | None = None):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"launch-{wo}.out").write_text("\n".join(lines) + "\n")
    if workorder_log is not None:
        (d / f"workorder-launch-{wo}.log").write_text(workorder_log)


@pytest.fixture
def line(tmp_path, monkeypatch):
    """The 2026-11-03 Omniverse2 situation before the L24 retries."""
    state, launch = tmp_path / "state", tmp_path / "launch"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.delenv("FORGE_FLOOR_SUPERVISOR_FEED", raising=False)
    for n in range(1, 5):
        mk_order(state, IWDG.format(n=n, l=19), gates=passed(f"SWE.{n}"), package=True, rid=f"01RUNL19SWE{n}",
                 source=IWDG.format(n=n - 1, l=19) if n > 1 else None, stop_after=f"SWE.{n}", created=T0 + n * 60)
    mk_order(state, IWDG.format(n=5, l=22), gates=passed("SWE.5"), package=True, rid="01RUNL22SWE5",
             source=IWDG.format(n=4, l=19), stop_after="SWE.5", created=T0 + 3600)
    mk_order(state, IWDG.format(n=6, l=22), gates=STUCK, package=True, rid="01RUNL22SWE6", source=IWDG.format(n=5, l=22),
             stop_after="SWE.6", created=T0 + 4000,
             inspection={"verdict": "FAIL", "recorded_at": _iso(T0 + 4100), "findings": [{"id": "SWE6-03", "detail": PROSE}]})
    mk_order(state, "WO-F014-SWE1-RCC-20261102-L16", gates=passed("SWE.1"), package=True, rid="01RUNRCC1", created=T0 - 7200)
    mk_order(state, "WO-F014-SWE2-RCC-20261102-L16", rid="01RUNRCC2", source="WO-F014-SWE1-RCC-20261102-L16",
             stop_after="SWE.2", created=T0 - 3600)
    mk_order(state, "WO-F014-SWE6-CRCL-20261103-L24", gates=passed("SWE.6"), package=True, rid="01RUNCRCL6",
             stop_after="SWE.6", created=T0 + 5000)
    ts = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))  # noqa: E731
    launch_log(launch, IWDG.format(n=5, l=19), [f"{ts(T0 + 1000)} CODE dcfec5b0 run branch", f"{ts(T0 + 1001)} STACK STOP (own root)",
                                                f"{ts(T0 + 1002)} OWN llama-server still running after stop",
                                                f"{ts(T0 + 1050)} STACK START (p) rc 1"])
    launch_log(launch, IWDG.format(n=5, l=21), [f"{ts(T0 + 1200)} STACK START (p) rc 0",
                                                f'{ts(T0 + 1800)} STACK NOT HEALTHY: {{"health": {{"fabro": false}}}}'])
    launch_log(launch, IWDG.format(n=5, l=22), [f'{ts(T0 + 3590)} LAUNCH {IWDG.format(n=5, l=22)} rc 0: {{"work_order": '
                                                f'"{IWDG.format(n=5, l=22)}", "fabro_run_id": "01RUNL22SWE5"}}'])
    launch_log(launch, "WO-F014-SWE1-CRCHAL-20261103-L24", [f"{ts(T0 + 5100)} STACK HEALTHY: {{}}",
                                                             f"{ts(T0 + 5110)} LAUNCH WO-F014-SWE1-CRCHAL-20261103-L24 rc 1: "
                                                             "Traceback ... FileNotFoundError: PROVIDED_"],
               "Traceback (most recent call last):\n  File \"workorder.py\", line 148, in provided_ll\n"
               "FileNotFoundError: PROVIDED_LL_MISSING:WO-F014-SWE6-CRCL-20261103-L24::no work order workspace\n")
    snap = {"01RUNRCC2": "failed:cancelled", "01RUNL22SWE6": "succeeded:completed"}
    return {"state": state, "launch": launch, "fabro": LC.FabroView(snapshot=snap), "tmp": tmp_path}


def conductor(line, **kw) -> LC.LineConductor:
    return LC.LineConductor(LC.Observer("local", line["launch"], line["fabro"], lookback_s=10 * 86400, **kw), unit="test.service")


def by_wo(feed, wo):
    return next(i for i in feed["issues"] if i["wo"] == wo)


# ------------------------------------------------------------------------------------------------ the feed
def test_generated_feed_validates_against_the_contract(line):
    feed = conductor(line).cycle()
    assert LC.feed_errors(feed) == []
    disk = json.loads(LC.feed_path().read_text())
    assert disk == feed and disk["schema"] == "forge-c/supervisor-issues/1" and disk["supervisor"]["mode"] == "OBSERVE"
    assert set(disk["budgets"]) == set(LC.BUDGETS) and disk["budgets"]["convergence_retries_per_phase"]["limit"] == 2
    assert disk["budgets"]["planner_tokens_per_order"]["limit"] == 200_000 and disk["budgets"]["phase_order_wall_s"]["limit"] == 21600
    journal = [json.loads(x) for x in LC.journal_path().read_text().splitlines()]
    assert {j["event"] for j in journal} == {"OPENED"} and len(journal) == len(feed["issues"])


def test_the_feed_write_is_atomic(line, monkeypatch):
    lc = conductor(line)
    first = lc.cycle()
    before = LC.feed_path().read_bytes()
    seen = []
    real = os.replace

    def replace(src, dst):  # the new feed is complete and valid before it takes the feed's name
        seen.append(json.loads(Path(src).read_text()))
        assert LC.feed_errors(seen[-1]) == []
        raise OSError("crash at the rename")

    monkeypatch.setattr(LC.os, "replace", replace)
    with pytest.raises(OSError):
        lc.cycle(time.time() + 30)
    assert LC.feed_path().read_bytes() == before  # a crash leaves the previous feed whole
    monkeypatch.setattr(LC.os, "replace", real)
    lc.cycle(time.time() + 60)
    assert json.loads(LC.feed_path().read_text())["supervisor"]["cycle"] == first["supervisor"]["cycle"] + 1
    assert not [p for p in LC.supervisor_dir().iterdir() if p.name.endswith(".tmp")]


def test_classification_of_the_2026_11_03_situation(line):
    feed = conductor(line).cycle()
    stuck = by_wo(feed, IWDG.format(n=6, l=22))
    assert (stuck["class"], stuck["status"], stuck["phase"]) == ("MODEL_CONVERGENCE", "OPEN", "SWE.6")
    assert stuck["lineage"] == "IWDGHAL/" + IWDG.format(n=1, l=19) and stuck["attempts"] == {"used": 0, "limit": 2}
    first = stuck["proposals"][0]
    assert (first["source"], first["status"], first["strategy"]) == ("RULE", "PROPOSED", "RETRY_PHASE_FROM_LAST_PASSED_ORDER")
    assert first["summary"] == f"retry SWE.6 from {IWDG.format(n=5, l=22)}" and first["args"]["resume_from"] == IWDG.format(n=5, l=22)
    assert all(p["source"] == "RULE" and p["status"] == "PROPOSED" for p in stuck["proposals"])
    assert {e["kind"] for e in stuck["evidence"]} >= {"gate_log", "package", "fabro_run"}
    rcc = by_wo(feed, "WO-F014-SWE2-RCC-20261102-L16")
    assert (rcc["class"], rcc["status"], rcc["error_code"]) == ("UNKNOWN", "PARKED", "FABRO_RUN_CANCELLED")
    assert rcc["proposals"][0]["args"]["resume_from"] == "WO-F014-SWE1-RCC-20261102-L16"
    l19, l21 = by_wo(feed, IWDG.format(n=5, l=19)), by_wo(feed, IWDG.format(n=5, l=21))
    assert (l19["class"], l19["error_code"], l19["status"]) == ("INFRA", "STACK_STOP_INCOMPLETE", "RESOLVED")
    assert (l21["class"], l21["error_code"], l21["status"]) == ("INFRA", "READINESS_FAILURE", "RESOLVED")
    assert {"kind": "superseded_by", "ref": f"workorders/{IWDG.format(n=5, l=22)}"} in l19["evidence"]
    assert l19["proposals"][0]["strategy"] == "STACK_REPAIR_RECIPE" and l19["proposals"][0]["status"] == "SUPERSEDED"
    hal = by_wo(feed, "WO-F014-SWE1-CRCHAL-20261103-L24")
    assert (hal["class"], hal["error_code"], hal["status"]) == ("INFRA", "PROVIDED_LL_MISSING", "OPEN")
    p = hal["proposals"][0]
    assert p["strategy"] == "RELAUNCH_WITH_CORRECTED_PROVIDED_FROM" and p["args"]["provided_from"] == "WO-F014-SWE6-CRCL-20261103-L24"
    assert {e["ref"] for e in hal["evidence"]} >= {"launch:workorder-launch-WO-F014-SWE1-CRCHAL-20261103-L24.log#3"}
    assert not [i for i in feed["issues"] if i["wo"] and "SWE1-IWDGHAL" in i["wo"]]  # passed orders raise nothing


def test_a_later_passing_retry_resolves_and_a_relaunch_resolves_the_launch(line):
    lc = conductor(line)
    first = lc.cycle()
    mk_order(line["state"], IWDG.format(n=6, l=24), gates=passed("SWE.6"), package=True, rid="01RUNL24SWE6",
             source=IWDG.format(n=5, l=22), stop_after="SWE.6", created=T0 + 6000)
    mk_order(line["state"], "WO-F014-SWE1-CRCHAL-20261103-L25", rid="01RUNCRCHAL25", stop_after="SWE.1", created=T0 + 6100)
    feed = lc.cycle(time.time() + 30)
    stuck = by_wo(feed, IWDG.format(n=6, l=22))
    assert stuck["status"] == "RESOLVED" and stuck["opened_at"] == by_wo(first, IWDG.format(n=6, l=22))["opened_at"]
    assert {"kind": "superseded_by", "ref": f"workorders/{IWDG.format(n=6, l=24)}"} in stuck["evidence"]
    assert all(p["status"] == "SUPERSEDED" for p in stuck["proposals"])
    assert by_wo(feed, "WO-F014-SWE1-CRCHAL-20261103-L24")["status"] == "RESOLVED"
    assert [j["event"] for j in map(json.loads, LC.journal_path().read_text().splitlines())].count("RESOLVED") == 2  # the L22 STUCK and the CRCHAL launch


def test_resolved_issues_leave_the_feed_after_7_days_and_the_journal_keeps_them(line):
    lc = conductor(line)
    lc.cycle()
    n = len(LC.journal_path().read_text().splitlines())
    feed = lc.cycle(time.time() + 8 * 86400)
    assert not [i for i in feed["issues"] if i["status"] == "RESOLVED"]
    assert by_wo(feed, IWDG.format(n=6, l=22))["status"] == "OPEN"
    assert len(LC.journal_path().read_text().splitlines()) >= n


# --------------------------------------------------------------------------------------- zero model calls
class FakeFabro(BaseHTTPRequestHandler):
    hits: list = []

    def do_GET(self):  # noqa: N802
        FakeFabro.hits.append(self.path)
        data = json.dumps({"id": self.path.rsplit("/", 1)[-1], "lifecycle": {"status": {"kind": "running"}}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_a):
        pass


def _serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def test_a_healthy_cycle_makes_zero_model_calls_and_the_guard_is_measured(tmp_path, monkeypatch):
    from forge_factory.supervisor import service

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    mk_order(tmp_path / "state", IWDG.format(n=1, l=30), gates=passed("SWE.1"), package=True, rid="01DONE")
    mk_order(tmp_path / "state", IWDG.format(n=2, l=30), rid="01RUNNING", source=IWDG.format(n=1, l=30), stop_after="SWE.2",
             created=time.time() - 60)
    srv, port = _serve(FakeFabro)
    FakeFabro.hits.clear()
    monkeypatch.setitem(LC.GUARD, "blocked", 0)
    monkeypatch.setitem(service.MODEL_CALLS, "blocked_attempts", 0)
    try:
        fabro = LC.FabroView(url=f"http://127.0.0.1:{port}/api/v1", token="t")
        LC.install_guard({fabro.port()})
        feed = LC.LineConductor(LC.Observer("local", None, fabro), unit="t").cycle()
        assert FakeFabro.hits == ["/api/v1/runs/01RUNNING"]  # the live Fabro API path is the only connection
        assert feed["issues"] == [] and feed["supervisor"]["model_calls_healthy"] == 0 and LC.model_calls() == 0
        for p in (11434, 11435, 8080):  # a model endpoint or any other port is refused and counted
            with socket.socket() as s, pytest.raises(PermissionError):
                s.connect(("127.0.0.1", p))
        assert LC.model_calls() == 3
    finally:
        LC.uninstall_guard()
        srv.shutdown()


def test_the_service_loop_notifies_systemd_and_writes_a_heartbeat(line, monkeypatch):
    name = f"forge-line-conductor-test-{os.getpid()}"  # abstract socket: no path length limit
    rx = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    rx.bind("\0" + name)
    rx.settimeout(5)
    monkeypatch.setenv("NOTIFY_SOCKET", "@" + name)
    try:
        assert LC.run(conductor(line), 0.0, 2) == 0
        msgs = [rx.recv(4096).decode() for _ in range(4)]
    finally:
        rx.close()
    assert msgs[0].startswith("READY=1") and sum(m.startswith("WATCHDOG=1") for m in msgs) == 2 and msgs[-1] == "STOPPING=1"
    hb = json.loads(LC.heartbeat_path().read_text())
    assert hb["ok"] is True and hb["mode"] == "OBSERVE" and hb["cycle"] == 2


def test_the_unit_template_is_a_restarting_notify_service():
    unit = (REPO_ROOT / "deploy/systemd/afo/forge-line-conductor.service.in").read_text()
    for line_ in ("Type=notify", "Restart=always", "WatchdogSec=", "forge_factory.afo.line_conductor",
                  "FORGE_LINE_FABRO_URL=", "FORGE_LINE_LAUNCH_DIR="):
        assert line_ in unit, line_


# ----------------------------------------------------------------------------------------------- owner ack
def test_the_owner_ack_sets_only_acknowledged_and_is_audited(line, monkeypatch):
    lc = conductor(line)
    before = lc.cycle()
    iid = by_wo(before, IWDG.format(n=6, l=22))["issue_id"]
    assert afo_cli.main(["supervisor", "ack", iid, "--by", "owner", "--note", "seen, retry tomorrow"]) == 0
    after = json.loads(LC.feed_path().read_text())
    a, b = by_wo(after, IWDG.format(n=6, l=22)), by_wo(before, IWDG.format(n=6, l=22))
    assert a["escalation"]["acknowledged"] is True and a["escalation"]["acknowledged_by"] == "owner"
    strip = lambda i: {**i, "escalation": {k: v for k, v in i["escalation"].items() if not k.startswith("ack")}}  # noqa: E731
    assert strip(a) == strip(b) and [i for i in after["issues"] if i["issue_id"] != iid] == \
        [i for i in before["issues"] if i["issue_id"] != iid] and after["supervisor"] == before["supervisor"]
    from forge_factory.events.emit import read_segment

    ev = [e for e in read_segment() if e.get("incident_id") == iid]
    assert len(ev) == 1 and ev[0]["channel"] == "audit" and ev[0]["event_id"] == a["escalation"]["ack_ref"]
    again = lc.cycle(time.time() + 30)  # the next cycle carries the acknowledgement
    assert by_wo(again, IWDG.format(n=6, l=22))["escalation"]["acknowledged"] is True
    assert not (line["state"] / "conductor").exists()  # the ack never creates the AFO queue
    assert afo_cli.main(["supervisor", "ack", "SUP-0000000000", "--by", "owner", "--note", "x"]) == 1
    assert afo_cli.main(["supervisor", "ack", iid, "--by", "owner", "--note", " "]) == 1


# ------------------------------------------------------------------------------- the Omniverse2 replay
REPLAY = os.environ.get("FORGE_M1_REPLAY_DIR")


@pytest.mark.skipif(not REPLAY, reason="FORGE_M1_REPLAY_DIR (read-only copy of the Omniverse2 line state) not given")
def test_classification_replay_over_a_copy_of_the_omniverse2_line_state(tmp_path, monkeypatch):
    src = Path(REPLAY)
    stamp = {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file()}

    def observe(copy: Path):
        monkeypatch.setenv("FORGE_STATE_DIR", str(copy / "state"))
        snap = json.loads((copy / "fabro-snapshot.json").read_text())
        obs = LC.Observer("local", copy / "launch", LC.FabroView(snapshot=snap), lookback_s=3650 * 86400)
        return {i["wo"]: i for i in LC.LineConductor(obs, unit="replay").cycle()["issues"]}

    def copy(name, drop=()):
        d = tmp_path / name
        shutil.copytree(src, d, ignore=shutil.ignore_patterns("issues.json", "issues.jsonl", "acks.jsonl", "*.heartbeat", "feed.lock"))
        for p in d.rglob("*"):
            p.chmod(0o700 if p.is_dir() else 0o600)
        for w in drop:
            shutil.rmtree(d / "state/workorders" / w)
        return d

    stuck_wo, l24 = "WO-F014-SWE6-IWDGHAL-20261103-L22", "WO-F014-SWE6-IWDGHAL-20261103-L24"
    # as of the end of the L22 SWE.6 run (before the L24 retry): OPEN, model convergence, RULE retry proposal
    early = observe(copy("early", drop=[l24]))
    s = early[stuck_wo]
    assert (s["class"], s["status"]) == ("MODEL_CONVERGENCE", "OPEN")
    assert any(p["source"] == "RULE" and p["status"] == "PROPOSED"
               and p["summary"] == "retry SWE.6 from WO-F014-SWE5-IWDGHAL-20261103-L22" for p in s["proposals"])
    # now: the L24 retry passed SWE.6
    now = observe(copy("now"))
    s = now[stuck_wo]
    assert (s["class"], s["status"]) == ("MODEL_CONVERGENCE", "RESOLVED")
    assert {"kind": "superseded_by", "ref": f"workorders/{l24}"} in s["evidence"]
    assert now["WO-F014-SWE2-RCC-20261102-L16"]["status"] == "PARKED"
    assert now["WO-F014-SWE2-RCC-20261102-L16"]["error_code"] == "FABRO_RUN_CANCELLED"
    for wo in ("WO-F014-SWE5-IWDGHAL-20261103-L19", "WO-F014-SWE5-IWDGHAL-20261103-L21",
               "WO-F014-SWE1-CRCL-20261103-L20", "WO-F014-SWE1-CRCL-20261103-L21"):
        assert (now[wo]["class"], now[wo]["status"]) == ("INFRA", "RESOLVED"), wo
    hal = now["WO-F014-SWE1-CRCHAL-20261103-L24"]
    assert (hal["class"], hal["error_code"], hal["status"]) == ("INFRA", "PROVIDED_LL_MISSING", "RESOLVED")
    assert hal["proposals"][0]["strategy"] == "RELAUNCH_WITH_CORRECTED_PROVIDED_FROM"
    assert hal["proposals"][0]["args"]["provided_from"] == "WO-F014-SWE6-CRCL-20261103-L24"
    assert {"kind": "superseded_by", "ref": "workorders/WO-F014-SWE1-CRCHAL-20261103-L25"} in hal["evidence"]
    assert {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file()} == stamp  # the source copy is untouched
