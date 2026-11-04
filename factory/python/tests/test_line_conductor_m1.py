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


PHASE_ENUM = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
# Proposed contract delta for the owner rule 2026-11-03 (the oracle commit applies it to the protected schema)
SCHEMA_DELTA = {
    "properties.progress": {
        "type": "array", "maxItems": 200,
        "description": "Owner rule 2026-11-03: the last good, quality-checked part per lineage (the furthest phase whose "
                       "inspection gate passed, in the newest order that passed it); every retry resumes from it.",
        "items": {"type": "object", "additionalProperties": False, "required": ["lineage", "phase", "wo", "at", "ref"],
                  "properties": {"lineage": {"$ref": "#/$defs/token"}, "phase": {"enum": PHASE_ENUM},
                                 "wo": {"$ref": "#/$defs/token"}, "at": {"$ref": "#/$defs/nullable_utc"},
                                 "ref": {"$ref": "#/$defs/ref"}}}},
    "$defs.issue.properties.attempts.properties.rule": {
        "type": "string", "maxLength": 80, "pattern": "^[A-Za-z0-9 _.:;,/()+=#@<>-]{1,80}$",
        "description": "The stop rule the strike count is held against: 'same issue > 3 times stops the line'."},
    "$defs.issue.properties.escalation.properties.reason": {
        "anyOf": [{"$ref": "#/$defs/code"}, {"type": "null"}],
        "description": "Why the issue needs the owner, e.g. SAME_ISSUE_EXCEEDED_3."},
}


def apply_delta(schema: dict) -> dict:
    out = json.loads(json.dumps(schema))
    for path, value in SCHEMA_DELTA.items():
        node = out
        *parents, leaf = path.split(".")
        for k in parents:
            node = node[k]
        node[leaf] = value
    return out


@pytest.fixture
def delta(tmp_path, monkeypatch):
    """The conductor and the floor against the contract with the proposed delta applied."""
    import jsonschema

    schema = apply_delta(json.loads(LC.SCHEMA_PATH.read_text()))
    jsonschema.Draft202012Validator.check_schema(schema)
    f = tmp_path / "supervisor-issues.schema.json"
    f.write_text(json.dumps(schema, indent=2))
    monkeypatch.setattr(LC, "SCHEMA_PATH", f)
    monkeypatch.setattr(LC, "_VALIDATOR", None)
    return f


def stuck(issues):
    return [{"phase": "SWE.6", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": issues},
            {"phase": "SWE.6", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": issues},
            {"phase": "SWE.6", "step": "route", "gate": {"decision": "BLOCKED", "reason": "STUCK: identical rejection"}}]


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
    assert set(disk["budgets"]) == set(LC.BUDGETS) and all(k.startswith("guard_") for k in disk["budgets"])  # guards only
    assert disk["budgets"]["guard_planner_tokens_per_order"]["limit"] == 200_000
    assert disk["budgets"]["guard_phase_order_wall_s"]["limit"] == 21600
    # owner retry rule: with the contract delta (oracle 5ffd6533) the feed carries the last good part and the strike rule;
    # without it the feed omits them and stays valid
    if "progress" in json.loads(LC.SCHEMA_PATH.read_text())["properties"]:
        assert isinstance(disk["progress"], list)
        assert all(i["attempts"].get("rule") == "same issue > 3 times stops the line" for i in disk["issues"])
    else:
        assert "progress" not in disk and all(set(i["attempts"]) == {"used", "limit"} for i in disk["issues"])
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
    assert stuck["lineage"] == "IWDGHAL/" + IWDG.format(n=1, l=19) and {k: v for k, v in stuck["attempts"].items() if k != "rule"} == {"used": 1, "limit": 3}
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
    # L19 -> L21 is progress (another issue), L21 -> the L22 pass resolves it
    assert {"kind": "superseded_by", "ref": f"launch:launch-{IWDG.format(n=5, l=21)}.out"} in l19["evidence"]
    assert {"kind": "superseded_by", "ref": f"workorders/{IWDG.format(n=5, l=22)}"} in l21["evidence"]
    assert l19["attempts"]["used"] == 1 and l21["attempts"]["used"] == 1
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


# --------------------------------------------------------------- owner rule 2026-11-03: strikes and progress
X_ISSUES, Y_ISSUES = STUCK_ISSUES, ["VT:TEST_WITHOUT_TRACE:PERF"]


def _retries(line, outcomes, start=6000, lnum=30):
    """SWE.6 retries of the IWDG HAL part from the passed L22 SWE.5 order: 'X'/'Y' = stuck on that issue, 'P' = pass."""
    wos = []
    for n, o in enumerate(outcomes):
        wo = IWDG.format(n=6, l=lnum + n)
        mk_order(line["state"], wo, gates=passed("SWE.6") if o == "P" else stuck(X_ISSUES if o == "X" else Y_ISSUES),
                 package=True, rid=f"01RETRY{n}", source=IWDG.format(n=5, l=22), stop_after="SWE.6", created=T0 + start + 60 * n)
        wos.append(wo)
    return wos


def chain(feed):
    return [i for i in feed["issues"] if i["phase"] == "SWE.6" and i["lineage"].startswith("IWDGHAL")]


def test_a_new_fingerprint_or_a_pass_resets_the_strike_count(line, delta):
    wos = _retries(line, "XYYPY")  # the fixture's L22 is X too: X X Y Y P Y
    feed = conductor(line).cycle()
    assert LC.feed_errors(feed) == []
    x = next(i for i in chain(feed) if "MISSING_REQUIRED_OUTPUT" in i["summary"])
    assert x["attempts"] == {"used": 2, "limit": 3, "rule": "same issue > 3 times stops the line"}
    assert x["status"] == "RESOLVED" and {"kind": "superseded_by", "ref": f"workorders/{wos[1]}"} in x["evidence"]
    assert "PROGRESS_NEW_ISSUE" in x["proposals"][0]["reason_codes"]
    ys = [i for i in chain(feed) if "MISSING_REQUIRED_OUTPUT" not in i["summary"]]
    assert len(ys) == 1  # one issue per fingerprint chain, its latest run named
    y = ys[0]
    assert y["wo"] == wos[4] and y["status"] == "OPEN" and y["attempts"]["used"] == 1  # the pass reset it


def test_four_consecutive_recurrences_stop_the_line_three_do_not(line, delta):
    _retries(line, "XX")  # with the fixture's L22: X X X - three strikes, keep retrying
    feed = conductor(line).cycle()
    (x,) = chain(feed)
    assert (x["status"], x["attempts"]["used"], x["escalation"]["level"]) == ("OPEN", 3, "FLOOR")
    assert x["proposals"][0]["strategy"] == "RETRY_PHASE_FROM_LAST_PASSED_ORDER"
    wos = _retries(line, "X", start=9000, lnum=40)  # the fourth time
    feed = conductor(line).cycle(time.time() + 30)
    (x,) = chain(feed)
    assert (x["status"], x["attempts"]["used"], x["wo"]) == ("ESCALATED", 4, wos[0])
    assert x["escalation"]["level"] == "NEEDS_OWNER" and x["escalation"]["reason"] == "SAME_ISSUE_EXCEEDED_3"
    p = x["proposals"][0]
    assert (p["strategy"], p["reason_codes"], p["args"]["resume_from"]) == \
        ("STOP_LINE_REQUEST_OWNER", ["SAME_ISSUE_EXCEEDED_3"], IWDG.format(n=5, l=22))
    assert x["opened_at"] == LC._utc(T0 + 4000)  # the issue opened with its first strike
    assert LC.feed_errors(feed) == []


def test_retries_resume_from_the_last_good_part_and_progress_names_it(line, delta):
    feed = conductor(line).cycle()
    prog = {g["lineage"]: g for g in feed["progress"]}
    assert (prog["IWDGHAL"]["phase"], prog["IWDGHAL"]["wo"]) == ("SWE.5", IWDG.format(n=5, l=22))
    assert prog["IWDGHAL"]["ref"].endswith("gates/gate-log.jsonl#2")
    assert (prog["RCC"]["phase"], prog["CRCL"]["phase"]) == ("SWE.1", "SWE.6")
    for i in feed["issues"]:
        for p in i["proposals"]:
            if p["strategy"] in ("RETRY_PHASE_FROM_LAST_PASSED_ORDER", "RELAUNCH_PHASE_FROM_LAST_PASSED_ORDER",
                                 "RESUME_PHASE_FROM_LAST_PASSED_ORDER") and i["phase"] != "SWE.1":
                assert p["args"]["resume_from"] and p["args"]["resume_from"] in p["summary"], (i["wo"], p)
    assert by_wo(feed, "WO-F014-SWE2-RCC-20261102-L16")["proposals"][0]["args"]["resume_from"] == \
        "WO-F014-SWE1-RCC-20261102-L16"


# ------------------------------------------------- first live feed (2026-11-03): stale noise is not left OPEN
def _age(ws: Path, seconds: float) -> None:
    t = time.time() - seconds
    for f in ws.rglob("*"):
        os.utime(f, (t, t))


def blocked_at(phase, reason="rework budget exhausted (3 failed cycles)"):
    return [{"phase": phase, "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": ["BUILD_FAIL: error: x"]},
            {"phase": phase, "step": "route", "gate": {"decision": "BLOCKED", "reason": reason}}]


def test_an_issue_is_superseded_when_the_part_passes_its_phase_or_a_later_one_in_any_newer_order(line):
    mk_order(line["state"], "WO-F014-SWE3-IWDGG-20261102-L12", gates=blocked_at("SWE.3"), package=True, rid="01G12",
             stop_after="SWE.3", created=T0)
    mk_order(line["state"], "WO-F014-SWE3-CRCK-20261102-L12", gates=blocked_at("SWE.3"), package=True, rid="01K12",
             stop_after="SWE.3", created=T0)
    # another lineage of the same part, resumed past SWE.3 (its gate log has SWE.6 only)
    mk_order(line["state"], "WO-F014-SWE6-IWDGG-20261102-L13", gates=passed("SWE.6"), package=True, rid="01G13",
             source="WO-F014-SWE5-IWDGG-20261102-L13", stop_after="SWE.6", created=T0 + 600)
    feed = conductor(line).cycle()
    g = by_wo(feed, "WO-F014-SWE3-IWDGG-20261102-L12")
    assert g["status"] == "RESOLVED" and {"kind": "superseded_by", "ref": "workorders/WO-F014-SWE6-IWDGG-20261102-L13"} in g["evidence"]
    assert all("SUPERSEDED_BY_PART_PROGRESS" in p["reason_codes"] and p["status"] == "SUPERSEDED" for p in g["proposals"])
    assert by_wo(feed, "WO-F014-SWE3-CRCK-20261102-L12")["status"] == "OPEN"  # another part's progress is not this part's


def test_the_wall_guard_is_for_live_or_recent_orders_and_a_dead_order_is_parked_or_superseded(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    day, h7 = 86400, 7 * 3600
    _age(mk_order(state, "WO-F014-SWE3-IWDGG-20261101-L1", stop_after="SWE.3", created=time.time() - 2 * day), 2 * day)
    _age(mk_order(state, "WO-F014-SWE2-CRCK-20261101-L9", stop_after="SWE.2", created=time.time() - 2 * day), 2 * day)
    _age(mk_order(state, "WO-F014-SWE6-CRCK-20261102-L11", gates=passed("SWE.6"), package=True, rid="01K11",
                  source="WO-F014-SWE5-CRCK-20261102-L11", stop_after="SWE.6", created=time.time() - day), day)
    _age(mk_order(state, "WO-F014-SWE4-OBL-20261103-L5", rid="01LIVE", stop_after="SWE.4", created=time.time() - h7), h7)
    recent = mk_order(state, "WO-F014-SWE4-RCC-20261103-L7", stop_after="SWE.4", created=time.time() - h7)
    _age(recent, h7)
    (recent / ".forge-run/tool-progress").mkdir()
    (recent / ".forge-run/tool-progress/swe4.json").write_text("{}")  # activity now
    mk_order(state, "WO-F014-SWE1-OBL-20261103-L6", stop_after="SWE.1", created=time.time() - 3600)  # young: nothing
    fabro = LC.FabroView(snapshot={"01LIVE": "running"})
    feed = LC.LineConductor(LC.Observer("local", None, fabro, lookback_s=10 * day), unit="t").cycle()
    dead = by_wo(feed, "WO-F014-SWE3-IWDGG-20261101-L1")
    assert (dead["status"], dead["error_code"], dead["escalation"]["reason"]) == \
        ("PARKED", "ABANDONED_NO_LIVE_RUN", "ABANDONED_NO_LIVE_RUN")
    assert dead["proposals"][0]["strategy"] == "RESUME_PHASE_FROM_LAST_PASSED_ORDER"
    sup = by_wo(feed, "WO-F014-SWE2-CRCK-20261101-L9")
    assert sup["status"] == "RESOLVED" and "SUPERSEDED_BY_PART_PROGRESS" in sup["proposals"][0]["reason_codes"]
    for wo in ("WO-F014-SWE4-OBL-20261103-L5", "WO-F014-SWE4-RCC-20261103-L7"):  # live run, recent activity
        i = by_wo(feed, wo)
        assert (i["status"], i["error_code"]) == ("OPEN", "PHASE_WALL_GUARD_EXCEEDED"), wo
    assert not [i for i in feed["issues"] if i["wo"] == "WO-F014-SWE1-OBL-20261103-L6"]
    assert LC.feed_errors(feed) == []


def test_a_packaging_order_ready_for_review_raises_nothing(line):
    assert LC.parse_wo("WO-F014-PKG-IWDG-20261102-01") == (None, "IWDG")
    ws = mk_order(line["state"], "WO-F014-PKG-IWDG-20261102-01", rid="01PKG", source="WO-F014-SWE6-IWDG-20261101-L6",
                  stop_after=None, created=T0)
    (ws / ".forge-run/package.json").write_text(json.dumps({"package_status": "READY_FOR_OFFLINE_REVIEW", "gaps": []}))
    feed = conductor(line).cycle()
    assert not [i for i in feed["issues"] if i["wo"] == "WO-F014-PKG-IWDG-20261102-01"]


# ------------------------------- live feed after bde48a92: re-derived open issues, factory-rule rejections
def test_a_persisted_open_issue_is_rederived_and_resolved_when_the_current_rules_do_not_raise_it(line):
    lc = conductor(line)
    feed = lc.cycle()
    # an issue an earlier rule set opened on an order the current rules do not raise (its phase passed)
    ghost = json.loads(json.dumps(by_wo(feed, IWDG.format(n=6, l=22))))
    ghost.update(issue_id="SUP-0123456789", wo=IWDG.format(n=5, l=22), phase="SWE.5", status="OPEN",
                 error_code="PHASE_WALL_GUARD_EXCEEDED", resolved_at=None)
    LC.atomic_write(LC.feed_path(), json.dumps({**feed, "issues": feed["issues"] + [ghost]}).encode())
    # and the stuck order leaves the look-back window: its persisted open issue is still re-derived from its records
    _age(line["state"] / "workorders" / IWDG.format(n=6, l=22) / "workspace", 3 * 86400)
    lc2 = LC.LineConductor(LC.Observer("local", line["launch"], line["fabro"], lookback_s=86400), unit="t")
    after = lc2.cycle(time.time() + 30)
    g = next(i for i in after["issues"] if i["issue_id"] == "SUP-0123456789")
    assert g["status"] == "RESOLVED" and all("NOT_RAISED_BY_CURRENT_RULES" in p["reason_codes"] for p in g["proposals"])
    assert by_wo(after, IWDG.format(n=6, l=22))["status"] == "OPEN"  # re-derived although outside the window
    ev = [json.loads(x) for x in LC.journal_path().read_text().splitlines()]
    assert [e["event"] for e in ev if e["issue"]["issue_id"] == "SUP-0123456789"] == ["RESOLVED"]
    assert LC.feed_errors(after) == []


def test_a_deterministic_factory_rule_rejection_is_a_factory_defect_never_infra(line):
    assert LC.gate_code("VIEWS:SYNTAX:workproducts/SWE.2/architecture_dynamic.puml:line 7:Syntax Error?") == "VIEWS:SYNTAX"
    assert LC.gate_code("MISSING_REQUIRED_OUTPUT:workproducts/SWE.6/software_verification_report.md") == \
        "MISSING_REQUIRED_OUTPUT:software_verification_report.md"
    assert LC.gate_code("VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH") == "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH"
    hal = "WO-F014-SWE{n}-CRCHAL-20261103-L26"
    mk_order(line["state"], hal.format(n=1), gates=passed("SWE.1"), package=True, rid="01H1", created=T0)
    views = [{"phase": "SWE.2", "step": "author", "result": "REJECTED", "status": "INCOMPLETE",
              "issues": ["MISSING_REQUIRED_OUTPUT:workproducts/SWE.2/api_calls.json", "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH"]},
             {"phase": "SWE.2", "step": "author", "result": "REJECTED", "status": "INCOMPLETE",
              "issues": ["VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH"]},
             {"phase": "SWE.2", "step": "author", "result": "REJECTED", "status": "INCOMPLETE",
              "issues": ["VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH"]},
             {"phase": "SWE.2", "step": "route", "gate": {"decision": "BLOCKED", "reason": "STUCK: identical deterministic "
                                                          "rejection twice (VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH); stopped early"}},
             {"phase": "SWE.1", "step": "upstream", "result": "NONE", "defects": []},
             {"phase": "SWE.2", "step": "upstream", "result": "NONE", "defects": []}]
    mk_order(line["state"], hal.format(n=2), gates=views, package=True, rid="01H2", source=hal.format(n=1),
             stop_after="SWE.2", created=T0 + 600)
    # an author-quality finding whose code the CRE transient rule also matches (TIMEOUT) is convergence, not INFRA
    mk_order(line["state"], "WO-F014-SWE6-CRCK-20261103-L30", gates=stuck(["VT:TIMEOUT_SCENARIO_UNOBSERVED:SWR-007"]),
             package=True, rid="01K30", stop_after="SWE.6", created=T0 + 700)
    feed = conductor(line).cycle()
    i = by_wo(feed, hal.format(n=2))
    assert (i["class"], i["status"], i["error_code"]) == ("FACTORY_DEFECT", "WAITING_EXTERNAL_CHANGE",
                                                          "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH")
    p = i["proposals"][0]
    assert p["strategy"] == "OPEN_CAPA_FACTORY_DEFECT_SUSPECTED" and p["source"] == "RULE" and p["status"] == "PROPOSED"
    assert p["summary"] == f"factory defect suspected: open CAPA; resume SWE.2 from {hal.format(n=1)} once fixed"
    assert "TRANSIENT" not in i["summary"] and "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH" in i["summary"]
    c = by_wo(feed, "WO-F014-SWE6-CRCK-20261103-L30")
    assert (c["class"], c["error_code"]) == ("MODEL_CONVERGENCE", "VT:TIMEOUT_SCENARIO_UNOBSERVED")
    assert not [x for x in feed["issues"] if x["class"] == "INFRA" and x["fabro_run_id"] in ("01H2", "01K30")]


REPLAY_LIVE = os.environ.get("FORGE_M1_REPLAY_LIVE_DIR")


@pytest.mark.parametrize("codes,expected", [
    (["UNIT:NO_UNITS"], "FACTORY_DEFECT"),
    (["UNIT:SPEC_TODO:USPEC-HAL-01-01"], "MODEL_CONVERGENCE"),
    (["UNIT:NO_UNITS", "MISSING_REQUIRED_OUTPUT:unit_specifications.md"], "MODEL_CONVERGENCE"),
])
def test_repeated_empty_unit_inventory_is_suspected_factory_failure_without_guessing_other_unit_findings(
        line, codes, expected):
    wo = "WO-F014-SWE3-CRCHAL-20261103-L27"
    gates = [{"phase": "SWE.3", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": codes},
             {"phase": "SWE.3", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": codes},
             {"phase": "SWE.3", "step": "route", "gate": {"decision": "BLOCKED",
              "reason": "STUCK: identical deterministic rejection twice; stopped early"}}]
    mk_order(line["state"], wo, gates=gates, package=True, rid="01EMPTYUNITS", stop_after="SWE.3", created=T0 + 600)
    issue = by_wo(conductor(line).cycle(), wo)
    assert issue["class"] == expected
    if expected == "FACTORY_DEFECT":
        assert issue["status"] == "WAITING_EXTERNAL_CHANGE"
        assert issue["proposals"][0]["strategy"] == "OPEN_CAPA_FACTORY_DEFECT_SUSPECTED"
        assert issue["proposals"][0]["status"] == "PROPOSED"
    else:
        assert issue["status"] == "OPEN"


@pytest.mark.skipif(not REPLAY_LIVE, reason="FORGE_M1_REPLAY_LIVE_DIR (read-only copy of the live line + supervisor state) not given")
def test_replay_live_state_with_its_persisted_feed(tmp_path, monkeypatch):
    src = Path(REPLAY_LIVE)

    def files():
        return {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file() and not p.name.endswith(("-shm", "-wal"))}

    stamp = files()
    work = tmp_path / "state"
    work.mkdir()
    (work / "workorders").symlink_to(src / "state/workorders")  # the orders are only read
    shutil.copytree(src / "state/supervisor", work / "supervisor")  # the persisted feed, journal and CRE db, as live
    for f in (work / "supervisor").iterdir():
        f.chmod(0o600)
    monkeypatch.setenv("FORGE_STATE_DIR", str(work))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    prev = json.loads((work / "supervisor/issues.json").read_text())
    stale = {i["issue_id"]: i["wo"] for i in prev["issues"] if i["status"] == "OPEN"}
    at = LC._ts((src / "snapshot-at.txt").read_text().strip())
    obs = LC.Observer("local", src / "launch", LC.FabroView(snapshot=json.loads((src / "fabro-snapshot.json").read_text())))
    feed = LC.LineConductor(obs, unit="replay").cycle(at)
    assert LC.feed_errors(feed) == []
    now = {i["issue_id"]: i for i in feed["issues"]}
    hal = next(i for i in feed["issues"] if i["wo"] == "WO-F014-SWE2-CRCHAL-20261103-L26" and i["status"] != "RESOLVED")
    stale.pop(hal["issue_id"], None)
    assert len(stale) >= 5  # the 4 stale noise issues and the misclassified CRCHAL one, as the earlier code left them
    for iid, wo in stale.items():  # every issue the earlier code left OPEN is re-derived under the current rules
        assert now[iid]["status"] == "RESOLVED", (iid, wo)
    journal = [json.loads(x) for x in (work / "supervisor/issues.jsonl").read_text().splitlines()]
    assert set(stale) <= {e["issue"]["issue_id"] for e in journal[-80:] if e["event"] == "RESOLVED"}
    assert (hal["class"], hal["status"]) == ("FACTORY_DEFECT", "WAITING_EXTERNAL_CHANGE")
    assert hal["proposals"][0]["summary"] == \
        "factory defect suspected: open CAPA; resume SWE.2 from WO-F014-SWE1-CRCHAL-20261103-L26 once fixed"
    assert not [i for i in feed["issues"] if i["status"] == "OPEN"]
    assert [i["wo"] for i in feed["issues"] if i["status"] == "PARKED"] == ["WO-F014-SWE2-RCC-20261102-L16"]
    assert files() == stamp


REPLAY_TODAY = os.environ.get("FORGE_M1_REPLAY_TODAY_DIR")


@pytest.mark.skipif(not REPLAY_TODAY, reason="FORGE_M1_REPLAY_TODAY_DIR (read-only copy of today's line state) not given")
def test_replay_today_the_first_live_feeds_stale_noise_is_not_open(monkeypatch):
    src = Path(REPLAY_TODAY)

    def files():  # SQLite's -shm/-wal are reader bookkeeping of the read-only WAL open, not the records
        return {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file() and not p.name.endswith(("-shm", "-wal"))}

    stamp = files()
    monkeypatch.setenv("FORGE_STATE_DIR", str(src / "state"))
    at = LC._ts((src / "snapshot-at.txt").read_text().strip())
    obs = LC.Observer("local", src / "launch", LC.FabroView(snapshot=json.loads((src / "fabro-snapshot.json").read_text())),
                      lookback_s=72 * 3600)
    issues, _ = obs.issues(at)  # pure: the copy is only read
    got = {i["wo"]: i for i in issues}
    # the three were prepared workspaces whose launch was refused: one launch issue per part and phase, IWDGG SWE.3
    # twice the same refusal (L1 then L12, two strikes), both later passed by the part in other lineages
    g = got["WO-F014-SWE3-IWDGG-20261102-L12"]
    assert (g["class"], g["status"], g["attempts"]["used"]) == ("INFRA", "RESOLVED", 2)
    assert {"kind": "launch_log", "ref": "launch:launch-WO-F014-SWE3-IWDGG-20261101-L1.out"} in g["evidence"]
    k = got["WO-F014-SWE2-CRCK-20261101-L9"]
    assert (k["class"], k["status"], k["error_code"]) == ("INFRA", "RESOLVED", "RESUME_RECORD_UNREADABLE")
    for i in (g, k):
        assert all("SUPERSEDED_BY_PART_PROGRESS" in p["reason_codes"] for p in i["proposals"]), i["wo"]
    assert not [i for i in issues if i["wo"] in ("WO-F014-SWE3-IWDGG-20261102-L12", "WO-F014-SWE3-IWDGG-20261101-L1",
                                                  "WO-F014-SWE2-CRCK-20261101-L9") and i["error_code"] == "PHASE_WALL_GUARD_EXCEEDED"]
    assert "WO-F014-PKG-IWDG-20261102-01" not in got
    assert got["WO-F014-SWE2-RCC-20261102-L16"]["status"] == "PARKED"
    live = json.loads((src / "live/issues.json").read_text())
    stale = {i["wo"] for i in live["issues"] if i["status"] == "OPEN"}
    assert stale >= {"WO-F014-SWE3-IWDGG-20261102-L12", "WO-F014-PKG-IWDG-20261102-01"}  # what the live feed had
    assert not [w for w in stale if got.get(w, {}).get("status") == "OPEN"]
    assert files() == stamp


# ------------------------------------------------------------------------------- the Omniverse2 replay
REPLAY = os.environ.get("FORGE_M1_REPLAY_DIR")


@pytest.mark.skipif(not REPLAY, reason="FORGE_M1_REPLAY_DIR (read-only copy of the Omniverse2 line state) not given")
def test_classification_replay_over_a_copy_of_the_omniverse2_line_state(tmp_path, monkeypatch, delta):
    src = Path(REPLAY)
    stamp = {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file()}

    def observe(copy: Path):
        monkeypatch.setenv("FORGE_STATE_DIR", str(copy / "state"))
        snap = json.loads((copy / "fabro-snapshot.json").read_text())
        obs = LC.Observer("local", copy / "launch", LC.FabroView(snapshot=snap), lookback_s=3650 * 86400)
        feed = LC.LineConductor(obs, unit="replay").cycle()
        assert LC.feed_errors(feed) == []
        progress[copy.name] = {g["lineage"]: (g["phase"], g["wo"]) for g in feed["progress"]}
        return {i["wo"]: i for i in feed["issues"]}

    progress: dict = {}

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
    assert progress["early"]["IWDGHAL"] == ("SWE.5", "WO-F014-SWE5-IWDGHAL-20261103-L22")  # last good part before L24
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
    assert progress["now"]["IWDGHAL"] == ("SWE.6", l24)
    assert progress["now"]["CRCL"] == ("SWE.6", "WO-F014-SWE6-CRCL-20261103-L24")
    assert {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file()} == stamp  # the source copy is untouched
