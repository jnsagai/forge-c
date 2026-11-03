"""Autonomous line M2 (owner 2026-11-03): afo/line_launcher.py - the safe replacement of the Omniverse2 bash launcher
(launch-generic-model.sh, M0 lock + RUN_LIVE) and the loop10 waiter (run_one_model.sh).

Fakes: a scripted host (the run worktree's stack CLI and the local Fabro API), a fake /proc (UIDs, network namespaces,
storage-lock holders, stubborn processes) and temporary git repositories. Two tests use real processes: the M0 `flock`
CLI holding the host launch lock, and spawned look-alike Fabro servers holding a storage lock under a temporary root
(only processes this test spawned can match the temporary roots)."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from forge_factory.afo import line_conductor as LC
from forge_factory.afo import line_launcher as LL
from forge_factory.lrtx import stack as ST

UID = os.getuid()
RM = b"# RM0486 chapter 99 (converted)\nregister X at 0x40000000\n"
TOKEN = "fabro_dev_SECRET_TOKEN_MUST_NOT_LEAK"
PROFILE = "test-line-prof"
PRIMARY, ALT = "qwen-test:27b", "ornith-test:35b"


def sh(cwd, *args) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit_all(repo: Path, msg: str) -> str:
    sh(repo, "add", "-A")
    sh(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)
    return sh(repo, "rev-parse", "HEAD")


@pytest.fixture
def line(tmp_path):
    """An Omniverse2-shaped line: launch dir F with the shared line repo F/repo (two revisions, a git-ignored hash
    -manifested input present only on its disk), stack root F/lrtx, runs root F/runs, and the host lock elsewhere."""
    F = tmp_path / "line"
    repo = F / "repo"
    (repo / "examples/0099-x-st/inputs").mkdir(parents=True)
    (repo / "examples/0099c-x").mkdir(parents=True)
    (repo / "config/factory/profiles").mkdir(parents=True)
    (repo / "factory/python").mkdir(parents=True)
    (repo / ".gitignore").write_text("examples/0099-x-st/inputs/*.md\n")
    (repo / "examples/0099-x-st/inputs/RM-x.md").write_bytes(RM)
    (repo / "examples/0099-x-st/inputs/inputs-manifest.json").write_text(json.dumps({"documents": [
        {"doc": "RM0486", "markdown": "RM-x.md", "markdown_sha256": hashlib.sha256(RM).hexdigest()}]}))
    (repo / "examples/0099c-x/guide.md").write_text("tracked guideline\n")
    (repo / "examples/0099c-x/workorder.json").write_text(json.dumps({"inputs": [
        {"path": "../0099-x-st/inputs/RM-x.md", "role": "reference_manual"}, {"path": "guide.md", "role": "guideline"}]}))
    (repo / f"config/factory/profiles/{PROFILE}.yaml").write_text(
        f"schema: forge-c/local-profile/1\nid: {PROFILE}\n"
        "deployment: {root_env: FORGE_LRTX_ROOT, default_root: /nonexistent, ports: {ollama: 11455, gateway: 11456, "
        "fabro: 32391, llama: 11457}}\n"
        f"runtime: {{llama_server: {{model: '{PRIMARY}'}}, llama_server_alternates: {{'{ALT}': {{slots: 1}}}}}}\n")
    (repo / "factory/python/VERSION").write_text("1\n")
    sh(repo, "init", "-q", "-b", "main")
    rev1 = commit_all(repo, "rev1")
    (repo / "factory/python/VERSION").write_text("2\n")
    rev2 = commit_all(repo, "rev2")
    sh(repo, "checkout", "-q", rev1)  # the shared checkout sits detached at rev1, like Omniverse2's $F/repo
    L = F / "lrtx"
    for d in ("run", "state/workorders", "fabro/storage"):
        (L / d).mkdir(parents=True)
    (L / "fabro/storage/server.lock").touch()
    (L / "fabro/storage/server.env").write_text(f"SESSION_SECRET=x\nFABRO_DEV_TOKEN={TOKEN}\n")
    cfg = LL.LineConfig.from_env(launch_dir=F, repo=repo, stack_root=L, runs_root=F / "runs",
                                 gpu_lock=tmp_path / "host/line/gpu.lock", python=Path(sys.executable),
                                 inputs_cache=tmp_path / "host/line/inputs-cache", references=[repo], guard="", log=False)
    cfg.health_poll_s = 5
    return {"F": F, "repo": repo, "L": L, "cfg": cfg, "rev1": rev1, "rev2": rev2, "tmp": tmp_path}


def order(wo="WO-F014-SWE1-XHAL-20261103-L30", rev=None, **kw) -> LL.Order:
    return LL.Order(wo=wo, rev=rev, example="0099c-x", profile=PROFILE, model=ALT, **kw)


class FakeHost:
    """The run worktree's `python -m forge_factory.lrtx.stack ...` and the local Fabro API, scripted."""

    def __init__(self, runs=(), api_up=True, serve_rc=None, listed=None, healthy_after=0, start_rc=0, on_stop=None,
                 orphan_runs=None, run_status=()):
        self.runs, self.api_up, self.serve_rc, self.listed = list(runs), api_up, serve_rc or {}, listed
        self.healthy_after, self.start_rc, self.on_stop = healthy_after, start_rc, on_stop
        self.orphan_runs, self.run_status = orphan_runs or {}, list(run_status)
        self.calls, self.envs, self.lock_fds, self.ns_queries, self.t = [], [], [], [], 0.0
        self.current, self.polls, self.n = None, 0, 0

    def stack(self, args, *, env, cwd, log, lock_fd=None, timeout=1800):
        self.calls.append(list(args))
        self.envs.append(env)
        assert Path(cwd).is_dir()
        cmd = args[2] if args[0] == "--host-port" else args[0]
        if cmd == "stop":
            self.lock_fds.append(lock_fd)
            if self.on_stop:
                self.on_stop()
            return 0, '{"stopped": []}'
        if cmd == "start":
            self.lock_fds.append(lock_fd)
            return self.start_rc, "{}" if self.start_rc == 0 else "Traceback\nRuntimeError: run `init` first"
        if cmd == "status":
            self.polls += 1
            return 0, json.dumps({"status": "UP", "health": {"fabro": self.polls > self.healthy_after, "gateway": True}})
        if cmd == "expose-api":
            return 0, '{"api_bridge": "UP", "url": "http://127.0.0.1:32397/api/v1"}'
        assert cmd == "exec" and args[1] == "--"
        inner = args[2:]
        if inner[0] == "curl":
            ids = self.listed(self.current) if self.listed else [self.current]
            return 0, json.dumps({"data": [{"id": i} for i in ids]})
        if inner[3] == "serve":  # bash -c '... serve --model "$1"' serve <model>
            m = inner[-1]
            rc = self.serve_rc.get(m, 0)
            if rc == 0:
                self.current = m
            return rc, json.dumps({"model_swap": "SWAPPED" if rc == 0 else "FAILED", "model": m})
        assert inner[3] == "workorder"
        self.n += 1
        wo = inner[inner.index("--wo") + 1]
        return 0, json.dumps({"work_order": wo, "fabro_run_id": f"01FAKERUN{self.n:04d}", "workspace": f"/w/{wo}",
                              "intake": None, "status": None})

    def fabro_runs(self):
        if not self.api_up:
            raise LL.FabroUnavailable("ConnectError")
        return self.runs

    def fabro_runs_in_ns(self, pid, port):
        self.ns_queries.append((pid, port))
        return self.orphan_runs.get(pid)

    def fabro_run(self, run_id):
        st = self.run_status.pop(0) if self.run_status else "running"
        if st is None:
            raise LL.FabroUnavailable("ConnectError")
        return {"id": run_id, "lifecycle": {"status": {"kind": st}}}

    def guard(self, own):
        return "OK"

    def sleep(self, s):
        self.t += s

    def monotonic(self):
        return self.t


class FakeProcs:
    """A fake /proc: Proc records, storage-lock holders, processes that ignore SIGTERM or every signal."""

    def __init__(self, procs=(), lock_holders=None, ignore_term=(), unkillable=()):
        self.p = {p.pid: p for p in procs}
        self.locks = {str(k): set(v) for k, v in (lock_holders or {}).items()}
        self.ignore_term, self.unkillable = set(ignore_term), set(unkillable)
        self.signals = []

    def pids(self):
        return sorted(self.p)

    def get(self, pid):
        return self.p.get(pid)

    def lock_holders(self, path):
        return {x for x in self.locks.get(str(path), set()) if x in self.p}

    def alive(self, pid, start):
        q = self.p.get(pid)
        return q is not None and (start is None or q.start == start)

    def signal(self, pid, start, sig, uid):
        q = self.p.get(pid)
        if q is None or q.uid != uid or (start is not None and q.start != start):
            return False
        self.signals.append((pid, signal.Signals(sig).name))
        if pid in self.unkillable or (sig == signal.SIGTERM and pid in self.ignore_term):
            return True
        del self.p[pid]
        return True

    def self_chain(self):
        return set()


def P(pid, cmd, *, uid=UID, ns="net:[4026530001]", cwd="/", env=None, start=None):
    return LL.Proc(pid=pid, uid=uid, cmdline=cmd, cwd=cwd, environ=env or {}, netns=ns, start=start or f"t{pid}")


def stack_procs(L: Path, ns: str, base: int) -> list[LL.Proc]:
    """The four daemons lrtx/stack.py starts for root L, inside netns `ns`."""
    return [
        P(base + 1, ["/opt/fabro", "server", "start", "--foreground", "--config", f"{L}/fabro/settings.toml",
                     "--storage-dir", f"{L}/fabro/storage"], ns=ns, cwd=str(L)),
        P(base + 2, [f"{L}/ollama-0.34.0/bin/ollama", "serve"], ns=ns, cwd=str(L)),
        P(base + 3, [f"{L}/venv/bin/python", "-m", "forge_factory.llm_gateway", "--port", "11456", "--meter",
                     f"{L}/state/llm-gateway/usage.jsonl"], ns=ns, cwd=str(L)),
        P(base + 4, [f"{L}/ollama-0.34.0/lib/ollama/llama-server", "--model", f"{L}/ollama-models/blobs/x", "--alias",
                     PRIMARY], ns=ns, cwd=str(L)),
    ]


def live_stack(L: Path, holder=500, ns="net:[4026539999]") -> list[LL.Proc]:
    (L / "run/holder.pid").write_text(f"{holder}\n")
    return [P(holder, ["sleep", "infinity"], ns=ns, env={"FORGE_LRTX_ROOT": str(L)}), *stack_procs(L, ns, holder)]


def read_attempts(d: Path) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(d.glob("attempt-*.json"), key=lambda f: int(f.stem.split("-")[1]))]


def tree_digest(wt: Path) -> dict:
    return {str(p.relative_to(wt)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(wt.rglob("*"))
            if p.is_file() and ".git" not in p.parts}


# ------------------------------------------------------------------------------------------------- 1 host launch lock
def test_concurrent_launch_refused_gpu_lock_held_by_the_m0_flock_cli(line):
    """The bash M0 launcher holds the lock with `flock -n -o -E 75 gpu.lock ...`; the Python launcher is refused."""
    cfg = line["cfg"]
    cfg.gpu_lock.parent.mkdir(parents=True)
    holder = subprocess.Popen(["flock", "-n", str(cfg.gpu_lock), "sleep", "60"])
    try:
        deadline = time.monotonic() + 10
        while not LL.flock_holders(cfg.gpu_lock) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert LL.flock_holders(cfg.gpu_lock), "flock CLI did not take the lock"
        host = FakeHost()
        res = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    finally:
        holder.kill()
        holder.wait()
    assert (res["outcome"], res["class"]) == ("GPU_LOCK_HELD", "REFUSED")
    assert host.calls == [] and not (cfg.runs_root / order().wo).exists()
    t = read_attempts(cfg.runs_root / ".launch" / order().wo)
    assert [x["outcome"] for x in t] == ["GPU_LOCK_HELD"] and res["transcript"].endswith("attempt-1.json")


def test_concurrent_launch_refused_in_process_and_cli_exit_75(line, capsys):
    cfg = line["cfg"]
    with LL.gpu_lock(cfg.gpu_lock):  # launch A holds the host lock
        host = FakeHost()
        rc = LL.main(["launch", line["rev1"], order().wo, "0099c-x", PROFILE, "--stop-after SWE.1", ALT,
                      *cli_layout(line)], host=host, procs=FakeProcs())
    out = capsys.readouterr().out
    assert rc == LL.GPU_LOCK_EXIT and "GPU_LOCK_HELD: another Forge-C launch holds" in out and host.calls == []


# ------------------------------------------------------------------------------------------------------- 2 RUN_LIVE
def test_run_live_refused_before_any_worktree_or_stack_action(line):
    cfg, L = line["cfg"], line["L"]
    head = sh(line["repo"], "rev-parse", "HEAD")
    host = FakeHost(runs=[{"id": "01LIVERUN", "lifecycle": {"status": {"kind": "running"}},
                           "source_directory": f"{L}/state/workorders/WO-X/workspace"}])
    res = LL.launch(order(rev=line["rev2"]), cfg, host=host, procs=FakeProcs())
    assert (res["outcome"], res["class"]) == ("RUN_LIVE", "REFUSED") and "01LIVERUN" in res["detail"]
    assert host.calls == [] and not (cfg.runs_root / order().wo).exists()
    assert sh(line["repo"], "worktree", "list", "--porcelain").count("worktree ") == 1
    assert sh(line["repo"], "rev-parse", "HEAD") == head
    steps = read_attempts(cfg.runs_root / ".launch" / order().wo)[0]["steps"]
    assert [s["step"] for s in steps] == ["gpu_lock", "outcome"]


def test_run_live_ignores_other_roots_and_ended_runs_but_fails_closed_on_a_silent_live_fabro(line):
    cfg, L = line["cfg"], line["L"]
    other = [{"id": "01OTHER", "lifecycle": {"status": {"kind": "running"}}, "source_directory": f"{L}-cloud/state/x"},
             {"id": "01DONE", "lifecycle": {"status": {"kind": "succeeded"}}, "source_directory": f"{L}/state/x"}]
    assert LL.launch(order(rev=line["rev1"]), cfg, host=FakeHost(runs=other), procs=FakeProcs())["outcome"] == "LAUNCHED"
    # the API does not answer while a Fabro of the LIVE stack is alive: refuse, never assume "no run"
    host = FakeHost(api_up=False)
    res = LL.launch(order("WO-F014-SWE1-XHAL-20261103-L31", rev=line["rev1"]), cfg, host=host,
                    procs=FakeProcs(live_stack(L)))
    assert res["outcome"] == "FABRO_API_UNREACHABLE" and host.calls == []
    assert not (cfg.runs_root / "WO-F014-SWE1-XHAL-20261103-L31").exists()
    # an orphan Fabro (outside the live stack) is asked in its own namespace; a live run there is RUN_LIVE too
    (L / "run/holder.pid").unlink()
    (L / "run/services.json").write_text(json.dumps({"ports": {"fabro": 32391}, "processes": {}}))
    orphans = stack_procs(L, "net:[4026530666]", 600)
    host = FakeHost(api_up=False, orphan_runs={601: [{"id": "01ORPHANRUN", "lifecycle": {"status": {"kind": "running"}},
                                                      "source_directory": f"{L}/state/workorders/W/workspace"}]})
    res = LL.launch(order("WO-F014-SWE1-XHAL-20261103-L32", rev=line["rev1"]), cfg, host=host, procs=FakeProcs(orphans))
    assert res["outcome"] == "RUN_LIVE" and "01ORPHANRUN@orphan-fabro-601" in res["detail"]
    assert host.ns_queries == [(601, 32391)] and host.calls == []


# --------------------------------------------------------------------------------------------- 3 one worktree per run
def test_run_a_worktree_unchanged_after_run_b_launches_on_another_revision(line):
    cfg, repo = line["cfg"], line["repo"]
    shared_head, shared_status = sh(repo, "rev-parse", "HEAD"), sh(repo, "status", "--porcelain", "--ignored")
    a = LL.launch(order("WO-F014-SWE1-XHAL-20261103-LA", rev=line["rev1"]), cfg, host=FakeHost(), procs=FakeProcs())
    assert a["outcome"] == "LAUNCHED" and a["fabro_run_id"] == "01FAKERUN0001"
    wa = Path(a["worktree"])
    assert wa == cfg.runs_root / "WO-F014-SWE1-XHAL-20261103-LA"
    assert (wa / "examples/0099-x-st/inputs/RM-x.md").read_bytes() == RM  # the ignored input, copied and verified
    a_head, a_files = sh(wa, "rev-parse", "HEAD"), tree_digest(wa)
    host_b = FakeHost()
    b = LL.launch(order("WO-F014-SWE2-XHAL-20261103-LB", rev=line["rev2"], resume_from="WO-F014-SWE1-XHAL-20261103-LA",
                        stop_after="SWE.2"), cfg, host=host_b, procs=FakeProcs())
    assert b["outcome"] == "LAUNCHED"
    wb = Path(b["worktree"])
    assert sh(wb, "rev-parse", "HEAD") == line["rev2"] and (wb / "factory/python/VERSION").read_text() == "2\n"
    assert sh(wa, "rev-parse", "HEAD") == a_head == line["rev1"]
    assert tree_digest(wa) == a_files and (wa / "factory/python/VERSION").read_text() == "1\n"
    # the shared checkout was never checked out or modified; run B's stack and work order ran B's own code
    assert sh(repo, "rev-parse", "HEAD") == shared_head and sh(repo, "status", "--porcelain", "--ignored") == shared_status
    assert all(e["FORGE_REPO_ROOT"] == str(wb) and e["PYTHONPATH"] == f"{wb}/factory/python" for e in host_b.envs)
    wo_args = next(c for c in host_b.calls if "workorder" in c)
    assert wo_args[wo_args.index("--resume-from") + 1] == "WO-F014-SWE1-XHAL-20261103-LA"
    assert wo_args[-1] == "--detach" and wo_args[wo_args.index("--example") + 1] == "../../examples/0099c-x"
    # the second order took its input from the content-addressed cache the first one seeded
    items = next(s for s in read_attempts(wb / ".forge-run/launch")[0]["steps"] if s["step"] == "inputs")["items"]
    assert {i["path"]: (i["status"], i.get("source")) for i in items} == {
        "examples/0099-x-st/inputs/RM-x.md": ("COPIED", "cache"), "examples/0099c-x/guide.md": ("TRACKED", None)}
    # re-launching run A's order: a different revision is refused, the same revision too (it already launched)
    host = FakeHost()
    r = LL.launch(order("WO-F014-SWE1-XHAL-20261103-LA", rev=line["rev2"]), cfg, host=host, procs=FakeProcs())
    assert r["outcome"] == "WORKTREE_REV_MISMATCH" and host.calls == []
    r = LL.launch(order("WO-F014-SWE1-XHAL-20261103-LA", rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    assert r["outcome"] == "WORKTREE_ALREADY_LAUNCHED" and host.calls == [] and tree_digest(wa) == a_files


def test_inputs_are_hash_verified_and_a_dirty_or_foreign_worktree_is_refused(line):
    cfg, repo = line["cfg"], line["repo"]
    (repo / "examples/0099-x-st/inputs/RM-x.md").write_bytes(RM + b"tampered\n")  # reference no longer matches
    host = FakeHost()
    r = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    assert r["outcome"] == "INPUT_UNAVAILABLE" and r["class"] == "ORDER" and host.calls == []
    wt = cfg.runs_root / order().wo
    assert not (wt / "examples/0099-x-st/inputs/RM-x.md").exists()
    (repo / "examples/0099-x-st/inputs/RM-x.md").write_bytes(RM)
    (wt / "factory/python/VERSION").write_text("edited\n")  # someone touched the run's worktree
    assert LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())["outcome"] == "WORKTREE_NOT_CLEAN"
    occupied = cfg.runs_root / "WO-F014-SWE1-XHAL-20261103-L33"
    occupied.mkdir(parents=True)
    (occupied / "x").write_text("not a worktree")
    r = LL.launch(order("WO-F014-SWE1-XHAL-20261103-L33", rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    assert r["outcome"] == "WORKTREE_PATH_OCCUPIED" and host.calls == []
    assert LL.launch(order("WO-F014-SWE1-XHAL-20261103-L34", rev="deadbee"), cfg, host=host,
                     procs=FakeProcs())["outcome"] == "REV_UNKNOWN"


# ------------------------------------------------------------------------------------------------- 4 orphan sweep
def incident_procs(L: Path, *, live=True) -> tuple[list[LL.Proc], dict]:
    """2026-11-03 00:49Z: a raced start left a Fabro server holding <root>/fabro/storage/server.lock in a network
    namespace whose holder was gone, with its Ollama, gateway and Ollama runner; next to it: the live stack, and
    processes the sweep must never touch (another UID on our root, our UID on a similarly named root, a supervisor
    and a monitor whose environment names our root, another project's holder)."""
    dead = "net:[4026530666]"
    procs = live_stack(L) if live else []
    procs += stack_procs(L, dead, 600)[:3]
    procs += [P(604, ["/mnt/shared/ollama-0.34.0/bin/ollama", "runner", "--model", "/mnt/shared/blob"], ns=dead,
                cwd=str(L), env={"FORGE_LRTX_ROOT": str(L), "OLLAMA_MODELS": f"{L}/ollama-models"})]
    foreign = [
        P(701, ["/opt/fabro", "server", "start", "--storage-dir", f"{L}/fabro/storage"], uid=UID + 1, ns=dead),
        P(702, ["/opt/fabro", "server", "start", "--storage-dir", f"{L}-cloud/fabro/storage"], ns=dead,
          cwd=f"{L}-cloud", env={"FORGE_LRTX_ROOT": f"{L}-cloud"}),
        P(703, [f"{L}/venv/bin/python", "-m", "forge_factory.afo.line_conductor", "--launch-dir", str(L.parent)],
          env={"FORGE_LRTX_ROOT": str(L), "FORGE_STATE_DIR": f"{L}/state"}),
        P(704, ["sleep", "infinity"], env={"FORGE_LRTX_ROOT": "/mnt/data/other-project/lrtx"}),
        P(705, ["/x/llama-server", "--model", "/mnt/data/other-project/m"], cwd="/mnt/data/other-project"),
        P(706, ["python3", "-m", "forge_factory.lrtx.progress_api", "--port", "8765"],
          env={"FORGE_FLOOR_SUPERVISOR_FEED": f"{L}/state/supervisor/issues.json", "FORGE_LRTX_ROOT": str(L)}),
    ]
    return procs + foreign, {LL.storage_lock(L): {601}}


def test_orphan_sweep_kills_only_our_uid_and_root_and_clears_the_old_netns_storage_lock_holder(line):
    L = line["L"]
    procs, locks = incident_procs(L)
    fp = FakeProcs(procs, locks, ignore_term={602})
    rep = LL.sweep(L, fp, uid=UID, kill=False)
    assert rep["live_holder"] == 500 and sorted(rep["orphans"]) == [601, 602, 603, 604] and rep["killed"] == []
    assert {c["pid"]: c["kind"] for c in rep["candidates"] if not c["current"]} == {
        601: "fabro", 602: "ollama", 603: "gateway", 604: "ollama"}
    assert next(c for c in rep["candidates"] if c["pid"] == 601)["storage_lock"] is True
    assert fp.signals == []  # report mode signals nothing
    rep = LL.sweep(L, fp, uid=UID, kill=True, grace_s=1, sleep=lambda s: None)
    assert sorted(rep["killed"]) == [601, 602, 603, 604] and rep["survivors"] == [] and rep["storage_lock_holders"] == []
    assert (602, "SIGTERM") in fp.signals and (602, "SIGKILL") in fp.signals  # ignored TERM -> KILL after the grace
    assert sorted(fp.pids()) == [500, 501, 502, 503, 504, 701, 702, 703, 704, 705, 706]  # live stack + foreign intact
    assert {pid for pid, _ in fp.signals} == {601, 602, 603, 604}


def test_orphan_sweep_real_processes_only_ours_killed_and_the_storage_lock_released(line, tmp_path):
    """Real look-alike Fabro servers (argv0 `fabro ... server start --storage-dir <root>/fabro/storage`, holding the
    root's server.lock with flock): ours under the line root, a foreign one under a similarly named root."""
    L = line["L"]
    foreign_root = Path(f"{L}-cloud")
    (foreign_root / "fabro/storage").mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "fabro").symlink_to(sys.executable)
    code = ("import fcntl,sys,time;f=open(sys.argv[-1]+'/server.lock','a');fcntl.flock(f,fcntl.LOCK_EX);"
            "time.sleep(120)")
    spawned = {r: subprocess.Popen([str(bindir / "fabro"), "-c", code, "server", "start", "--storage-dir",
                                    f"{r}/fabro/storage"], cwd=str(r)) for r in (L, foreign_root)}
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not all(LL.flock_holders(LL.storage_lock(r)) for r in spawned):
            time.sleep(0.05)
        assert LL.flock_holders(LL.storage_lock(L)) == {spawned[L].pid}
        rep = LL.sweep(L, LL.ProcFS(), kill=True, grace_s=5)
        assert rep["killed"] == [spawned[L].pid] and rep["survivors"] == [] and rep["storage_lock_holders"] == []
        assert spawned[L].wait(timeout=10) == -signal.SIGTERM
        assert spawned[foreign_root].poll() is None  # the similarly named root's server is untouched
        assert LL.flock_holders(LL.storage_lock(foreign_root)) == {spawned[foreign_root].pid}
        fd = os.open(LL.storage_lock(L), os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # a new Fabro can take its storage lock again
        finally:
            os.close(fd)
    finally:
        for p in spawned.values():
            if p.poll() is None:
                p.kill()
            p.wait()


def test_launch_clears_exactly_the_2026_11_03_incident_then_starts(line):
    """No live holder any more (its PID file names a dead holder), the old namespace's Fabro holds the storage lock,
    its Ollama/gateway/runner are orphaned: stop, sweep them, start, launch."""
    cfg, L = line["cfg"], line["L"]
    (L / "run/holder.pid").write_text("499\n")
    procs, locks = incident_procs(L, live=False)
    fp = FakeProcs(procs, locks)
    host = FakeHost()
    res = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=fp)
    assert res["outcome"] == "LAUNCHED", res
    steps = {s["step"]: s for s in read_attempts(Path(res["worktree"]) / ".forge-run/launch")[0]["steps"]}
    assert sorted(steps["sweep"]["killed"]) == [601, 602, 603, 604]
    assert next(o for o in steps["sweep"]["orphans"] if o["pid"] == 601)["storage_lock"] is True
    assert [c[0] for c in host.calls[:2]] == ["stop", "start"]
    assert sorted(fp.pids()) == [701, 702, 703, 704, 705, 706]


def test_an_orphan_that_survives_the_sweep_stops_the_launch_before_start(line):
    cfg, L = line["cfg"], line["L"]
    procs, locks = incident_procs(L, live=False)
    host = FakeHost()
    res = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs(procs, locks, unkillable={601}))
    assert (res["outcome"], res["class"]) == ("STACK_STOP_INCOMPLETE", "INFRA")
    assert "fabro 601 still running" in res["detail"] and "FABRO_STORAGE_LOCK_HELD by [601]" in res["detail"]
    assert [c[0] for c in host.calls] == ["stop"]  # no start, no smoke, no launch


# ------------------------------------------------------------------------------------------------- 4 stack lock
def test_stack_lock_is_inherited_only_by_the_holders_own_start(line):
    """The launcher holds the lock and hands its descriptor to the stack CLI it runs: that start proceeds; any other
    process (no descriptor, or a descriptor of another file) is refused."""
    L = line["L"]
    probe = ("import sys;from forge_factory.lrtx import stack as S\n"
             "try:\n    cm=S.stack_lock(sys.argv[1]);cm.__enter__();print('ACQUIRED')\n"
             "except S.StackLockHeld:\n    print('REFUSED')\n")
    env = {**os.environ, "PYTHONPATH": str(Path(LL.__file__).resolve().parents[2])}
    env.pop(ST.LOCK_FD_ENV, None)
    other = os.open(line["tmp"] / "other.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with LL.held_stack_lock(L) as fd:
            def run(fd_env, fds):
                e = {**env, **({ST.LOCK_FD_ENV: str(fd_env)} if fd_env is not None else {})}
                return subprocess.run([sys.executable, "-c", probe, str(L)], env=e, pass_fds=fds, capture_output=True,
                                      text=True, timeout=60).stdout.strip()
            assert run(fd, (fd,)) == "ACQUIRED"
            assert run(None, ()) == "REFUSED"
            assert run(other, (other,)) == "REFUSED"
            with pytest.raises(LL.LaunchError) as e:  # a second launcher on the same root
                with LL.held_stack_lock(L):
                    pass
            assert e.value.code == "STACK_LOCK_HELD"
    finally:
        os.close(other)


def test_launch_refused_when_another_party_holds_the_stack_lock(line):
    cfg = line["cfg"]
    host = FakeHost()
    with ST.stack_lock(line["L"]):  # e.g. an operator's `stack start` racing the launcher
        res = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    assert (res["outcome"], res["class"]) == ("STACK_LOCK_HELD", "REFUSED") and host.calls == []
    host = FakeHost()
    assert LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())["outcome"] == "LAUNCHED"
    assert host.lock_fds and all(isinstance(fd, int) for fd in host.lock_fds)  # start/stop got the held descriptor


# ------------------------------------------------------------------------------------------------- 5 smoke, health
def test_smoke_failure_is_a_typed_infra_error_and_nothing_is_launched(line):
    cfg = line["cfg"]
    host = FakeHost(serve_rc={ALT: 1})
    res = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    assert (res["outcome"], res["class"]) == ("SMOKE_FAIL", "INFRA") and f"serve {ALT} exited 1" in res["detail"]
    assert not any("workorder" in c for c in host.calls)
    host = FakeHost(listed=lambda cur: [PRIMARY] if cur == ALT else [cur])  # the server lists the other model
    res = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    assert res["outcome"] == "SMOKE_FAIL" and "expected " + ALT in res["detail"]
    assert not any("workorder" in c for c in host.calls)
    host = FakeHost()
    assert LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())["outcome"] == "LAUNCHED"
    served = [c[-1] for c in host.calls if c[0] == "exec" and c[5] == "serve"]
    assert served == [ALT, PRIMARY]  # the bash order: the alternate (Ornith), then the primary (Qwen)


def test_stack_not_healthy_and_start_failure_are_typed(line):
    cfg = line["cfg"]
    cfg.health_timeout_s = 30
    host = FakeHost(healthy_after=10_000)
    res = LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())
    assert res["outcome"] == "STACK_NOT_HEALTHY" and host.polls == 7  # every 5 s for 30 s, then refused
    host = FakeHost(healthy_after=2)
    assert LL.launch(order(rev=line["rev1"]), cfg, host=host, procs=FakeProcs())["outcome"] == "LAUNCHED"
    res = LL.launch(order("WO-F014-SWE1-XHAL-20261103-L35", rev=line["rev1"]), cfg, host=FakeHost(start_rc=1),
                    procs=FakeProcs())
    assert res["outcome"] == "STACK_START_FAILED" and res["class"] == "INFRA"


# ------------------------------------------------------------------------------------------------- 6 transcripts
def test_each_attempt_writes_its_transcript_with_every_step_and_typed_outcome(line):
    cfg = line["cfg"]
    o = order(rev=line["rev1"])
    r1 = LL.launch(o, cfg, host=FakeHost(serve_rc={PRIMARY: 1}), procs=FakeProcs())
    r2 = LL.launch(o, cfg, host=FakeHost(), procs=FakeProcs())
    r3 = LL.launch(o, cfg, host=FakeHost(), procs=FakeProcs())
    wt = cfg.runs_root / o.wo
    t = read_attempts(wt / ".forge-run/launch")
    assert [(x["attempt"], x["outcome"], x["class"]) for x in t] == [(1, "SMOKE_FAIL", "INFRA"), (2, "LAUNCHED", "LAUNCHED")]
    assert [r["transcript"] for r in (r1, r2)] == [str(wt / f".forge-run/launch/attempt-{n}.json") for n in (1, 2)]
    # the refused re-attempt is recorded next to the runs: a launched run's worktree is never written by another launch
    assert r3["transcript"] == str(cfg.runs_root / ".launch" / o.wo / "attempt-3.json")
    assert read_attempts(cfg.runs_root / ".launch" / o.wo)[0]["outcome"] == "WORKTREE_ALREADY_LAUNCHED"
    assert all(x["schema"] == LL.SCHEMA and x["revision"] == line["rev1"] and x["order"]["wo"] == o.wo for x in t)
    assert [s["step"] for s in t[1]["steps"]] == [
        "gpu_lock", "run_live", "revision", "worktree", "inputs", "stack_lock", "stack_stop", "sweep", "stack_start",
        "stack_healthy", "expose_api", "smoke", "smoke", "workorder_launch"]
    assert t[1]["fabro_run_id"] == "01FAKERUN0001" and all(s["outcome"] == "OK" for s in t[1]["steps"])
    assert t[0]["steps"][-1] == {**t[0]["steps"][-1], "step": "outcome", "outcome": "SMOKE_FAIL"}
    assert worktree_ok(wt)  # transcripts never make the run's worktree dirty
    text = "".join(f.read_text() for f in (wt / ".forge-run/launch").glob("*.json"))
    assert TOKEN not in text  # the Fabro token is never recorded
    # a refusal before the worktree exists is recorded next to the runs, numbered on
    with LL.gpu_lock(cfg.gpu_lock):
        r4 = LL.launch(o, cfg, host=FakeHost(), procs=FakeProcs())
    assert r4["attempt"] == 4 and read_attempts(cfg.runs_root / ".launch" / o.wo)[-1]["outcome"] == "GPU_LOCK_HELD"


def worktree_ok(wt: Path) -> bool:
    return LL.worktree_clean(wt) == []


# ------------------------------------------------------------------------------------------------- 7 wait, verdict
def gate_log(ws: Path, rows: list[dict]) -> Path:
    (ws / ".forge-run/gates").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps({"ts": f"2026-11-03T10:{i:02d}:00Z", **r})
                                                                + "\n" for i, r in enumerate(rows)))
    return ws


def test_verdict_reader_pass_no_and_infra_unavailable(tmp_path):
    insp = lambda d, ph="SWE.2": {"phase": ph, "step": "inspect", "gate": {"decision": d}}  # noqa: E731
    pas = gate_log(tmp_path / "pass", [{"phase": "SWE.2", "step": "author", "result": "FROZEN"}, insp("FAIL"),
                                       {"phase": "SWE.2", "step": "author", "result": "FROZEN"}, insp("PASS"),
                                       {"phase": "SWE.2", "step": "route", "gate": {"decision": "PASS"}}])
    assert LL.phase_verdict(pas, "SWE.2")["verdict"] == "PASS"
    assert LL.phase_verdict(pas, "SWE.3") == {"phase": "SWE.3", "verdict": "NO", "reason": "NO_INSPECTION", "line": None}
    no = gate_log(tmp_path / "no", [insp("PASS", "SWE.1"), insp("FAIL"),
                                    {"phase": "SWE.2", "step": "route", "gate": {"decision": "BLOCKED"}}])
    assert LL.phase_verdict(no, "SWE.2")["verdict"] == "NO" and LL.phase_verdict(no, "SWE.1")["verdict"] == "PASS"
    # CAPA-122: the author visit's calls were refused -> the gate records INFRA_UNAVAILABLE, the route ends BLOCKED
    # with a retryable infra_outcome: neither PASS nor a product NO
    infra_author = gate_log(tmp_path / "ia", [insp("FAIL"), {"phase": "SWE.2", "step": "author",
                                                             "result": "INFRA_UNAVAILABLE", "status": "MODEL_CALLS_REFUSED"}])
    infra_inspect = gate_log(tmp_path / "ii", [{"phase": "SWE.2", "step": "inspect", "result": "INFRA_UNAVAILABLE",
                                                "status": "MODEL_CALLS_REFUSED"}])
    infra_route = gate_log(tmp_path / "ir", [insp("FAIL"), {"phase": "SWE.2", "step": "author",
                                                            "result": "INFRA_UNAVAILABLE"},
                                             {"phase": "SWE.2", "step": "route", "gate": {
                                                 "decision": "BLOCKED", "infra_outcome": {"code": "MODEL_CALLS_REFUSED",
                                                                                          "retryable": True}}}])
    for ws in (infra_author, infra_inspect, infra_route):
        v = LL.phase_verdict(ws, "SWE.2")
        assert v["verdict"] == "INFRA_UNAVAILABLE" and v["reason"].endswith("MODEL_CALLS_REFUSED"), (ws, v)
    assert LL.phase_verdict(tmp_path / "missing", "SWE.2")["reason"] == "GATE_LOG_MISSING"


def test_order_verdict_reads_the_stack_state_and_wait_for_end_polls_through_outages(line):
    cfg, L = line["cfg"], line["L"]
    gate_log(L / "state/workorders/WO-A/workspace", [{"phase": "SWE.1", "step": "inspect", "gate": {"decision": "PASS"}}])
    assert LL.order_verdict(cfg, "WO-A", "SWE.1")["verdict"] == "PASS"
    host = FakeHost(run_status=["running", None, None, "running", "succeeded"])
    w = LL.wait_for_end("01RUN", host, poll_s=30)
    assert w == {"run_id": "01RUN", "status": "succeeded", "ended": True, "polls": 5, "unreachable_polls": 2}
    assert host.t == 120
    w = LL.wait_for_end("01RUN", FakeHost(run_status=["running"] * 10), poll_s=30, timeout_s=60)
    assert w["ended"] is False and w["status"] == "running"


# ------------------------------------------------------------------------------------------------- dry run, CLI
def cli_layout(line) -> list[str]:
    cfg = line["cfg"]
    return ["--launch-dir", str(line["F"]), "--repo", str(line["repo"]), "--stack-root", str(line["L"]),
            "--runs-root", str(cfg.runs_root), "--gpu-lock", str(cfg.gpu_lock), "--python", sys.executable,
            "--inputs-cache", str(cfg.inputs_cache), "--guard", "", "--no-log"]


def test_dry_run_prints_the_plan_and_acts_on_nothing(line, capsys):
    L = line["L"]
    procs, locks = incident_procs(L)
    fp = FakeProcs(procs, locks)
    host = FakeHost()
    rc = LL.main(["launch", line["rev2"], order().wo, "0099c-x", PROFILE, "--provided-from WO-F014-SWE6-XL-20261103-L1 "
                  "--stop-after SWE.1", ALT, "--dry-run", *cli_layout(line)], host=host, procs=fp)
    out = capsys.readouterr().out
    assert rc == 0 and host.calls == [] and fp.signals == []
    assert not line["cfg"].runs_root.exists() and not line["cfg"].gpu_lock.exists()
    for needle in ("plan gpu_lock:", "plan run_live: none", f"worktree add --detach {line['cfg'].runs_root / order().wo}",
                   "plan input: examples/0099-x-st/inputs/RM-x.md COPY from reference", "plan input: examples/0099c-x/"
                   "guide.md TRACKED", "sweep orphans now [(601, 'fabro'), (602, 'ollama'), (603, 'gateway'), (604, "
                   "'ollama')]", "Fabro storage lock held by [601]", f"serve --model {ALT}", "--provided-from "
                   "WO-F014-SWE6-XL-20261103-L1 --detach", "outcome=planned"):
        assert needle in out, needle
    assert not re.search(r"LAUNCH WO-|RUN_LIVE|GPU_LOCK_HELD|SMOKE FAIL|NOT HEALTHY", out)  # no waiter/M1 marker


def test_cli_lines_are_read_by_the_loop10_waiter_and_the_m1_conductor(line, capsys):
    """Drop-in: the launch record (stdout -> launch-<WO>.out) carries the bash markers the loop10 waiter greps and
    the M1 Line Conductor classifies (LC.scan_launches)."""
    F = line["F"]
    waiter = re.compile(r"LAUNCH WO-\S+|SMOKE FAIL|NOT HEALTHY|CODE NOT AT|OWN llama-server still running|GUARD FAIL|"
                        r"GPU_LOCK_HELD|RUN_LIVE")

    def record(wo, host, *extra):
        rc = LL.main(["launch", line["rev1"], wo, "0099c-x", PROFILE, "--stop-after SWE.1", ALT, *extra,
                      *cli_layout(line)], host=host, procs=FakeProcs())
        out = capsys.readouterr().out
        (F / f"launch-{wo}.out").write_text(out)
        assert waiter.search(out), out
        return rc, out

    rc, out = record("WO-F014-SWE1-XHAL-20261103-L40", FakeHost())
    assert rc == 0
    rid = re.search(r'"fabro_run_id": "([A-Z0-9]*)', [x for x in out.splitlines() if "LAUNCH WO-" in x][-1]).group(1)
    assert rid == "01FAKERUN0001"
    assert record("WO-F014-SWE1-XHAL-20261103-L41", FakeHost(serve_rc={ALT: 1}))[0] == 1
    with ST.stack_lock(line["L"]):
        assert record("WO-F014-SWE1-XHAL-20261103-L43", FakeHost())[0] == 3
    with LL.gpu_lock(line["cfg"].gpu_lock):
        assert record("WO-F014-SWE1-XHAL-20261103-L44", FakeHost())[0] == 75
    host = FakeHost(runs=[{"id": "01LIVE", "lifecycle": {"status": {"kind": "running"}},
                           "source_directory": f"{line['L']}/state/workorders/W/workspace"}])
    assert record("WO-F014-SWE1-XHAL-20261103-L45", host)[0] == 3
    got = {r["wo"]: r["code"] for r in LC.scan_launches(F, time.time(), 3600)}
    assert got == {"WO-F014-SWE1-XHAL-20261103-L41": "MODEL_SMOKE_FAILED",
                   "WO-F014-SWE1-XHAL-20261103-L43": "STACK_LOCK_HELD",
                   "WO-F014-SWE1-XHAL-20261103-L44": "GPU_LOCK_HELD",
                   "WO-F014-SWE1-XHAL-20261103-L45": "RUN_LIVE"}


def test_extra_string_is_parsed_strictly():
    assert LL.parse_extra("--provided-from WO-F014-SWE6-IWDG-20261101-L6 --resume-from WO-F014-SWE5-IWDGHAL-20261103-L22"
                          " --stop-after SWE.6") == {"provided_from": "WO-F014-SWE6-IWDG-20261101-L6",
                                                     "resume_from": "WO-F014-SWE5-IWDGHAL-20261103-L22",
                                                     "stop_after": "SWE.6"}
    assert LL.parse_extra("") == {} and LL.parse_extra("--timeout-scale=2") == {"timeout_scale": 2.0}
    for bad in ("--acp-authors codex", "--stop-after", "--stop-after SWE.1; rm -rf /", "x"):
        with pytest.raises(LL.LaunchError) as e:
            LL.parse_extra(bad)
        assert e.value.code == "ORDER_ARGS_INVALID"
    with pytest.raises(LL.LaunchError):
        LL.Order(wo="WO-X;rm", rev="abc1234", example="e", profile="p", model="m").validate()
    with pytest.raises(LL.LaunchError):
        LL.Order(wo="WO-F014-SWE1-A-1", rev="abc1234", example="../e", profile="p", model="m").validate()
    with pytest.raises(LL.LaunchError):
        LL.Order(wo="WO-F014-SWE1-A-1", rev="abc1234", example="e", profile="p", model="m", stop_after="SWE.9").validate()
