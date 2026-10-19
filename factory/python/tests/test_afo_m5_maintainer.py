"""AFO M5 (AFO-T045..T053; AT-039/043..051) - Factory Maintainer proposals: allowlist + git-diff veto, isolated
candidate worktree, sandboxed candidate tests without credentials, baseline-failing reproducer + 004 CAPA link,
independent CRE evaluation, append-only records with quarantine, broker that can only make a branch / draft PR, and
the bounded WAITING_EXTERNAL_CHANGE while unrelated orders keep running."""
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
from forge_factory.afo import maintainer as M
from forge_factory.afo import scheduler
from forge_factory.afo.queue import QueueError, Store
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import maintainer as mnt_mcp
from forge_factory.reliability import isolation
from forge_factory.reliability.policy import load as cre_policy
from forge_factory.reliability.store import CREStore
from test_afo_m2_queue import OK, _env, _pilot, repo  # noqa: F401 - the M2 queue fixture and helpers

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
REPRO = ('import sys\nfrom forge_factory import calc\nif calc.add(2, 2) != 4:\n'
         '    print("SYMPTOM_PRESENT:calc.add subtracts")\n    sys.exit(1)\nprint("SYMPTOM_ABSENT")\n')
SIG = "calc.add subtracts"


class Eff(dict):
    mode = "PILOT"

    def get(self, k, d=None):
        return super().get(k, d)


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    """A small factory repo with the shapes that matter: allowlisted code, AFO code, frozen CRE oracles, evidence."""
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv(isolation.MODE_ENV, "none")  # unit tests: plain processes; the sandbox test opts back in
    r = tmp_path / "factory-repo"
    files = {"factory/python/forge_factory/__init__.py": "", "factory/python/forge_factory/calc.py":
             "def add(a, b):\n    return a - b\n", "factory/python/forge_factory/afo/__init__.py": "",
             "factory/python/forge_factory/afo/policy.py": "FLOOR = True\n",
             "tests/reliability/reproducers/manifest.yaml": "reproducers: []\n", "evidence/run.json": "{}\n",
             "config/factory/reliability-policy.yaml": "x: 1\n", "factory/python/tests/afo_candidate/README": "x\n"}
    for rel, text in files.items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_text(text)
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=r, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=r, check=True)
    return r


def _head(r: Path, ref: str = "HEAD") -> str:
    return subprocess.run(["git", "rev-parse", ref], cwd=r, capture_output=True, text=True, check=True).stdout.strip()


def _commit(src: Path, msg: str = "c") -> str:
    subprocess.run([*GIT, "add", "-A"], cwd=src, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", msg], cwd=src, check=True)
    return _head(src)


def _case(factory, pid="mnt-abcd-a1"):
    return M.prepare(pid, "HEAD", {"order_id": "afo-o1", "incident_id": "INC-1", "reason": "x"}, factory)


def _good_candidate(case):
    M.write_source(case, "factory/python/forge_factory/calc.py", "def add(a, b):\n    return a + b\n")
    M.write_source(case, M.CANDIDATE_TESTS + "rpr_calc.py", REPRO)
    M.write_source(case, M.CANDIDATE_TESTS + "test_calc.py",
                   "from forge_factory import calc\n\n\ndef test_add():\n    assert calc.add(2, 2) == 4\n")


def test_path_policy_separates_maintainer_from_protected_and_decider_paths():
    g = M.protected_globs()
    assert M.path_issue("factory/python/forge_factory/inspection/gate.py", g) is None
    assert M.path_issue(M.CANDIDATE_TESTS + "test_x.py", g) is None
    assert M.path_issue("tests/reliability/reproducers/manifest.yaml", g) == "PROTECTED_PATH"
    assert M.path_issue("evidence/cre/decisions/x.json", g) == "PROTECTED_PATH"
    assert M.path_issue("config/factory/reliability-policy.yaml", g) == "PROTECTED_PATH"
    assert M.path_issue("factory/python/forge_factory/reliability/promotion.py", g) == "MAINTAINER_DENIED_PATH"
    assert M.path_issue("factory/python/forge_factory/afo/policy.py", g) == "MAINTAINER_DENIED_PATH"
    assert M.path_issue("factory/python/forge_factory/registry/agents.py", g) == "MAINTAINER_DENIED_PATH"
    assert M.path_issue("factory/python/tests/test_t009_inspection.py", g) == "NOT_ALLOWLISTED"  # frozen suite
    assert M.path_issue("config/factory/afo-policy.yaml", g) == "NOT_ALLOWLISTED"
    assert M.path_issue("factory/python/forge_factory/../../../etc/passwd", g) == "PATH_TRAVERSAL"


def test_isolated_worktree_os_hardening_and_canonical_writes(factory):
    case = _case(factory)
    src = Path(case["src"])
    assert case["base"] == _head(factory) and src != factory and case["hardened_files"] >= 4
    assert not os.access(src / "tests/reliability/reproducers/manifest.yaml", os.W_OK)    # OS read-only
    assert not os.access(src / "factory/python/forge_factory/afo/policy.py", os.W_OK)
    assert os.access(src / "factory/python/forge_factory/calc.py", os.W_OK)
    for rel, code in [("tests/reliability/reproducers/manifest.yaml", "PROTECTED_PATH"),
                      ("factory/python/forge_factory/afo/policy.py", "MAINTAINER_DENIED_PATH"),
                      ("factory/python/forge_factory/../../evil.py", "PATH_TRAVERSAL"),
                      ("factory/python/tests/test_frozen.py", "NOT_ALLOWLISTED")]:
        with pytest.raises(M.MaintainerDenied) as e:
            M.write_source(case, rel, "x")
        assert e.value.code == code
    (src / "factory/python/forge_factory/link").symlink_to(factory.parent)              # symlink escape attempt
    with pytest.raises(M.MaintainerDenied) as e:
        M.write_source(case, "factory/python/forge_factory/link/x.py", "x")
    assert e.value.code == "SYMLINK"
    (src / "factory/python/forge_factory/link").unlink()
    (src / "factory/python/forge_factory/calc.py").chmod(0o444)
    with pytest.raises(M.MaintainerDenied) as e:
        M.write_source(case, "factory/python/forge_factory/calc.py", "x")
    assert e.value.code == "OS_READ_ONLY"
    with pytest.raises(M.MaintainerDenied):
        M.read_source(case, "evidence/run.json")                                      # holdouts/evidence unreadable
    assert "def add" in M.read_source(case, "factory/python/forge_factory/calc.py")


def test_veto_judges_the_git_diff_not_the_agent(factory):
    base = _head(factory)
    case = _case(factory)
    src = Path(case["src"])
    (src / "factory/python/forge_factory/calc.py").write_text("def add(a, b):\n    return a + b\n")
    good = _commit(src)
    assert M.veto(base, good, factory) == []
    (src / "tests/reliability/reproducers/manifest.yaml").chmod(0o644)                 # a compromised writer
    (src / "tests/reliability/reproducers/manifest.yaml").write_text("reproducers: [x]\n")
    (src / "factory/python/forge_factory/leak.py").write_text(
        "import pathlib\nTOKEN = pathlib.Path('~/.codex/auth.json').expanduser().read_text()\n")
    (src / "factory/python/forge_factory/ship.py").write_text("import os\nos.system('gh pr merge 5 --admin')\n")
    (src / "factory/python/forge_factory/alias").symlink_to("/etc/passwd")
    bad = _commit(src)
    v = M.veto(base, bad, factory)
    assert "PROTECTED_PATH:M:tests/reliability/reproducers/manifest.yaml" in v
    assert "CREDENTIAL_ACCESS:factory/python/forge_factory/leak.py" in v
    assert "SELF_MERGE_OR_DEPLOY:factory/python/forge_factory/ship.py" in v
    assert "SYMLINK:factory/python/forge_factory/alias" in v
    other = subprocess.run([*GIT, "commit-tree", "-m", "x", f"{base}^{{tree}}"], cwd=factory, capture_output=True,
                           text=True, check=True).stdout.strip()
    assert "NOT_DESCENDANT_OF_BASELINE" in M.veto(base, other, factory)


def test_maintainer_mcp_is_the_only_surface_and_is_role_scoped(factory, monkeypatch):
    case = _case(factory)
    p = M.case_dir(case["proposal_id"]) / "case.json"
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": case["src"], "FORGE_ROLE": "afo-factory-maintainer",
                 "FORGE_AFO_MAINT_CASE": str(p)}.items():
        monkeypatch.setenv(k, v)
    op = {x.name: x for x in mnt_mcp.OPERATIONS}
    ok = sdk.invoke("forge-maintainer-mcp", op["write_source"],
                    {"path": "factory/python/forge_factory/calc.py", "content": "def add(a, b):\n    return a + b\n"})
    assert ok["status"] == "PASS"
    bad = sdk.invoke("forge-maintainer-mcp", op["write_source"],
                     {"path": "tests/reliability/reproducers/manifest.yaml", "content": "x"})
    assert bad["status"] != "PASS" and "PROTECTED_PATH" in json.dumps(bad)
    monkeypatch.setenv("FORGE_ROLE", "fabric-repair")                               # infra repair: no source grant
    assert sdk.invoke("forge-maintainer-mcp", op["read_case"], {})["status"] != "PASS"
    monkeypatch.setenv("FORGE_ROLE", "afo-factory-maintainer")
    monkeypatch.setenv("FORGE_AFO_MAINT_CASE", str(factory / "case.json"))           # outside the case root
    (factory / "case.json").write_text("{}")
    assert sdk.invoke("forge-maintainer-mcp", op["read_case"], {})["status"] != "PASS"


def test_maintainer_role_grants_are_distinct_from_fabric_repair():
    from forge_factory.registry.agents import load_agents, preflight
    from forge_factory.registry.mcp_registry import load_registry

    r = preflight(["afo-factory-maintainer"], include_afo=True)
    assert r["status"] == "PASS", r["issues"]
    tools = r["snapshot"]["afo-factory-maintainer"]["allowed_tools"]
    assert tools == sorted(f"forge-maintainer-mcp.{o.name}" for o in mnt_mcp.OPERATIONS)
    roles = {a["id"] if isinstance(a, dict) else a.id: a for a in load_agents(include_afo=True)[0]}
    fr = roles["fabric-repair"]
    fr_tools = fr["allowed_tools"] if isinstance(fr, dict) else fr.allowed_tools
    assert not any(t.startswith("forge-maintainer-mcp.") for t in fr_tools)
    assert not any(t.startswith("forge-repo-mcp.") for t in tools)
    assert not any(k.startswith("forge-maintainer-mcp") for k in load_registry().ops())   # v0.4 view unchanged
    assert isolation.ROLES["maintainer"] not in (isolation.ROLES["repair"], isolation.ROLES["verifier"])


@pytest.mark.skipif(not __import__("shutil").which("podman"), reason="rootless podman not installed")
def test_candidate_tests_run_as_sandbox_uid_without_credentials_or_network(factory, monkeypatch):
    """T052 credential exfiltration: candidate code can read neither the owner's 0600 files nor the Codex profile,
    sees no token variables and has no network."""
    monkeypatch.setenv(isolation.MODE_ENV, "podman")
    monkeypatch.setenv("GH_TOKEN", "ghp_not_for_the_maintainer")
    case = _case(factory, "mnt-sandbox-a1")
    src = Path(case["src"])
    secret = src / "factory/python/forge_factory/owner_secret.txt"
    secret.write_text("s3cret")
    secret.chmod(0o600)
    from forge_factory.common import data_root

    M.write_source(case, M.CANDIDATE_TESTS + "test_exfil.py", (
        "import os, socket, pytest\n\n\ndef test_no_secrets_no_network():\n"
        f"    for p in ({str(secret)!r}, {str(data_root() / 'codex-home/auth.json')!r}):\n"
        "        with pytest.raises(OSError):\n            open(p).read()\n"
        "    assert not [k for k in os.environ if 'TOKEN' in k or k.startswith('GH_')]\n"
        "    with pytest.raises(OSError):\n        socket.create_connection(('1.1.1.1', 53), timeout=2)\n"
        "    with pytest.raises(OSError):\n        open(" + repr(str(src / "factory/python/forge_factory/calc.py"))
        + ", 'a').write('x')\n"))
    r = M.run_tests(case, [M.CANDIDATE_TESTS + "test_exfil.py"])
    assert r["isolation"] == "podman-rootless-subuid"
    assert r["passed"], r["excerpt"]
    M.quarantine(case)


def test_triage_rejects_an_unsupported_claim_and_quarantines(factory):
    store = Store()
    case = _case(factory, "mnt-claim-a1")
    M.write_source(case, "factory/python/forge_factory/calc.py", "def add(a, b):\n    return a + b\n")
    M.write_source(case, M.CANDIDATE_TESTS + "rpr_calc.py", 'print("SYMPTOM_ABSENT")\n')  # "fixed" without proof
    sub = M.submit(case, "fix calc.add sign error", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    assert sub["veto"] == [] and Path(sub["staged"]["manifest"]).is_file()
    rec = M.process(store, case["proposal_id"], CREStore(), cre_policy(),
                    evaluator=lambda *a, **k: pytest.fail("must not be evaluated"))
    assert rec["outcome"] == "REJECTED" and "REPRODUCER_DOES_NOT_FAIL_ON_BASELINE" in rec["cre_promotion_id"]
    assert not Path(case["src"]).exists()                                            # quarantined worktree
    with pytest.raises(M.MaintainerDenied):
        M.publish(store, case["proposal_id"], Eff({"maintenance.enable_factory_maintainer": True}))


def test_safe_proposal_reaches_offline_review_only_and_broker_makes_a_branch(factory):
    store = Store()
    main = _head(factory, "main")
    case = _case(factory, "mnt-safe-a1")
    _good_candidate(case)
    sub = M.submit(case, "fix calc.add sign error", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    seen = {}

    def evaluator(cand, base, cstore, pol, **kw):
        seen.update(kw, cand=cand, base=base)
        return {"decision": "ELIGIBLE_FOR_OFFLINE_REVIEW", "decision_id": "pd-test", "allowed_auto_deployment": False}

    rec = M.process(store, case["proposal_id"], CREStore(), cre_policy(), evaluator=evaluator)
    assert seen["reproducers"] == [sub["staged"]["id"]] and seen["staged_manifest"].is_file()
    assert seen["cand"] == sub["candidate"] and seen["base"] == case["base"]
    assert rec["outcome"] == "ELIGIBLE_FOR_OFFLINE_REVIEW" and rec["auto_deployment_allowed"] is False
    assert rec["capa_id"] == "CAPA-001" and rec["changed_paths"] == sorted([
        "factory/python/forge_factory/calc.py", M.CANDIDATE_TESTS + "rpr_calc.py", M.CANDIDATE_TESTS + "test_calc.py"])
    from forge_factory.reliability.capa import CapaRegistry

    reg = CapaRegistry(CREStore(), cre_policy())
    assert reg.links("CAPA-001", "AFO_PROPOSAL") == [case["proposal_id"]]
    assert reg.must("CAPA-001")["root_cause_status"] == "HYPOTHESIS"                  # a maintainer never verifies
    with pytest.raises(M.MaintainerDenied) as e:
        M.publish(store, case["proposal_id"], Eff())                                  # policy: maintainer disabled
    assert e.value.code == "MAINTAINER_DISABLED_BY_POLICY"
    calls = []

    def runner(argv):
        calls.append(argv)
        if argv[:2] == ["git", "branch"]:                                            # local: real
            return subprocess.run(argv, cwd=factory, capture_output=True, text=True)
        return subprocess.CompletedProcess(argv, 0, "https://example.invalid/pr/7\n", "")  # remote: recorded only

    out = M.publish(store, case["proposal_id"], Eff({"maintenance.enable_factory_maintainer": True}), runner=runner)
    assert out["branch_ref"] == f"afo/proposal/{case['proposal_id']}" and out["pr_url"] is None
    assert calls == [["git", "branch", out["branch_ref"], sub["candidate"]]]          # no push, no PR (policy)
    assert _head(factory, out["branch_ref"]) == sub["candidate"] and _head(factory, "main") == main
    calls.clear()
    out = M.publish(store, case["proposal_id"], Eff({"maintenance.enable_factory_maintainer": True,
                                                     "maintenance.allow_proposal_pr": True}), runner=runner)
    assert [c[:3] for c in calls] == [["git", "push", "origin"], ["gh", "pr", "create"]]
    assert "--draft" in calls[1] and out["pr_url"] == "https://example.invalid/pr/7"
    assert _head(factory, "main") == main                                            # nothing merged or deployed
    assert [h["status"] for h in store.proposal_history(case["proposal_id"])] == [
        "ELIGIBLE_FOR_OFFLINE_REVIEW", "PUBLISHED", "PUBLISHED"]


@pytest.mark.parametrize("argv", [["gh", "pr", "merge", "7"], ["git", "merge", "x"], ["git", "rebase", "main"],
                                  ["git", "push", "origin", "HEAD:main"], ["git", "push", "--force", "origin", "b"],
                                  ["git", "push", "origin", "refs/heads/x:refs/heads/main"],
                                  ["gh", "pr", "create", "--base", "main", "--head", "b"], ["gh", "pr", "ready", "7"]])
def test_broker_guard_refuses_merge_force_main_and_non_draft(argv):
    with pytest.raises(M.MaintainerDenied) as e:
        M.guard(argv)
    assert e.value.code == "BROKER_FORBIDDEN"


def test_malicious_and_regressing_candidates_are_quarantined_append_only(factory):
    """T052: protected-path patch (vetoed before any evaluation) and a candidate the CRE gate rejects (holdout /
    prevention regression) are both quarantined; records cannot be changed; no lesson is created from them."""
    store = Store()
    case = _case(factory, "mnt-evil-a1")
    _good_candidate(case)
    f = Path(case["src"]) / "tests/reliability/reproducers/manifest.yaml"
    f.chmod(0o644)
    f.write_text("reproducers: []  # oracle edited\n")
    sub = M.submit(case, "fix calc and quietly edit the oracle", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    assert sub["staged"] is None and any(v.startswith("PROTECTED_PATH") for v in sub["veto"])
    rec = M.process(store, case["proposal_id"], CREStore(), cre_policy(),
                    evaluator=lambda *a, **k: pytest.fail("a vetoed candidate is never evaluated"))
    assert rec["outcome"] == "QUARANTINED" and "protected_changes_count" not in rec
    case2 = _case(factory, "mnt-regress-a1")
    _good_candidate(case2)
    M.submit(case2, "fix calc.add sign error", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    rec2 = M.process(store, case2["proposal_id"], CREStore(), cre_policy(), evaluator=lambda *a, **k: {
        "decision": "REJECTED", "decision_id": "pd-holdout-fail", "allowed_auto_deployment": False})
    assert rec2["outcome"] == "REJECTED" and rec2["cre_promotion_id"] == "pd-holdout-fail"
    assert not Path(case2["src"]).exists() and not _head(factory, "main") == rec2["candidate_commit"]
    c = sqlite3.connect(store.path)
    for sql in ("UPDATE afo_maintainer_proposals SET status='ELIGIBLE_FOR_OFFLINE_REVIEW'",
                "DELETE FROM afo_maintainer_proposals"):
        with pytest.raises(sqlite3.DatabaseError, match="APPEND_ONLY"):
            c.execute(sql)
    from forge_factory.knowledge.store import LessonStore

    found = LessonStore().find("INSPECTION_FAIL", "afo-o1", None, "SWE.3", 3).get("lessons", [])
    assert not [x for x in found if "mnt-" in json.dumps(x)]


def test_waiting_external_change_is_bounded_and_unrelated_orders_continue(repo, tmp_path, monkeypatch):  # noqa: F811
    """T051/T053 (AT-039/050): order A waits for a validated-but-unapproved source change; B is admitted meanwhile;
    A is finalized BLOCKED at the TTL. Order C gets an approved external change and re-enters with a NEW attempt."""
    s = Store()
    pilot = _pilot(tmp_path, monkeypatch)
    a, _ = s.submit(_env(repo, rid="RCC-HAL-A", name="ma"), repo=repo, max_queued=10)
    for to in ("ADMITTED", "RUNNING", "WAITING_EXTERNAL_CHANGE"):
        s.transition(a, to, "test path to a factory defect")
    b, _ = s.submit(_env(repo, rid="RCC-HAL-B", name="mb"), repo=repo, max_queued=10)
    r = scheduler.cycle(s, "A", eff=pilot, probes=OK)
    assert r["action"] == "admitted" and r["order_id"] == b and s.order(a)["state"] == "WAITING_EXTERNAL_CHANGE"
    ttl = float(pilot.get("budgets.max_order_wall_seconds"))
    r = scheduler.cycle(s, "A", eff=pilot, probes=OK, now=time.time() + ttl - 60)
    assert s.order(a)["state"] == "WAITING_EXTERNAL_CHANGE"                               # still inside the TTL
    r = scheduler.cycle(s, "A", eff=pilot, probes=OK, now=time.time() + ttl + 1)
    assert r["expired_waiting"] == [a] and s.order(a)["state"] == "BLOCKED"
    assert s.order(a)["terminal_reason"].startswith("WAITING_EXTERNAL_CHANGE_TTL")
    c, _ = s.submit(_env(repo, rid="RCC-HAL-C", name="mc"), repo=repo, max_queued=10)
    s.transition(b, "BLOCKED", "free the worker for C")
    for to in ("ADMITTED", "RUNNING", "WAITING_EXTERNAL_CHANGE"):
        s.transition(c, to, "test")
    with pytest.raises(QueueError) as e:
        s.external_change_approved(c, "not-a-sha", "", "op")
    assert e.value.code == "EXTERNAL_CHANGE_UNTRACEABLE"
    s.external_change_approved(c, "481c3ef", "PR #9 merged by owner", "op")
    assert s.order(c)["state"] == "QUEUED" and s.order(c)["waiting_since_epoch"] is None
    r = scheduler.cycle(s, "A", eff=pilot, probes=OK)
    assert r["action"] == "admitted" and r["order_id"] == c and r["attempt_id"].endswith("-a1")
    assert [x["type"] for x in s.events(c)].count("afo.external_change_approved") == 1
