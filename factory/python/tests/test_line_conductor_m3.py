"""Autonomous line M3 (owner 2026-11-03): the Line Conductor places and continues orders from owner-approved
campaign files, gated by a signed PILOT grant, with the owner retry rule (decision 14), the quality rule (decision
15), owner escalation (decision 5) and the disk guard (decision 12).

Fakes: the line (launcher subprocess, Fabro status, git revisions, disk, gh) and the clock. The ACT-dry-run replay
over a read-only copy of the Omniverse2 line state runs when FORGE_M3_REPLAY_DIR names the copy."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from forge_factory.afo import authz
from forge_factory.afo import line_campaign as LCMP
from forge_factory.afo import line_conductor as LC
from forge_factory.afo import line_launcher as LL
from forge_factory.afo import line_orders as LO
from forge_factory.common import REPO_ROOT

REV1, REV2, REV3 = "82fabdb9" + "0" * 32, "5f19d046" + "1" * 32, "aaaa1111" + "2" * 32
PROFILE = "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"
ORN = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"
PHASES = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
X = ["MISSING_REQUIRED_OUTPUT:workproducts/SWE.2/api_calls.json", "REQUIRED_TOOL_NOT_PASS:run_unit:FAIL"]
Y = ["VT:TEST_WITHOUT_TRACE:PERF"]
QUALITY = {"structural_coverage": {"line": {"target": 100, "minimum": 90}, "branch": {"target": 100, "minimum": 85}},
           "requirements_coverage": {"uspec_tested": {"target": 100, "minimum": 95},
                                     "swr_verified_swe6": {"target": 100, "minimum": 100}},
           "misra": {"open_violations_max": 0, "undeviated_rules_max": 0, "deviation_owner_approval": True}}
GB = 1024 ** 3


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime(t))


def passed(ph):
    return [{"phase": ph, "step": "author", "result": "FROZEN"}, {"phase": ph, "step": "inspect", "gate": {"decision": "PASS"}}]


def stuck(ph, issues):
    rej = {"phase": ph, "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": issues}
    return [rej, {"phase": ph, "step": "route", "gate": {"decision": "REWORK", "reason": "NO_BASELINE"}}, rej,
            {"phase": ph, "step": "route", "gate": {"decision": "BLOCKED", "reason": "STUCK: identical deterministic "
                                                    "rejection twice; stopped early"}}]


class Clock:
    def __init__(self):
        self.t = time.time() + 10

    def __call__(self):
        return self.t

    def tick(self, s=700):
        self.t += s
        return self.t


class FakeLine:
    """The line seen by the placer: the launcher (synchronous here), Fabro, git, disk, gh. Nothing real is run."""

    def __init__(self, tmp: Path, clock: Clock):
        self.tmp, self.clock = tmp, clock
        self.launch_d, self.runs = tmp / "launch", tmp / "runs"
        self.fabro: dict[str, str] = {}
        self.launched: list[dict] = []
        self.revs = {"82fabdb9": REV1, REV1: REV1, "5f19d046": REV2, REV2: REV2, "aaaa1111": REV3, REV3: REV3}
        self.quality_ok: set = set()
        self.spec_q: dict = {}
        self.free = 500 * GB
        self.gh_calls: list[list[str]] = []
        self.sweeps = 0
        self.live: list[str] = []
        self.fail_launch: dict[str, list[str]] = {}
        self.pytest_roots = [tmp / "pytest-of-me"]
        self.removed: list[str] = []
        self.n = 0

    state_root = property(lambda self: Path(os.environ["FORGE_STATE_DIR"]))

    def workspace(self, wo):
        return self.state_root / "workorders" / wo / "workspace"

    def launch_dir(self):
        return self.launch_d

    def transcripts(self, wo):
        d = self.runs / ".launch" / wo
        return [json.loads(f.read_text()) for f in sorted(d.glob("attempt-*.json"))] if d.is_dir() else []

    def run_status(self, rid):
        return self.fabro.get(rid)

    def live_runs(self):
        return list(self.live)

    def verdict(self, wo, phase):
        return {"work_order": wo, **LL.phase_verdict(self.workspace(wo), phase)}

    def gpu_holders(self):
        return []

    def resolve(self, rev):
        return self.revs.get(rev) if rev else None

    def spec_quality(self, sha, example):
        return True, self.spec_q.get(example)

    def quality_supported(self, sha):
        return sha in self.quality_ok

    def spawn_launch(self, argv, wo):
        flags = {argv[i]: argv[i + 1] for i in range(5, len(argv) - 1) if argv[i].startswith("--")}
        rec = {"wo": wo, "rev": argv[1], "example": argv[3], "profile": argv[4], **flags}
        self.launched.append(rec)
        d = self.runs / ".launch" / wo
        d.mkdir(parents=True, exist_ok=True)
        n = len(list(d.glob("attempt-*.json"))) + 1
        fails = self.fail_launch.get(wo) or []
        if fails:
            code = fails.pop(0)
            (d / f"attempt-{n}.json").write_text(json.dumps({"attempt": n, "outcome": code, "class": LL.CODES[code],
                                                             "ended_at": _iso(self.clock()), "work_order": wo}))
            return {"pid": 0, "start": None}
        self.n += 1
        rid = f"01RUN{self.n:04d}"
        ws = self.workspace(wo)
        (ws / ".forge-run/gates").mkdir(parents=True, exist_ok=True)
        man = {"work_order": wo, "created_at": _iso(self.clock()), "phase_scope": {"stop_after": flags["--stop-after"]},
               "factory_revision": {"commit": self.revs[argv[1]], "basis": "recorded_at_launch"}}
        if flags.get("--resume-from"):
            man["resumed_from"] = {"source_work_order": flags["--resume-from"]}
        if flags.get("--quality"):
            man["quality"], man["quality_source"] = json.loads(Path(flags["--quality"]).read_text()), "campaign"
        (ws / ".forge-run/manifest.json").write_text(json.dumps(man))
        (ws / ".forge-run/gates/gate-log.jsonl").write_text("")
        (ws / ".forge-run/fabro_run_id").write_text(rid)
        self.fabro[rid] = "running"
        (d / f"attempt-{n}.json").write_text(json.dumps({"attempt": n, "outcome": "LAUNCHED", "class": "LAUNCHED",
                                                         "fabro_run_id": rid, "ended_at": _iso(self.clock())}))
        (self.runs / wo).mkdir(parents=True, exist_ok=True)
        return {"pid": 0, "start": None}

    def alive(self, pid, start):
        return False

    def sweep(self):
        self.sweeps += 1
        return {"ok": True, "killed": [], "survivors": []}

    def free_bytes(self):
        return self.free

    def run_worktree(self, wo):
        return self.runs / wo

    def remove_worktree(self, wo):
        self.removed.append(wo)
        return True

    def gh(self, argv):
        self.gh_calls.append(argv)
        return 0, f"https://github.com/jnsagai/forge-c/issues/{900 + len(self.gh_calls)}"

    # test helpers ---------------------------------------------------------------------------------------------
    def finish(self, wo, result="PASS", *, phase=None, defects=None):
        ws = self.workspace(wo)
        ph = phase or json.loads((ws / ".forge-run/manifest.json").read_text())["phase_scope"]["stop_after"]
        rid = (ws / ".forge-run/fabro_run_id").read_text()
        if result == "CANCELLED":
            self.fabro[rid] = "failed:cancelled"
            return
        if result == "PASS":
            gates = passed(ph)
        elif result == "INFRA":
            gates = [{"phase": ph, "step": "author", "result": "INFRA_UNAVAILABLE", "infra_outcome": True}]
        else:
            gates = stuck(ph, result)
        (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps({**g, "ts": _iso(self.clock())}) + "\n"
                                                                    for g in gates))
        for d in defects or []:
            (ws / ".forge-run/defects").mkdir(parents=True, exist_ok=True)
            (ws / f".forge-run/defects/{d['id']}.json").write_text(json.dumps(d))
        (ws / ".forge-run/package.json").write_text(json.dumps({"package_status": "BLOCKED", "gaps": []}))
        self.fabro[rid] = "succeeded:completed"


def lineage(id_, tag, series, **kw):
    base = {"id": id_, "example": f"ex-{id_}", "tag": tag, "series": series, "driver_class": f"STM32N6_{tag}",
            "factory_revision": "82fabdb9", "profile": PROFILE, "run_model": ORN, "purpose": "ASPICE_ONLY",
            "phases": PHASES, "priority": 50}
    base.update(kw)
    return base


def _git(d, *a):
    subprocess.run(["git", "-c", "user.name=owner", "-c", "user.email=owner@example.invalid", *a], cwd=d, check=True,
                   capture_output=True)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    monkeypatch.delenv("FORGE_DURABLE_AUTONOMY", raising=False)
    (tmp_path / "state").mkdir()
    camp = tmp_path / "campaigns"
    camp.mkdir()
    _git(camp, "init", "-q")
    pol = yaml.safe_load((REPO_ROOT / "config/factory/line-policy.yaml").read_text())
    pol["authorization_ref"] = "AUTH-T"
    (tmp_path / "line-policy.yaml").write_text(yaml.safe_dump(pol))
    key = tmp_path / "owner_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "owner", "-f", str(key)], check=True)
    signers = tmp_path / "allowed_signers"
    signers.write_text(f'jnsagai namespaces="{authz.NAMESPACE}" {(tmp_path / "owner_ed25519.pub").read_text()}')
    (tmp_path / "auth").mkdir()
    clock = Clock()
    return {"tmp": tmp_path, "camp": camp, "key": key, "signers": signers, "clock": clock,
            "line": FakeLine(tmp_path, clock)}


def write_campaign(env, lineages, name="c.yaml", commit=True, cid="CMP-TEST-1"):
    p = env["camp"] / name
    p.write_text(yaml.safe_dump({"schema": LCMP.SCHEMA_ID, "campaign_id": cid, "line": "local", "wo_prefix": "WO-F014",
                                 "lineages": lineages}, sort_keys=False))
    if commit:
        _git(env["camp"], "add", name)
        _git(env["camp"], "commit", "-q", "-m", f"campaign {name}")
    return p


def grant(env, *, expires=None, issued=None, drivers=None, models=None, services=None, actions=None, sha=None,
          sign=True):
    pol = LO.load_policy(env["tmp"] / "line-policy.yaml")
    now = env["clock"]()
    rec = {"schema_version": "1.0", "authorization_id": "AUTH-T", "approver": "jnsagai",
           "approval_evidence_ref": "owner test grant", "issued_utc": _iso(issued if issued is not None else now - 60)[:19] + "Z",
           "expires_utc": _iso(expires if expires is not None else now + 14 * 86400)[:19] + "Z",
           "policy_sha256": sha or pol.sha256, "mode": "PILOT",
           "allowed_actions": actions or ["submit_workorder", "launch_workorder", "recover_workorder"],
           "scope": {"driver_classes": drivers or ["STM32N6_CRCL", "STM32N6_CRCHAL", "STM32N6_WWDGL", "STM32N6_WWDGHAL"],
                     "models": models or [PROFILE],
                     "service_actions": services or ["line_stack_restart", "line_orphan_sweep", "line_run_worktree_cleanup"]},
           "signature_ref": "AUTH-T.sig", "revoked_utc": None, "signed_runbook_ref": None}
    p = env["tmp"] / "auth/AUTH-T.json"
    p.write_text(json.dumps(rec))
    if sign:
        authz.sign(p, env["key"])
    return rec


def placer(env, **kw):
    kw.setdefault("dry_run", False)
    return LO.Placer(env["line"], campaigns_dir=env["camp"], policy_path=env["tmp"] / "line-policy.yaml",
                     auth_base=env["tmp"] / "auth", allowed_signers=env["signers"], clock=env["clock"], capa_of={}, **kw)


def lin(out, lid):
    return next(x for x in out["lineages"] if x["lineage"].endswith("/" + lid))


def queue_rows():
    return LO._queue_rows(LO.supervisor_dir() / "line-queue.sqlite3")


def drive(env, pl, results: dict | None = None, cycles=40, until=None):
    """Cycle the placer; every launched order finishes with results[wo] (default PASS) on the next cycle."""
    line, outs = env["line"], []
    results = results or {}
    for _ in range(cycles):
        out = pl.cycle()
        outs.append(out)
        for rec in line.launched:
            ws = line.workspace(rec["wo"])
            if (ws / ".forge-run/fabro_run_id").is_file() and not (ws / ".forge-run/package.json").is_file() \
                    and line.fabro.get((ws / ".forge-run/fabro_run_id").read_text()) == "running":
                r = results.get(rec["wo"], "PASS")
                if r != "HOLD":
                    line.finish(rec["wo"], r[0] if isinstance(r, tuple) else r,
                                defects=r[1] if isinstance(r, tuple) else None)
        env["clock"].tick()
        if until and until(out):
            break
    return outs


# ------------------------------------------------------------------------------------------------------ campaigns
def test_the_example_campaign_matches_todays_line_and_validates():
    c = LCMP.parse(REPO_ROOT / "config/factory/campaigns/omniverse2-local-20261103.yaml", require_approval=False)
    by = {L.id: L for L in c.lineages}
    assert by["iwdg-hal"].status == "DONE" and by["iwdg-hal"].completed_by == "WO-F014-SWE6-IWDGHAL-20261103-L24"
    assert (by["wwdg-ll"].example, by["wwdg-ll"].factory_revision) == ("0016c-st-cube-wwdg", "82fabdb9")
    assert by["wwdg-ll"].wo("SWE.1") == "WO-F014-SWE1-WWDGL-20261103-L29"  # the live L29 order is adopted by name
    # owner 2026-11-03: CAPA-133 + the SWE2-08 revisions record keep the ST CRC LL L24 verified (no L30 rerun)
    assert by["crc-ll"].status == "DONE" and by["crc-ll"].completed_by == "WO-F014-SWE6-CRCL-20261103-L24"
    h = by["crc-hal"]
    assert h.provided_from == "WO-F014-SWE6-CRCL-20261103-L24" and h.depends_on is None
    assert h.start == {"resume_from": "WO-F014-SWE1-CRCHAL-20261103-L27", "at": "SWE.2"} and h.factory_revision is None
    assert h.wo("SWE.2") == "WO-F014-SWE2-CRCHAL-20261103-L31"
    assert by["wwdg-hal"].depends_on["lineage"] == "wwdg-ll" and by["wwdg-hal"].factory_revision is None
    assert by["rcc-ll"].status == "ON_HOLD"
    assert by["wwdg-ll"].priority > by["crc-hal"].priority > by["wwdg-hal"].priority
    if LCMP.CONTRACT.is_file():
        import yaml as Y

        assert LCMP.contract_errors(Y.safe_load(c.path.read_text())) == []
    assert [LCMP.retry_suffix(n) for n in (1, 2, 26, 27, 28)] == ["", "B", "Z", "AA", "AB"]


@pytest.mark.parametrize("change,code", [
    ({"depends_on": {"lineage": "a", "phase": "SWE.6", "verdict": "PASS"}}, "FIELD_INVALID:depends_on"),
    ({"phases": ["SWE.1", "SWE.3"]}, "FIELD_INVALID:phases"),
    ({"status": "DONE"}, "DONE_NEEDS_COMPLETED_BY"),
    ({"factory_revision": 12345678}, "FIELD_INVALID:factory_revision"),
    ({"quality": {"structural_coverage": {"line": {"target": 90, "minimum": 95}}}}, "QUALITY"),
    ({"bogus": 1}, "UNKNOWN_KEY:bogus"),
    ({"start": {"resume_from": "WO-F014-SWE1-X-20261103-L1", "at": "SWE.1"}}, "FIELD_INVALID:start")])
def test_invalid_campaigns_are_refused(change, code):
    doc = {"schema": LCMP.SCHEMA_ID, "campaign_id": "CMP-T-1", "line": "local", "lineages": [lineage("a", "AA", "20261103-L1", **change)]}
    errs = LCMP.validate(doc)
    assert any(code in e for e in errs), errs
    if LCMP.CONTRACT.is_file() and code not in ("QUALITY", "FIELD_INVALID:phases"):
        assert LCMP.contract_errors(doc)


def test_a_campaign_is_loaded_only_when_committed_and_unmodified(env):
    p = write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30")], commit=False)
    good, bad = LCMP.load_all(env["camp"])
    assert not good and bad[0]["code"] == "CAMPAIGN_NOT_COMMITTED"
    _git(env["camp"], "add", p.name)
    _git(env["camp"], "commit", "-q", "-m", "approve")
    good, bad = LCMP.load_all(env["camp"])
    assert len(good) == 1 and not bad and len(good[0].commit) == 40 and good[0].sha256 == LO.sha256_bytes(p.read_bytes())
    p.write_text(p.read_text().replace("priority: 50", "priority: 51"))
    good, bad = LCMP.load_all(env["camp"])
    assert not good and bad[0]["code"] == "CAMPAIGN_MODIFIED_SINCE_COMMIT"


# --------------------------------------------------------------------------------------------- authorization gate
@pytest.mark.parametrize("case", ["none", "unsigned", "expired", "wrong_driver", "wrong_model", "wrong_policy",
                                  "no_launch_action", "no_stack_service"])
def test_act_refuses_without_a_valid_grant_and_stays_observing(env, case):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30")])
    now = env["clock"]()
    if case == "unsigned":
        grant(env, sign=False)
    elif case == "expired":
        grant(env, issued=now - 20 * 86400, expires=now - 86400)
    elif case == "wrong_driver":
        grant(env, drivers=["STM32N6_RCC_LL"])
    elif case == "wrong_model":
        grant(env, models=["codex-claude"])
    elif case == "wrong_policy":
        grant(env, sha="0" * 64)
    elif case == "no_launch_action":
        grant(env, actions=["submit_workorder", "recover_workorder"])
    elif case == "no_stack_service":
        grant(env, services=["line_orphan_sweep"])
    out = placer(env).cycle()
    assert env["line"].launched == [] and not queue_rows()
    act = [a for a in out["actions"] if a["action"] == "PLACE"]
    if case in ("none", "unsigned", "expired", "wrong_policy"):
        assert out["mode"] == "OBSERVING" and out["authorization"]["code"] != "AUTH_OK"
        assert act[0]["outcome"] == "WOULD_REFUSE"
    else:  # the grant is valid, the request is outside it: refused, nothing placed
        assert out["mode"] == "ACTING" and act[0]["outcome"] == "REFUSED"
        assert act[0]["detail"].startswith(("AUTH_OUT_OF_SCOPE", "AUTH_ACTION_NOT_ALLOWED"))


def test_the_line_policy_floor_is_never_weakened(env):
    pol = yaml.safe_load((env["tmp"] / "line-policy.yaml").read_text())
    for path, value in (("owner_rules.same_issue_limit", 5), ("disk.min_free_gb", 10), ("disk.cleanup_min_age_days", 1),
                        ("pacing.max_concurrent_gpu_runs", 2), ("never.merge", False), ("escalation.mentions", True)):
        p = json.loads(json.dumps(pol))
        a, b = path.split(".")
        p[a][b] = value
        f = env["tmp"] / "weak.yaml"
        f.write_text(yaml.safe_dump(p))
        lp = LO.load_policy(f)
        assert any(path.split(".")[-1] in i for i in lp.issues), (path, lp.issues)
        assert LO.verify_grant(lp, now=env["clock"]()).code == "LINE_POLICY_INVALID"


# --------------------------------------------------------------------------------------------------- chaining
def test_replaying_a_campaign_chains_swe1_to_swe6_then_ll_to_hal(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", priority=50),
                         lineage("crc-hal", "CRCHAL", "20261103-L31", priority=40,
                                 depends_on={"lineage": "crc-ll", "phase": "SWE.6", "verdict": "PASS"})])
    grant(env)
    pl = placer(env)
    first = pl.cycle()
    assert lin(first, "crc-hal")["state"] == "WAITING" and lin(first, "crc-hal")["reason"] == "DEPENDS_ON:crc-ll:SWE.6:PASS"
    drive(env, pl, until=lambda o: lin(o, "crc-hal")["state"] == "DONE")
    L = env["line"].launched
    ll = [f"WO-F014-SWE{n}-CRCL-20261103-L30" for n in range(1, 7)]
    hal = [f"WO-F014-SWE{n}-CRCHAL-20261103-L31" for n in range(1, 7)]
    assert [x["wo"] for x in L] == ll + hal
    assert [x.get("--resume-from") for x in L] == [None] + ll[:5] + [None] + hal[:5]
    assert [x["--stop-after"] for x in L] == PHASES * 2
    assert {x["rev"] for x in L} == {"82fabdb9"}  # the campaign's revision, every phase
    assert [x.get("--provided-from") for x in L] == [None] * 6 + ["WO-F014-SWE6-CRCL-20261103-L30"] * 6
    rows = queue_rows()
    assert sorted(rows) == sorted(ll + hal)
    assert all(r["state"] == "BLOCKED" and r["terminal_reason"].startswith("PHASE_VERDICT:PASS") for r in rows.values())
    assert all(r["envelope"]["manifest_sha256"] == LO.sha256_bytes((env["camp"] / "c.yaml").read_bytes())
               for r in rows.values())
    last = placer(env).cycle()
    assert lin(last, "crc-ll")["state"] == "DONE" and lin(last, "crc-ll")["last_good"]["wo"] == ll[-1]
    assert len(env["line"].launched) == 12  # nothing more to place


def test_one_gpu_run_at_a_time_and_priority_picks_the_next_lineage(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", priority=50),
                         lineage("wwdg-ll", "WWDGL", "20261103-L29", priority=60)])
    grant(env)
    pl = placer(env)
    pl.cycle()
    assert [x["wo"] for x in env["line"].launched] == ["WO-F014-SWE1-WWDGL-20261103-L29"]
    out = pl.cycle()  # running: nothing else is placed
    assert len(env["line"].launched) == 1 and out["gpu"]["busy"] and lin(out, "crc-ll")["state"] == "QUEUED"
    env["line"].live = ["01FOREIGN"]  # a live run outside the campaigns also holds the line
    env["line"].finish("WO-F014-SWE1-WWDGL-20261103-L29")
    out = pl.cycle()
    assert len(env["line"].launched) == 1 and out["gpu"]["reason"] == "RUN_LIVE_NOT_IN_CAMPAIGN"


# ------------------------------------------------------------------------------------------- restart / adoption
def test_a_restart_mid_run_adopts_the_run_and_never_double_launches(env):
    write_campaign(env, [lineage("wwdg-ll", "WWDGL", "20261103-L29", quality=QUALITY)])
    grant(env)
    line = env["line"]
    line.spec_q["ex-wwdg-ll"] = QUALITY  # the revision gives exactly the campaign's quality (no flag)
    # a live run launched outside the conductor (the loop10 ladder's L29 SWE.1)
    ws = line.workspace("WO-F014-SWE1-WWDGL-20261103-L29")
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-F014-SWE1-WWDGL-20261103-L29",
                                                             "created_at": _iso(env["clock"]() - 3600),
                                                             "phase_scope": {"stop_after": "SWE.1"},
                                                             "factory_revision": {"commit": REV1}}))
    (ws / ".forge-run/fabro_run_id").write_text("01LADDER")
    line.fabro["01LADDER"] = "running"
    out = placer(env).cycle()
    assert line.launched == [] and lin(out, "wwdg-ll")["state"] == "RUNNING"
    assert [a["outcome"] for a in out["actions"] if a["action"] == "ADOPT"] == ["ADOPTED"]
    assert queue_rows()["WO-F014-SWE1-WWDGL-20261103-L29"]["state"] == "RUNNING"
    for _ in range(3):  # restarts while the run is live: adopted once, never launched
        out = placer(env).cycle()
        env["clock"].tick()
    assert line.launched == [] and not [a for a in out["actions"] if a["action"] == "ADOPT"]
    line.finish("WO-F014-SWE1-WWDGL-20261103-L29")
    placer(env).cycle()
    assert [x["wo"] for x in line.launched] == ["WO-F014-SWE2-WWDGL-20261103-L29"]
    assert line.launched[0]["--resume-from"] == "WO-F014-SWE1-WWDGL-20261103-L29"
    # a crash after the queue admission and before the launcher started: the restart launches it exactly once
    pl = placer(env)
    real = line.spawn_launch
    line.spawn_launch = lambda argv, wo: (_ for _ in ()).throw(SystemExit("crash"))  # type: ignore[method-assign]
    line.finish("WO-F014-SWE2-WWDGL-20261103-L29")
    with pytest.raises(SystemExit):
        pl.cycle()
    assert queue_rows()["WO-F014-SWE3-WWDGL-20261103-L29"]["state"] == "ADMITTED"
    line.spawn_launch = real  # type: ignore[method-assign]
    second = placer(env).cycle()  # the crashed process still holds the act lock: the second instance observes
    assert second["mode"] == "OBSERVING" and second["error"] == "ACT_LOCK_HELD" and len(line.launched) == 1
    del pl  # the crashed process is gone
    import gc

    gc.collect()
    for _ in range(3):
        placer(env).cycle()
        env["clock"].tick()
    assert [x["wo"] for x in line.launched].count("WO-F014-SWE3-WWDGL-20261103-L29") == 1
    assert not [x for x in line.launched if x["wo"].endswith("L29B")]  # the admitted order itself, not a new name
    # a campaign change under a never-launched order: the old order is closed in the queue, a new name is placed
    line.fail_launch["WO-F014-SWE4-WWDGL-20261103-L29"] = ["GPU_LOCK_HELD"]
    line.finish("WO-F014-SWE3-WWDGL-20261103-L29")
    placer(env).cycle()  # SWE.4 placed; the launch is refused GPU_LOCK_HELD (the line was busy)
    write_campaign(env, [lineage("wwdg-ll", "WWDGL", "20261103-L29", quality=QUALITY, factory_revision="5f19d046")])
    line.revs["5f19d046"] = REV2
    env["clock"].tick()
    placer(env).cycle()
    assert line.launched[-1]["wo"] == "WO-F014-SWE4-WWDGL-20261103-L29B" and line.launched[-1]["rev"] == "5f19d046"
    assert queue_rows()["WO-F014-SWE4-WWDGL-20261103-L29"]["state"] == "BLOCKED"
    env["clock"].tick()
    placer(env).cycle()
    assert [x["wo"] for x in line.launched].count("WO-F014-SWE4-WWDGL-20261103-L29") == 1


# -------------------------------------------------------------------------------------------- owner retry rule
def test_the_same_fingerprint_four_times_stops_the_lineage_and_escalates_once(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", priority=60),
                         lineage("wwdg-ll", "WWDGL", "20261103-L29", priority=50)])
    grant(env)
    pl = placer(env)
    sw2 = [f"WO-F014-SWE2-CRCL-20261103-L30{s}" for s in ("", "B", "C", "D")]
    outs = drive(env, pl, {w: X for w in sw2}, cycles=8)
    launched = [x["wo"] for x in env["line"].launched]
    assert launched[:5] == ["WO-F014-SWE1-CRCL-20261103-L30"] + sw2  # three retries, each from the last passed order
    assert {x.get("--resume-from") for x in env["line"].launched[1:5]} == {"WO-F014-SWE1-CRCL-20261103-L30"}
    v = lin(outs[-1], "crc-ll")
    assert (v["state"], v["reason"], v["strikes"]["count"]) == ("ESCALATED", "SAME_ISSUE_EXCEEDED_3", 4)
    assert "WO-F014-SWE2-CRCL-20261103-L30E" not in launched
    assert launched[5] == "WO-F014-SWE1-WWDGL-20261103-L29"  # the other lineage keeps going
    assert len(env["line"].gh_calls) == 1  # once, however many cycles
    argv = env["line"].gh_calls[0]
    assert argv[:4] == ["issue", "create", "--repo", "jnsagai/forge-c"] and "@" not in " ".join(argv)
    assert "SAME_ISSUE_EXCEEDED_3" in argv[argv.index("--title") + 1]
    esc = [json.loads(x) for x in (LO.supervisor_dir() / "escalations.jsonl").read_text().splitlines()]
    assert [e["status"] for e in esc] == ["CREATED"]


def test_escalation_is_dry_run_testable_and_never_mentions(env):
    e = LO.Escalator(env["line"], "jnsagai/forge-c", dry_run=True, now=env["clock"](), persist=True)
    r = e.raise_once("k1", "line stopped @jnsagai", "ping @owner please")
    assert r["status"] == "DRY_RUN" and env["line"].gh_calls == [] and "@" not in r["title"]
    assert e.raise_once("k1", "x", "y")["deduplicated"] is True


def test_different_fingerprints_keep_retrying(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30")])
    grant(env)
    sw2 = [f"WO-F014-SWE2-CRCL-20261103-L30{LCMP.retry_suffix(n)}" for n in range(1, 8)]
    results = {w: (X if i % 2 == 0 else Y) for i, w in enumerate(sw2)}
    outs = drive(env, placer(env), results, cycles=9)
    launched = [x["wo"] for x in env["line"].launched]
    assert all(w in launched for w in sw2) and env["line"].gh_calls == []
    assert lin(outs[-1], "crc-ll")["state"] != "ESCALATED" and lin(outs[-1], "crc-ll")["strikes"]["count"] == 1


def test_infra_sweeps_and_relaunches_with_backoff(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30")])
    grant(env)
    line, clock = env["line"], env["clock"]
    line.fail_launch["WO-F014-SWE1-CRCL-20261103-L30"] = ["STACK_START_FAILED"]
    pl = placer(env)
    pl.cycle()
    assert len(line.launched) == 1 and line.sweeps == 0
    out = pl.cycle()  # within the backoff: nothing
    nxt = lin(out, "crc-ll")["next"]
    assert len(line.launched) == 1 and nxt["action"] == "RELAUNCH" and nxt["sweep"] and nxt["kind"] == "RELAUNCH_INFRA"
    clock.tick(120)
    pl.cycle()
    assert line.sweeps == 1 and [x["wo"] for x in line.launched] == ["WO-F014-SWE1-CRCL-20261103-L30"] * 2
    pl.cycle()  # the next cycle's queue bookkeeping: launched -> RUNNING (second attempt of the same order)
    q = queue_rows()["WO-F014-SWE1-CRCL-20261103-L30"]
    assert q["state"] == "RUNNING" and len(line.launched) == 2
    # a run that ended on CAPA-122's INFRA_UNAVAILABLE: sweep, then a new order from the last passed part
    line.finish("WO-F014-SWE1-CRCL-20261103-L30")
    clock.tick()
    pl.cycle()
    line.finish("WO-F014-SWE2-CRCL-20261103-L30", "INFRA")
    clock.tick(10)
    pl.cycle()
    assert line.sweeps == 1  # backoff first
    clock.tick(700)
    pl.cycle()
    assert line.sweeps == 2 and line.launched[-1]["wo"] == "WO-F014-SWE2-CRCL-20261103-L30B"
    assert line.launched[-1]["--resume-from"] == "WO-F014-SWE1-CRCL-20261103-L30"


def test_model_convergence_retries_from_the_last_passed_order_and_upstream_defects_take_the_defect_route(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30")])
    grant(env)
    sw4 = "WO-F014-SWE4-CRCL-20261103-L30"
    defect = {"id": "DEF-0001", "detected_phase": "SWE.4", "target_phase": "SWE.2", "status": "OPEN", "kind": "ARCHITECTURE"}
    drive(env, placer(env), {sw4: (X, [defect])}, cycles=8)
    L = env["line"].launched
    up = next(x for x in L if x["wo"] == "WO-F014-SWE2-CRCL-20261103-L30B")
    assert (up["--resume-from"], up["--resume-upto"], up["--stop-after"]) == (sw4, "SWE.2", "SWE.2")
    after = [x["wo"] for x in L[L.index(up) + 1:]]
    assert after[:2] == ["WO-F014-SWE3-CRCL-20261103-L30B", "WO-F014-SWE4-CRCL-20261103-L30B"]
    assert L[L.index(up) + 1]["--resume-from"] == "WO-F014-SWE2-CRCL-20261103-L30B"


def test_factory_defect_waits_then_resumes_when_the_campaign_revision_is_bumped(env):
    lin_ = lineage("crc-hal", "CRCHAL", "20261103-L31")
    write_campaign(env, [lin_])
    grant(env)
    views = ["VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH"]
    sw2 = "WO-F014-SWE2-CRCHAL-20261103-L31"
    outs = drive(env, placer(env), {sw2: views}, cycles=6)
    assert [x["wo"] for x in env["line"].launched][-1] == sw2  # no loop
    v = lin(outs[-1], "crc-hal")
    assert v["state"] == "WAITING" and v["reason"].startswith("WAITING_EXTERNAL_CHANGE")
    write_campaign(env, [{**lin_, "factory_revision": "5f19d046"}])  # the owner/Claude bumps the run revision
    grant(env)  # (the grant is bound to the line policy, not to the campaign file)
    out = placer(env).cycle()
    last = env["line"].launched[-1]
    assert (last["wo"], last["rev"], last["--resume-from"]) == (sw2 + "B", "5f19d046", "WO-F014-SWE1-CRCHAL-20261103-L31")
    assert lin(out, "crc-hal")["state"] == "LAUNCHING" or lin(out, "crc-hal")["state"] in ("RUNNING", "QUEUED")


def test_a_cancelled_run_is_parked_until_the_owner_changes_the_lineage(env):
    lin_ = lineage("crc-ll", "CRCL", "20261103-L30")
    write_campaign(env, [lin_])
    grant(env)
    outs = drive(env, placer(env), {"WO-F014-SWE1-CRCL-20261103-L30": "CANCELLED"}, cycles=4)
    assert len(env["line"].launched) == 1 and lin(outs[-1], "crc-ll")["state"] == "PARKED"
    write_campaign(env, [{**lin_, "priority": 55}])
    placer(env).cycle()
    assert env["line"].launched[-1]["wo"] == "WO-F014-SWE1-CRCL-20261103-L30B"


# ------------------------------------------------------------------------------------------------------- quality
def test_the_quality_minimum_is_passed_through_into_the_order(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", quality=QUALITY)])
    grant(env)
    out = placer(env).cycle()  # the revision cannot carry the block and its effective quality differs: no order
    assert env["line"].launched == [] and lin(out, "crc-ll")["reason"] == "QUALITY_NOT_DELIVERABLE_AT_REVISION"
    env["line"].quality_ok.add(REV1)
    placer(env).cycle()
    rec = env["line"].launched[0]
    q = json.loads(Path(rec["--quality"]).read_text())
    assert q == QUALITY and q["structural_coverage"]["branch"]["minimum"] == 85
    man = json.loads((env["line"].workspace(rec["wo"]) / ".forge-run/manifest.json").read_text())
    assert man["quality"]["requirements_coverage"]["uspec_tested"]["minimum"] == 95
    # the example's own block equal to the campaign's needs no flag
    env["line"].quality_ok.clear()
    env["line"].spec_q["ex-crc-ll"] = QUALITY
    env["line"].launched.clear()
    env["line"].finish(rec["wo"])
    env["clock"].tick()
    write_campaign(env, [lineage("x-ll", "XL", "20261103-L40", quality=QUALITY, example="ex-crc-ll", priority=90)],
                   name="d.yaml", cid="CMP-TEST-2")
    placer(env).cycle()  # x-ll (priority 90) is outside the grant's driver classes: refused; crc-ll goes on
    assert [x["wo"] for x in env["line"].launched] == ["WO-F014-SWE2-CRCL-20261103-L30"]
    env["line"].launched.clear()
    write_campaign(env, [lineage("x-ll", "XL", "20261103-L40", quality=QUALITY, example="ex-crc-ll", priority=90,
                                 driver_class="STM32N6_CRCL")], name="d.yaml", cid="CMP-TEST-2")
    env["line"].finish("WO-F014-SWE2-CRCL-20261103-L30")
    placer(env).cycle()
    x = env["line"].launched[0]
    assert x["wo"] == "WO-F014-SWE1-XL-20261103-L40" and "--quality" not in x  # the revision gives exactly that quality
    spec = json.loads((LO.supervisor_dir() / "line-orders" / f"{x['wo']}.json").read_text())
    assert spec["quality"] == QUALITY and spec["quality_via"] == "REVISION"


def test_a_gap_below_target_but_at_the_minimum_is_accepted_and_reported(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", phases=["SWE.4"],
                                 start={"resume_from": "WO-F014-SWE3-CRCL-20261103-L29", "at": "SWE.4"})])
    grant(env)
    line = env["line"]
    src = line.workspace("WO-F014-SWE3-CRCL-20261103-L29")
    (src / ".forge-run/gates").mkdir(parents=True)
    (src / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-F014-SWE3-CRCL-20261103-L29",
                                                              "created_at": _iso(env["clock"]() - 99),
                                                              "phase_scope": {"stop_after": "SWE.3"}}))
    (src / ".forge-run/gates/gate-log.jsonl").write_text(json.dumps(passed("SWE.3")[1]) + "\n")
    pl = placer(env)
    pl.cycle()
    wo = "WO-F014-SWE4-CRCL-20261103-L30"
    assert line.launched[0]["--resume-from"] == "WO-F014-SWE3-CRCL-20261103-L29"
    line.finish(wo)
    log = line.workspace(wo) / ".forge-run/gates/gate-log.jsonl"
    log.write_text(log.read_text() + json.dumps({"phase": "SWE.4", "step": "quality", "result": "BELOW_TARGET_ACCEPTED",
                                                 "shortfall": ["REQUIREMENT_COVERAGE_BELOW_TARGET:uspec_tested:93.33% "
                                                               "(target 100%, minimum 90% met): UT:SPEC_NOT_VERIFIED:x"]}) + "\n")
    env["clock"].tick()
    out = pl.cycle()
    assert lin(out, "crc-ll")["state"] == "DONE"
    assert out["quality_gaps"] == [{"lineage": "CMP-TEST-1/crc-ll", "wo": wo, "phase": "SWE.4", "metric": "uspec_tested",
                                    "achieved": 93.33, "target": 100.0, "minimum": 90.0,
                                    "code": "REQUIREMENT_COVERAGE_BELOW_TARGET"}]


def test_the_work_order_cli_takes_the_campaign_quality_block(tmp_path, monkeypatch):
    from forge_factory import workorder as WO

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    _ws, m = WO.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-Q-CMP", purpose="ASPICE_ONLY", quality=QUALITY)
    assert m["quality"] == QUALITY and m["quality_source"] == "campaign"
    seen = {}
    monkeypatch.setattr(WO, "run", lambda *a, **k: seen.update(k) or {"work_order": "W", "package": None})
    f = tmp_path / "q.json"
    f.write_text(json.dumps(QUALITY))
    WO.main(["--example", "x", "--wo", "WO-Q-1", "--quality", str(f)])
    assert seen["quality"] == QUALITY
    o = LL.Order(wo="WO-Q-1", rev="82fabdb9", example="0014l", profile="p", model="m", stop_after="SWE.1",
                 quality_file=str(f))
    o.validate()
    assert o.workorder_args()[-3:] == ["--quality", str(f), "--detach"]
    assert LL.parse_extra(f"--quality {f}") == {"quality_file": str(f)}

    class R:
        def __init__(self, src):
            self.src = src

        def read(self, _p):
            return self.src

    assert LL.quality_supported(R(b'ap.add_argument(\n        "--quality",')) and not LL.quality_supported(R(b"x"))


# ---------------------------------------------------------------------------------------------------- disk guard
def test_the_disk_guard_stops_placement_escalates_and_cleans_only_own_old_archived_worktrees(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30")])
    grant(env)
    line, clock = env["line"], env["clock"]
    pl = placer(env)
    drive(env, pl, cycles=2)  # SWE.1 placed and passed, SWE.2 placed
    line.free = 20 * GB
    n = len(line.launched)
    drive(env, pl, cycles=3)
    out = pl.cycle()
    assert len(line.launched) == n and out["disk"] == {"free_gb": 20.0, "min_gb": 30.0, "placing": False}
    assert len([c for c in line.gh_calls if "disk below" in c[c.index("--title") + 1]]) == 1
    # cleanup: own, terminal, packaged, older than 3 days; nothing else
    old = "WO-F014-SWE1-CRCL-20261103-L30"
    pkg = line.workspace(old) / ".forge-run/package.json"
    os.utime(pkg, (clock() - 4 * 86400, clock() - 4 * 86400))
    (line.runs / "WO-FOREIGN-RUN").mkdir(parents=True)
    pt = line.pytest_roots[0]
    for name, age in (("pytest-1", 5), ("pytest-2", 1)):
        (pt / name).mkdir(parents=True)
        os.utime(pt / name, (clock() - age * 86400, clock() - age * 86400))
    out = pl.cycle()
    assert line.removed == [old]
    assert not (pt / "pytest-1").exists() and (pt / "pytest-2").exists() and (line.runs / "WO-FOREIGN-RUN").exists()
    line.free = 200 * GB
    out = pl.cycle()
    assert out["disk"]["placing"]


# ------------------------------------------------------------------------------------------------ feed and floor
def test_the_feed_shows_acting_vs_observing_and_validates(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30"),
                         lineage("crc-hal", "CRCHAL", "20261103-L31",
                                 depends_on={"lineage": "crc-ll", "phase": "SWE.6", "verdict": "PASS"})])
    obs = LC.Observer("local", env["tmp"] / "launch", LC.FabroView(snapshot=env["line"].fabro))
    lc = LC.LineConductor(obs, placer=placer(env))
    feed = lc.cycle(env["clock"]())
    assert feed["supervisor"]["mode"] == "OBSERVE"
    if LC.contract_keys() and "placement" in LC.contract_keys()[0]:
        assert feed["placement"]["mode"] == "OBSERVING" and feed["placement"]["authorization"]["code"] == "AUTH_RECORD_MISSING"
        assert LC.feed_errors(feed) == []
    grant(env)
    env["clock"].tick()
    lc2 = LC.LineConductor(obs, placer=placer(env))
    feed = lc2.cycle(env["clock"]())
    assert feed["supervisor"]["mode"] == "PILOT"
    if LC.contract_keys() and "placement" in LC.contract_keys()[0]:
        st = {x["lineage"].split("/")[1]: x["state"] for x in feed["placement"]["lineages"]}
        assert st == {"crc-ll": "QUEUED", "crc-hal": "WAITING"} or st["crc-ll"] in ("LAUNCHING", "RUNNING")
        assert feed["placement"]["mode"] == "ACTING" and LC.feed_errors(feed) == []
        from forge_factory.lrtx import floor_api

        os.environ["FORGE_FLOOR_SUPERVISOR_FEED"] = str(LC.feed_path())
        try:
            s = floor_api.supervisor_station(env["clock"]())
        finally:
            os.environ.pop("FORGE_FLOOR_SUPERVISOR_FEED")
        assert s["available"] and s["placement"]["mode"] == "ACTING"
    html = (REPO_ROOT / "factory/python/forge_factory/dashboard/static/factory-floor.html").read_text()
    assert "Acting" in html and "Observing" in html and "placement" in html


def test_healthy_act_cycles_make_zero_model_calls(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30"),
                         lineage("crc-hal", "CRCHAL", "20261103-L31",
                                 depends_on={"lineage": "crc-ll", "phase": "SWE.6", "verdict": "PASS"})])
    grant(env)
    LC.GUARD["blocked"] = 0
    LC.install_guard({32397})
    try:
        before = LC.model_calls()
        drive(env, placer(env), until=lambda o: lin(o, "crc-hal")["state"] == "DONE")
        assert LC.model_calls() - before == 0 and len(env["line"].launched) == 12
        import socket

        with pytest.raises(PermissionError):  # the guard is live: a model port is refused and counted
            socket.create_connection(("127.0.0.1", 11434), timeout=1)
        assert LC.model_calls() - before == 1
    finally:
        LC.uninstall_guard()
        LC.GUARD["blocked"] = 0


def test_dry_run_plans_without_writing_or_launching(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30")])
    grant(env)
    out = placer(env, dry_run=True).cycle()
    assert out["mode"] == "DRY_RUN" and env["line"].launched == [] and not queue_rows()
    act = [a for a in out["actions"] if a["action"] == "PLACE"][0]
    assert act["outcome"] == "PLANNED" and act["argv"][:6] == ["launch", "82fabdb9", "WO-F014-SWE1-CRCL-20261103-L30",
                                                               "ex-crc-ll", PROFILE, "--model"]
    assert not (LO.supervisor_dir() / "line-orders").exists() and not (LO.supervisor_dir() / "placement.jsonl").exists()


REPLAY = os.environ.get("FORGE_M3_REPLAY_DIR")


@pytest.mark.skipif(not REPLAY, reason="FORGE_M3_REPLAY_DIR (read-only copy of the Omniverse2 line state) not given")
def test_act_dry_run_replay_over_todays_line_state(tmp_path, monkeypatch):
    src = Path(REPLAY)
    stamp = {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file()}
    monkeypatch.setenv("FORGE_STATE_DIR", str(src / "lrtx/state"))
    monkeypatch.setenv("FORGE_LINE_LAUNCH_DIR", str(src / "launch"))
    monkeypatch.setenv("FORGE_LINE_STACK_ROOT", str(src / "lrtx"))
    monkeypatch.setenv("FORGE_LINE_REPO", str(Path(os.environ.get("FORGE_M3_LINE_REPO", REPO_ROOT))))
    monkeypatch.setenv("FORGE_LINE_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("FORGE_LINE_GPU_LOCK", str(tmp_path / "gpu.lock"))
    snap = json.loads((src / "fabro-snapshot.json").read_text())
    line = LO.RealLine(fabro_snapshot=snap, pytest_roots=[])
    out = LO.Placer(line, dry_run=True, capa_of={}).cycle()
    assert out["mode"] == "DRY_RUN"
    st = {x["lineage"].split("/")[1]: x for x in out["lineages"]}
    assert st["iwdg-hal"]["state"] == "DONE" and st["rcc-ll"]["state"] == "ON_HOLD"
    assert st["crc-ll"]["state"] == "DONE" and st["crc-hal"]["state"] == "WAITING"
    assert st["crc-hal"]["reason"] == "FACTORY_REVISION_PENDING" and st["crc-hal"]["provided_from"] == "WO-F014-SWE6-CRCL-20261103-L24"
    assert st["crc-hal"]["last_good"] == {"phase": "SWE.1", "wo": "WO-F014-SWE1-CRCHAL-20261103-L27"}
    assert st["wwdg-hal"]["state"] == "WAITING"
    (tmp_path / "plan.json").write_text(json.dumps(out, indent=1, default=str))
    assert {p: p.stat().st_mtime_ns for p in src.rglob("*") if p.is_file()} == stamp  # the copy is untouched
