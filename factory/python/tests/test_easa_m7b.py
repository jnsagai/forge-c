"""EASA-T061 (protected-path history), T063/T070 (readiness record, assurance case summary)."""
import subprocess

import pytest
from forge_factory.assurance import contracts, history, readiness


def _git(r, *a):
    return subprocess.run(["git", *a], cwd=r, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    (r / "evidence/runs").mkdir(parents=True)
    (r / "config/factory").mkdir(parents=True)
    (r / "evidence/runs/old.json").write_text("{}")
    (r / "config/factory/reliability-policy.yaml").write_text("mode: OBSERVE_ONLY\n")
    _git(r, "init", "-q")
    _git(r, "-c", "user.email=o@o", "-c", "user.name=o", "add", ".")
    _git(r, "-c", "user.email=o@o", "-c", "user.name=o", "commit", "-qm", "base")
    return r


def _commit(r, msg, **files):
    for rel, text in files.items():
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    _git(r, "-c", "user.email=a@a", "-c", "user.name=a", "add", ".")
    _git(r, "-c", "user.email=a@a", "-c", "user.name=a", "commit", "-qm", msg)


AGENT = "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def test_t061_agent_edit_of_existing_evidence_or_policy_is_a_violation(repo):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "add run" + AGENT, **{"evidence/runs/new.json": "{}"})
    assert history.check(base, repo=repo)["status"] == "PASS"
    _commit(repo, "fix evidence" + AGENT, **{"evidence/runs/old.json": '{"status": "PASS"}'})
    _commit(repo, "relax policy" + AGENT, **{"config/factory/reliability-policy.yaml": "mode: ACTIVE\n"})
    r = history.check(base, repo=repo)
    assert r["status"] == "FAIL" and len(r["violations"]) == 2
    assert any(v.endswith("M:evidence/runs/old.json") for v in r["violations"])
    _commit(repo, "Owner decision 2026-10-17: pilot" + AGENT, **{"config/factory/reliability-policy.yaml": "mode: PILOT\n"})
    _commit(repo, "owner edit", **{"config/factory/reliability-policy.yaml": "mode: OBSERVE_ONLY\n"})
    kinds = [x["kind"] for x in history.check(base, repo=repo)["protected_changes"]][-2:]
    assert kinds == ["OWNER_DECISION_OR_ORACLE_COMMIT", "OWNER_AUTHORED"]


def test_t070_readiness_record_matches_contract_and_never_approves():
    rec = readiness.record("OBSERVE_ONLY", None, ["owner: safety scope (QM/ASIL) not recorded"])
    assert contracts.errors("assurance-readiness", rec) == [] and rec["safety_approval"] is None
    assert rec["technical_gates"] == "NOT_DEMONSTRATED" and rec["normative_catalog_status"] == "UNVERIFIED"
    txt = readiness.case_summary(rec, [{"claim": "SWE.4 tests detect behavioural faults", "status": "UNSUPPORTED",
                                        "evidence": "r102 survivor LT_TO_LE@21"}], ["Renode is not HIL"])
    from forge_factory.assurance.normative import compliance_assertions

    assert compliance_assertions(txt) == [] and "not a safety sign-off" in txt
