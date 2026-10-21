"""EASA M0: baseline audit, protected paths, append-only store (EASA-T001/T006/T007)."""
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
from forge_factory.assurance import baseline, contracts, protect
from forge_factory.assurance.store import AssuranceStore


def test_classify_truthful_states():
    assert baseline.classify(False, [], []) == "MISSING"
    assert baseline.classify(True, [{"status": "NOT_RUN"}], []) == "SPEC_ONLY"
    assert baseline.classify(True, [{"status": "PASS"}, {"status": "NOT_RUN"}], []) == "PARTIAL"
    assert baseline.classify(True, [{"status": "NOT_RUN"}], ["pkg"]) == "PARTIAL"
    assert baseline.classify(True, [{"status": "PASS"}], ["pkg"]) == "IMPLEMENTED"
    assert baseline.classify(True, [{"status": "CHECKED_WITHOUT_EVIDENCE"}], []) == "SPEC_ONLY"


def test_checked_box_without_evidence_is_reported_not_counted(tmp_path, monkeypatch):
    spec = tmp_path / "specs/006-enhanced-ai-software-assurance"
    spec.mkdir(parents=True)
    run = tmp_path / "evidence/v0.4/runs/EASA-T001"
    run.mkdir(parents=True)
    (run / "latest.json").write_text(json.dumps({"status": "FAIL", "exit_code": 1}))
    (spec / "tasks.md").write_text(
        "- [X] **EASA-T001 [P0]** a ✅ Evidence: `evidence/v0.4/runs/EASA-T001/latest.json`\n"
        "- [X] **EASA-T002 [P0]** narrated only\n- [ ] **EASA-T003 [P0]** open\n")
    monkeypatch.setattr(baseline, "REPO_ROOT", tmp_path)
    st = {t["task"]: t["status"] for t in baseline._tasks("006")}
    assert st == {"EASA-T001": "CHECKED_WITHOUT_EVIDENCE", "EASA-T002": "CHECKED_WITHOUT_EVIDENCE",
                  "EASA-T003": "NOT_RUN"}


def test_live_matrix_and_no_historical_evidence_change():
    before = baseline.evidence_digest()
    rows = {r["feature"]: r for r in baseline.capability_matrix()}
    assert baseline.evidence_digest() == before
    assert rows["005"]["class"] == "PARTIAL"   # AFO merged (PR #6): 66 tasks checked with PASS evidence, 9 owner-gated open
    assert rows["002"]["class"] == "IMPLEMENTED" and rows["002"]["tasks_total"] == 51
    assert rows["006"]["tasks_total"] == 72


def test_locked_archive_mismatch_detected(tmp_path, monkeypatch):
    d = tmp_path / "archives/WO-0002A-STM32N6-RCC-LL-r101"
    d.mkdir(parents=True)
    (d / "x-review.zip").write_bytes(b"tampered")
    (d / "x-review.zip.sha256").write_text("0" * 64 + "  x-review.zip\n")
    monkeypatch.setattr(baseline, "data_root", lambda: tmp_path)
    refs = {r["ref"]: r["status"] for r in baseline.locked_references()}
    assert refs["archive:WO-0002A-STM32N6-RCC-LL-r101"] == "MISMATCH"
    assert refs["archive:WO-0002B-STM32N6-RCC-HAL-r102"] == "NOT_VERIFIABLE"


def _git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    (r / "config/factory").mkdir(parents=True)
    (r / "factory/python/forge_factory/assurance").mkdir(parents=True)
    (r / "config/factory/reliability-policy.yaml").write_text("mode: OBSERVE_ONLY\nauthorization: null\n")
    (r / "config/factory/release-package-policy.yaml").write_text("min: 1\n")
    (r / "factory/python/forge_factory/assurance/x.py").write_text("A = 1\n")
    _git(r, "init", "-q")
    _git(r, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    return r


def _commit(r, rel, text):
    (r / rel).parent.mkdir(parents=True, exist_ok=True)
    (r / rel).write_text(text)
    _git(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "c")
    return _git(r, "rev-parse", "HEAD")


def test_at080_cre_authorization_and_release_policy_edits_are_denied(repo):
    base = _git(repo, "rev-parse", "HEAD")
    c1 = _commit(repo, "config/factory/reliability-policy.yaml", "mode: ACTIVE\nauthorization: {by: agent}\n")
    assert protect.denied(base, c1, repo=repo) == ["M:config/factory/reliability-policy.yaml"]
    c2 = _commit(repo, "config/factory/release-package-policy.yaml", "min: 0\n")
    assert "M:config/factory/release-package-policy.yaml" in protect.denied(c1, c2, repo=repo)
    c3 = _commit(repo, "factory/python/forge_factory/assurance/x.py", "A = 2\n")
    assert protect.denied(c2, c3, repo=repo) == []


def test_store_append_only_supersession_and_first_pass(tmp_path):
    s = AssuranceStore(tmp_path / "db.sqlite3")
    a = s.append("gate", "WO-1:SWE.4", {"state": "BLOCKED"}, actor="easa-gate")
    assert s.append("gate", "WO-1:SWE.4", {"state": "BLOCKED"}, actor="easa-gate") == a   # replay no-op
    b = s.append("gate", "WO-1:SWE.4", {"state": "PASS"}, actor="easa-gate", supersedes=a)
    assert s.current("gate", "WO-1:SWE.4")["record_id"] == b
    assert s.first_pass("gate", "WO-1:SWE.4")["record"] == {"state": "BLOCKED"}
    with pytest.raises(KeyError):
        s.append("gate", "WO-1:SWE.4", {"state": "PASS"}, actor="x", supersedes="easa-gate-nope")
    with sqlite3.connect(s.path) as c, pytest.raises(sqlite3.DatabaseError):
        c.execute("UPDATE easa_records SET record='{}'")
    with sqlite3.connect(s.path) as c, pytest.raises(sqlite3.DatabaseError):
        c.execute("DELETE FROM easa_records")


def test_store_migration_is_additive_on_existing_cre_db(tmp_path):
    from forge_factory.reliability.store import CREStore

    p = tmp_path / "incidents.sqlite3"
    CREStore(p)
    with sqlite3.connect(p) as c:
        before = {r[0]: r[1] for r in c.execute("SELECT name, sql FROM sqlite_master WHERE name NOT LIKE '%easa%'")}
    assert AssuranceStore(p).version() == 1 and AssuranceStore(p).migrate() == []   # idempotent
    with sqlite3.connect(p) as c:
        after = {r[0]: r[1] for r in c.execute("SELECT name, sql FROM sqlite_master WHERE name NOT LIKE '%easa%'")}
    assert after == before


def test_contract_tooling_validates_schemas_and_rejects_invalid():
    for name in contracts.SCHEMAS:
        assert contracts.schema(name)["type"] == "object"
    pol = contracts.load(contracts.POLICY_EXAMPLE)
    assert contracts.errors("assurance-policy", pol) == []
    bad = dict(pol, allow_change_asil_from_profile=True)
    assert any("allow_change_asil_from_profile" in e for e in contracts.errors("assurance-policy", bad))
    assert contracts.errors("safety-scope", {}) != []
    digests = contracts.contract_digests()
    assert len([k for k in digests if k.endswith(".schema.json")]) == 13


# ---- T003 / AT-003 / AT-073: frozen baseline manifests ------------------------------------------------------------
import hashlib  # noqa: E402
import zipfile  # noqa: E402

from forge_factory.assurance import audit, compat, impact, regress  # noqa: E402
from forge_factory.common import data_root, sha256_file  # noqa: E402


def _pkg(tmp_path, summary=None, extra=b"x"):
    z = tmp_path / "forge-c-WO-T-review.zip"
    files = {"manifest.json": json.dumps({"run_id": "WO-T", "status": "BLOCKED",
                                          "safety_target": "ISO 26262-6:2018 ASIL B evidence candidate"}).encode(),
             "evidence/operations/run/run-summary.json": json.dumps(summary or {"workspace_head": "abc1234def",
                                                                                 "dirty": True}).encode(),
             "evidence/software/src/a.c": extra}
    sums = "".join(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in files.items())
    with zipfile.ZipFile(z, "w") as f:
        for n, b in {**files, "SHA256SUMS.txt": sums.encode()}.items():
            f.writestr(n, b)
    (tmp_path / (z.name + ".sha256")).write_text(f"{sha256_file(z)}  {z.name}\n")
    return z


def test_at003_freeze_is_read_only_and_reports_unknowns(tmp_path):
    z = _pkg(tmp_path)
    before = sha256_file(z)
    fr = audit.freeze(z)
    assert sha256_file(z) == before and fr["sidecar_match"] and fr["sha256sums_mismatch"] == []
    assert {u["fact"] for u in fr["unknown_facts"]} >= {"factory_revision", "fabro_run_id", "model_per_role",
                                                         "silicon_revision", "approved_safety_scope"}
    assert {c["code"] for c in fr["unsupported_claims"]} == {"SAFETY_TARGET_WITHOUT_APPROVED_SCOPE",
                                                             "BUILT_FROM_DIRTY_WORKSPACE"}


def test_at073_swapped_commit_is_stale_baseline_and_changed_bytes_stale_digest(tmp_path):
    z = _pkg(tmp_path)
    fr = audit.freeze(z)
    assert audit.verify(fr, z, "abc1234") == []
    assert audit.verify(fr, z, "fffffff")[0].startswith("STALE_BASELINE")
    z2 = _pkg(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path, extra=b"tampered")
    issues = audit.verify(fr, z2, "abc1234")
    assert "STALE_DIGEST:archive" in issues and "MEMBER_CHANGED:evidence/software/src/a.c" in issues


@pytest.mark.skipif(not (data_root() / "archives/WO-0002A-STM32N6-RCC-LL-r101").is_dir(), reason="archive volume absent")
def test_real_r101_r102_frozen_manifests_match_sealed_bytes():
    for wo, n in (("WO-0002A-STM32N6-RCC-LL-r101", 148), ("WO-0002B-STM32N6-RCC-HAL-r102", 169)):
        z = data_root() / "archives" / wo / f"forge-c-{wo}-review.zip"
        fr = audit.freeze(z)
        assert fr["sidecar_match"] and fr["member_count"] == n and fr["sha256sums_mismatch"] == []
        committed = json.loads((Path(__file__).resolve().parents[3] / f"evidence/easa/baselines/{wo}.json").read_text())
        assert committed["archive_sha256"] == fr["archive_sha256"] and committed["members"] == fr["members"]


# ---- T004 / AT-004: regression evidence with negative controls ---------------------------------------------------
def test_at004_negative_spec_controls_fail_and_valid_passes(tmp_path):
    import sys

    good = regress.run_check("g", [sys.executable, str(regress.SPEC / "validate_spec.py")], "pass", [])
    assert good["status"] == "PASS" and good["exit_code"] == 0 and len(good["output_sha256"]) == 64
    for m in ("46-methods", "checked-entry"):
        d = regress.negative_spec_copy(tmp_path, m)
        bad = regress.run_check(m, [sys.executable, str(d / "validate_spec.py")], "fail", [])
        assert bad["exit_code"] != 0 and bad["status"] == "PASS"     # the invalid input was rejected
    wrong = regress.run_check("w", [sys.executable, str(regress.SPEC / "validate_spec.py")], "fail", [])
    assert wrong["status"] == "FAIL"                                  # a negative control that passes is a FAIL


# ---- T007 / AT-007 / AT-077: migration compatibility and impact --------------------------------------------------
def test_at007_migration_on_copy_of_db_keeps_existing_shape(tmp_path):
    from forge_factory.reliability.store import CREStore

    live = tmp_path / "incidents.sqlite3"
    CREStore(live)
    with sqlite3.connect(live) as c:
        c.execute("INSERT INTO cre_events (event_id, type, ts_utc, record) VALUES ('e1','t','now','{}')")
    before = sha256_file(live)
    r = compat.db_check(live)
    assert r["status"] == "PASS" and r["applied_first"] == [1] and r["applied_second"] == [] and r["changed"] == []
    assert sha256_file(live) == before                              # live file never migrated by the check
    assert compat.db_check(tmp_path / "absent.sqlite3")["status"] == "NOT_VERIFIABLE"


def test_at077_dependency_change_invalidates_dependents_first_pass_kept(tmp_path):
    s = AssuranceStore(tmp_path / "db.sqlite3")
    g = impact.ImpactGraph()
    g.add("req:SWR-013", "r1")
    g.add("code:hal_rcc.c", "c1")
    g.add("test:UT-003b", "t1", ["req:SWR-013", "code:hal_rcc.c"])
    g.add("verif:run_unit", "v1", ["test:UT-003b", "code:hal_rcc.c"])
    g.add("claim:SWR-013-verified", "k1", ["verif:run_unit"])
    g.add("claim:unrelated", "k2", [])
    first = s.append("claim", "claim:SWR-013-verified", {"status": "SUPPORTED"}, actor="easa")
    assert g.change("req:SWR-013", "r1") == []
    hit = g.change("req:SWR-013", "r2", store=s)
    assert hit == ["claim:SWR-013-verified", "test:UT-003b", "verif:run_unit"]
    assert "claim:unrelated" not in hit and g.stale() == ["test:UT-003b"]
    assert s.current("impact", "claim:SWR-013-verified")["record"]["status"] == "REVALIDATION_REQUIRED"
    assert s.get(first)["record"] == {"status": "SUPPORTED"}
