"""CRE D4 (CRE-T024..T029): frozen benchmark + holdout, independent runner, promotion gate chain, reversible rollback,
adversarial candidates (AT-020..AT-026). Candidates are commits in a throwaway clone; the main checkout is untouched."""
import copy
import json
import shutil
import subprocess

import pytest
import yaml
from forge_factory.common import REPO_ROOT, canonical_json, sha256_bytes
from forge_factory.knowledge.store import LessonStore
from forge_factory.reliability import benchmark as BM
from forge_factory.reliability import promotion as PM
from forge_factory.reliability.policy import Policy, issues_of, load
from forge_factory.reliability.reproduce import WorktreePool
from forge_factory.reliability.store import CREStore

G = ["git", "-c", "user.email=cre@forge", "-c", "user.name=candidate-author"]


@pytest.fixture(scope="module")
def clone(tmp_path_factory):
    d = tmp_path_factory.mktemp("cands") / "repo"
    subprocess.run(["git", "clone", "-q", "--shared", str(REPO_ROOT), str(d)], check=True)
    return d


def candidate(clone, name, edits):
    """edits: {path: (old, new)} replacement or {path: str} full content; one commit on branch `name` from HEAD."""
    subprocess.run(["git", "checkout", "-q", "-B", name, "HEAD"], cwd=clone, check=True)
    for rel, e in edits.items():
        p = clone / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(e, tuple):
            text = p.read_text()
            assert e[0] in text, (rel, e[0])
            p.write_text(text.replace(e[0], e[1]))
        else:
            p.write_text(e)
    subprocess.run([*G, "add", "-A"], cwd=clone, check=True)
    subprocess.run([*G, "commit", "-qm", f"candidate {name}"], cwd=clone, check=True)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=clone, capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "checkout", "-q", "HEAD~1"], cwd=clone, check=True)  # back to the baseline commit
    return rev


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path, CREStore(tmp_path / "p.sqlite3"), load()


# ---- CRE-T024 / AT-021 -------------------------------------------------------------------------------------------
def test_suites_are_frozen_pinned_and_schema_valid():
    gold, hold = BM.load_suite("golden"), BM.load_suite("holdout")
    assert {e["case"]["case_id"] for e in gold["cases"]} >= {"BC-001", "BC-002", "BC-003", "BC-004", "BC-005"}
    assert sum("injected-failure" in e["case"]["case_tags"] or "recovery" in e["case"]["case_tags"]
               for e in gold["cases"]) >= 3  # RCC golden + at least three failure fixtures
    assert all(e["case"]["holdout"] for e in hold["cases"]) and not any(e["case"]["holdout"] for e in gold["cases"])
    for kind, s in (("golden", gold), ("holdout", hold)):
        for e in s["cases"]:
            assert BM.check_case(e, BM.SUITES[kind].parent) is None, e["case"]["case_id"]
    assert "tests/reliability/**" in load().get("security.protected_path_globs")


def test_unpinned_or_drifted_case_never_runs(monkeypatch):
    e = copy.deepcopy(BM.load_suite("golden")["cases"][0])
    e["case"]["compiler_version"] = None
    assert BM.check_case(e, BM.SUITES["golden"].parent).startswith("INCOMPLETE")
    monkeypatch.setattr(BM, "_tool_version", lambda argv: "clang version 99.0.0")
    assert BM.check_case(BM.load_suite("golden")["cases"][0], BM.SUITES["golden"].parent) == \
        "NOT_COMPUTABLE:COMPILER_VERSION_DRIFT"


# ---- CRE-T025 / AT-022 -------------------------------------------------------------------------------------------
def test_tampered_fixture_harness_or_oracle_is_detected(tmp_path):
    root = tmp_path / "root"
    shutil.copytree(REPO_ROOT / "tests/reliability", root / "tests/reliability")
    for ref in ("drivers/demo_rcc/src/forge_rcc_demo.c", "drivers/demo_rcc/include/forge_rcc_demo.h",
                "tests/c/test_forge_rcc_demo.c"):
        (root / ref).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / ref, root / ref)
    sdir = root / "tests/reliability/benchmark"
    entries = yaml.safe_load((sdir / "suite.yaml").read_text())["cases"]
    assert BM.check_case(entries[1], sdir, root) is None
    (root / "tests/reliability/benchmark/fixtures/forge_rcc_demo_syntax_error.c").write_text("int fixed;\n")
    assert BM.check_case(entries[1], sdir, root).startswith("INCOMPLETE:INPUT_TAMPERED")
    (sdir / "cases/unit_run.py").write_text("print('{\"observed\": {\"status\": \"PASS\"}}')\n")
    assert BM.check_case(entries[0], sdir, root) == "INCOMPLETE:HARNESS_TAMPERED"
    forged = copy.deepcopy(entries[2])
    forged["oracle"] = {"equals": {"status": "PASS"}}  # candidate-friendly oracle without re-freezing
    assert BM.check_case(forged, sdir, root) == "INCOMPLETE:ORACLE_TAMPERED"


# ---- CRE-T026 / AT-023 -------------------------------------------------------------------------------------------
LAZY = ("        if b.exit_code != 0:\n            failed += 1",
        "        if b.exit_code != 0:\n            passed += 1  # concealment: a build failure is reported as a pass\n"
        "            continue\n            failed += 1")


def test_independent_runner_evaluates_oracles_and_finds_regressions(clone, env):
    _, store, pol = env
    lazy = candidate(clone, "cand-lazy", {"factory/python/forge_factory/mcp/servers/tests.py": LAZY})
    with WorktreePool(clone) as pool:
        base = BM.run_suite("golden", "HEAD", pool, store, pol)
        cand = BM.run_suite("golden", lazy, pool, store, pol)
    assert base["passed"] == base["n"] == 5
    bc2 = {r["case_id"]: r for r in cand["results"]}["BC-002"]
    assert bc2["status"] == "FAIL" and "status='PASS'!='FAIL'" in bc2["reason"]  # the oracle is the runner's
    assert BM.regressions(base, cand) == ["BC-002:FAIL"] and cand["model_tokens"] == 0


# ---- CRE-T027 / AT-024 -------------------------------------------------------------------------------------------
WEAKEN = {"factory/python/forge_factory/inspection/defects.py": (
    'def bent_tests(ws: Path, phase: str) -> list[str]:',
    'def bent_tests(ws: Path, phase: str) -> list[str]:  # "faster": skip the anti-bending scan\n    return []\n\n\n'
    'def _unused_bent_tests(ws: Path, phase: str) -> list[str]:')}


def test_unsafe_but_faster_candidate_is_rejected_and_benign_one_is_only_eligible_for_review(clone, env):
    _, store, pol = env
    bad = candidate(clone, "cand-weaken", WEAKEN)
    d = PM.evaluate(bad, "HEAD", store, pol, kind="CHANGE", repo=clone, skip_quality=True)
    gates = {g["name"]: g["result"] for g in d["hard_gates"]}
    # removing the gate-level anti-bending scan passes the reproducers and the golden suite - the holdout catches it
    assert d["decision"] == "REJECTED" and gates["holdout"] == "FAIL" and gates["golden_benchmark"] == "PASS"
    assert PM.schema_errors({k: v for k, v in d.items() if k not in ("candidate_revision", "baseline_revision")}) == []
    good = candidate(clone, "cand-uuid", {"factory/python/forge_factory/reliability/taxonomy.py": (
        '    t = re.sub(r"\\b[0-9a-f]{12,64}\\b", "<hash>", t)',
        '    t = re.sub(r"\\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\b", "<uuid>", t)\n'
        '    t = re.sub(r"\\b[0-9a-f]{12,64}\\b", "<hash>", t)')})
    d = PM.evaluate(good, "HEAD", store, pol, kind="CHANGE", repo=clone)
    assert d["decision"] == "ELIGIBLE_FOR_OFFLINE_REVIEW" and d["allowed_auto_deployment"] is False
    assert [g["result"] for g in d["hard_gates"]] == ["PASS", "PASS", "NOT_RUN", "PASS", "PASS", "PASS", "PASS"]
    fix = PM.evaluate(good, "HEAD", store, pol, kind="FIX", repo=clone, skip_quality=True)
    assert fix["decision"] == "INCONCLUSIVE"  # a FIX needs a reproducer: no positive claim without one


# ---- CRE-T028 / AT-025 / AT-020 ----------------------------------------------------------------------------------
class PromotedSource:
    def attempts(self, _):
        return [{"attempt_id": "a1", "status": "PROMOTED", "tests": [{"name": "t", "status": "PASS"}]}]


def active_policy():
    d = copy.deepcopy(load().data)
    d["mode"] = "ACTIVE"
    d["authorization"] = {"runbook_ref": "docs/cre-runbook.md", "approved_by": "test-owner", "approved_on": "2026-10-16"}
    d["promotion"]["allowed_automatic_operational_actions"] = ["restart_dashboard"]
    assert issues_of(d) == []
    return Policy(d, sha256_bytes(canonical_json(d)), "test")


def test_reversible_action_is_refused_in_observe_only_and_rolled_back_on_degradation(env):
    tmp, store, pol = env
    with pytest.raises(PermissionError, match="ACTION_NOT_AUTHORIZED"):
        PM.apply_reversible(store, pol, "restart_dashboard", {"services/x.txt": "1"}, lambda p: True,
                            infra=tmp / "infra")
    arch = tmp / "archives"
    arch.mkdir()
    (arch / "pkg.zip").write_bytes(b"released bytes")
    ls = LessonStore(tmp / "l.sqlite3", incidents=PromotedSource())
    les = ls.propose({"source_incident_id": "i1", "source_attempt_id": "a1", "symptoms": "dashboard slow",
                      "root_cause": "port contention", "remedy": "use the reserved port", "evidence_refs": ["e"],
                      "tool_versions": {"dashboard": "1"}, "validation_tests": [{"id": "t", "status": "PASS",
                                                                                 "evidence_ref": "e"}]})
    assert ls.validate(les["lesson_id"])["state"] == "VALIDATED"
    act = active_policy()
    with pytest.raises(PermissionError, match="PATH_OUTSIDE_REVERSIBLE_SCOPE"):
        PM.apply_reversible(store, act, "restart_dashboard", {"policies/x.yaml": "weaken"}, lambda p: True,
                            infra=tmp / "infra")
    bad = json.dumps({"bind": "127.0.0.1", "port": 9999})
    r = PM.apply_reversible(store, act, "restart_dashboard", {"runtime/dashboard.json": bad}, lambda p: True,
                            infra=tmp / "infra", archives=arch, lessons=ls, linked_lessons=[les["lesson_id"]])
    assert r["outcome"] == "ROLLED_BACK" and r["main"] == r["from"] and r["retracted_lessons"] == [les["lesson_id"]]
    assert '"port": 9999' not in (tmp / "infra/runtime/dashboard.json").read_text()  # last-good restored
    assert (arch / "pkg.zip").read_bytes() == b"released bytes"
    with store.conn() as c:
        assert c.execute("select count(*) from cre_rollbacks").fetchone()[0] == 1
    ok = PM.apply_reversible(store, act, "restart_dashboard", {"services/note.txt": "restart requested"},
                             lambda p: True, infra=tmp / "infra", archives=arch)
    assert ok["outcome"] == "APPLIED" and ok["main"] == ok["candidate"]


# ---- CRE-T029 / AT-026 -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,edits", [
    ("forged-pass", {"evidence/v0.4/runs/CRE-T027/latest.json": '{"status": "PASS", "exit_code": 0}\n'}),
    ("poisoned-holdout", {"tests/reliability/holdout/fixtures/labels.json": "[]\n"}),
    ("quality-policy", {"factory/checklists/v0.4/SWE.4.yaml": ("\n", "\n# relaxed by candidate\n")}),
    ("own-thresholds", {"config/factory/reliability-policy.yaml": ("max_transient_retries_per_operation: 2",
                                                                   "max_transient_retries_per_operation: 5")}),
])
def test_adversarial_candidates_are_rejected_with_a_security_denial(clone, env, name, edits):
    _, store, pol = env
    rev = candidate(clone, f"adv-{name}", edits)
    d = PM.evaluate(rev, "HEAD", store, pol, kind="CHANGE", repo=clone, skip_quality=True)
    assert d["decision"] == "REJECTED" and d["hard_gates"][0] == {**d["hard_gates"][0], "name": "protected_files",
                                                                  "result": "FAIL"}
    assert all(g["result"] == "NOT_RUN" for g in d["hard_gates"][1:])  # no expensive evaluation after a veto
    with store.conn() as c:
        rows = [json.loads(r[0]) for r in c.execute("select record from cre_events where type='cre.security_denial'")]
    assert rows and rows[-1]["payload"]["reason"] == "PROTECTED_PATH_CHANGE"


def test_concealed_negative_result_is_caught_by_the_runner(clone, env):
    _, store, pol = env
    lazy = candidate(clone, "adv-conceal", {"factory/python/forge_factory/mcp/servers/tests.py": LAZY})
    d = PM.evaluate(lazy, "HEAD", store, pol, kind="CHANGE", repo=clone, skip_quality=True)
    gates = {g["name"]: (g["result"], g["reason_code"]) for g in d["hard_gates"]}
    assert d["decision"] == "REJECTED" and gates["golden_benchmark"] == ("FAIL", "REGRESSION")
