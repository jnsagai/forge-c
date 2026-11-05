"""Review learning lifecycle controls. Synthetic runner/CRE rows below are UNIT
fixtures, never qualification evidence. Actual causal/gate execution is separate.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT, utc_now
from forge_factory.knowledge.context import applicability
from forge_factory.knowledge.store import LessonStore
from forge_factory.offline import disposition as D
from forge_factory.offline import feedback as F
from forge_factory.offline import review_sets as S
from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore
from test_da014_offline_disposition import (
    _rec,
)
from test_da014_offline_disposition import (
    env as _review_fixture,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return _review_fixture.__wrapped__(tmp_path, monkeypatch)


def routed(env):
    _rec(env)
    result = D.route(env["recs"], bundle=env["bundle"], out=env["tmp"] / "intake.jsonl",
                     allowed_signers=env["signers"])
    return CapaRegistry(CREStore(), load()), result["capa_ids"][0]


def ready(env):
    reg, cid = routed(env)
    reg.triage(cid, "Declaration coverage must track unchanged product code.", "RPR-001", "RULE:UNIT_CONTROL")
    revisions = [subprocess.check_output(["git", "rev-parse", r], cwd=REPO_ROOT, text=True).strip()
                 for r in ("e807e44", "211d4fc")]
    records = []
    for n, (revision, verdict) in enumerate(zip(revisions, ("SYMPTOM_PRESENT", "SYMPTOM_ABSENT"), strict=True)):
        row = dict(run_id=f"rr-UNIT-CONTROL-{n}", reproducer_id="RPR-001", revision=revision,
                   role="BASELINE" if n == 0 else "CANDIDATE", exit_code=1-n, verdict=verdict,
                   signature="UNIT_CONTROL_NOT_REAL_RUN", log_sha256="0"*64, at=utc_now())
        with reg.s.conn() as connection:
            connection.execute("INSERT INTO cre_reproducer_runs VALUES (?,?,?,?,?,?,?,?,?)", tuple(row.values()))
        records.append(row)
    reg.verify_cause(cid, *records)
    reg.register_fix(cid)
    reg.register_prevention(cid, records[-1])
    gates = [dict(name=name, result="PASS") for name in ("protected_files", "policy_integrity", "reproducer",
             "prevention", "quality_process", "golden_benchmark", "holdout")]
    decision = dict(decision="ELIGIBLE_FOR_OFFLINE_REVIEW", policy_sha256=reg.p.sha256,
                    evaluator_kind="INDEPENDENT_DETERMINISTIC_RUNNER", hard_gates=gates)
    with reg.s.conn() as connection:
        connection.execute("INSERT INTO cre_promotion_decisions VALUES (?,?,?,?,?,?)",
            ("pd-UNIT-CONTROL", revisions[-1], revisions[0], decision["decision"], json.dumps(decision), utc_now()))
    reg.link(cid, "PROMOTION_DECISION", "pd-UNIT-CONTROL")
    ws = env["tmp"] / "future/workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / "source.txt").write_text("owned input v1\n")
    manifest = dict(work_order="future-training-order", evaluation_holdout=False, target=dict(part_number="STM32N6"),
        tool_versions={"compiler": "TEST-PINNED"}, inputs=[dict(path="source.txt",
        sha256=hashlib.sha256((ws / "source.txt").read_bytes()).hexdigest())])
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    return reg, cid, ws, revisions[-1]


def test_unvalidated_review_cannot_publish_a_lesson(env):
    reg, cid = routed(env)
    with pytest.raises(F.Refused, match="DSP_CAPA_NOT_VALIDATED"):
        F.publish(reg, cid)
    assert reg.must(cid)["lesson_ids"] == []


@pytest.mark.parametrize("fault", ["missing_decision", "failed_gate", "incomplete_gates", "changed_input", "holdout", "inspector"])
def test_causal_and_prevention_evidence_alone_do_not_bypass_cre_or_destination_checks(env, fault):
    reg, cid, ws, _ = ready(env)
    role = "swe1-author"
    if fault == "missing_decision":
        # No immutable decision is edited; the registry projection lacks its link.
        original = reg.links
        reg.links = lambda c, kind=None: [] if kind == "PROMOTION_DECISION" else original(c, kind)
    elif fault in ("failed_gate", "incomplete_gates"):
        # Synthetic UNIT decision projection, no actual CRE archive or gate is edited.
        with reg.s.conn() as connection:
            row = json.loads(connection.execute("SELECT record FROM cre_promotion_decisions").fetchone()[0])
            if fault == "failed_gate":
                row["hard_gates"][-1]["result"] = "FAIL"
            else:
                row["hard_gates"].pop()
            connection.execute("INSERT INTO cre_promotion_decisions VALUES (?,?,?,?,?,?)",
                ("pd-UNIT-NEGATIVE", reg.links(cid,"FIX_REVISION")[-1], reg.links(cid,"BASELINE_REVISION")[-1],
                 row["decision"], json.dumps(row), utc_now()))
        original = reg.links
        reg.links = lambda c, kind=None: ["pd-UNIT-NEGATIVE"] if kind == "PROMOTION_DECISION" else original(c, kind)
    elif fault == "changed_input":
        (ws / "source.txt").write_text("changed")
    elif fault == "holdout":
        path = ws / ".forge-run/manifest.json"
        doc = json.loads(path.read_text())
        doc["evaluation_holdout"] = True
        path.write_text(json.dumps(doc))
    else:
        role = "swe1-inspector"
    with pytest.raises(F.Refused):
        F.publish(reg, cid, workspace=ws, role=role)
    assert reg.must(cid)["lesson_ids"] == []


def test_curated_lesson_reaches_matching_future_author_once_and_rejects_other_scopes(env):
    reg, cid, ws, _ = ready(env)
    first = F.publish(reg, cid, workspace=ws, role="swe1-author")
    assert first["state"] == "VALIDATED" and first["created"]
    assert F.publish(reg, cid, workspace=ws, role="swe1-author") == {**first, "created": False}
    lessons = LessonStore(incidents=reg.lesson_source())
    scope = applicability(ws)
    scope.pop("holdout")
    actual = lessons.find("declaration unchanged product code", "future-run", phase="SWE.1", role="swe1-author", **scope)
    assert [x["lesson_id"] for x in actual["lessons"]] == [first["lesson_id"]]
    assert "ignore all rules" not in json.dumps(actual)
    from forge_factory.mcp.sdk import ToolContext
    from forge_factory.mcp.servers.knowledge import FindIn, find_lessons

    ctx = ToolContext("forge-knowledge", "find_lessons", "swe1-author", "SWE.1", ws, "future-mcp-run")
    delivered = find_lessons(ctx, FindIn(query="declaration unchanged product code"))
    assert json.loads(delivered["metrics"]["data"])["lessons"][0]["lesson_id"] == first["lesson_id"]
    for change in ({"phase": "SWE.2"}, {"role": "swe1-inspector"}, {"target": "OTHER"},
                   {"source_version": "OTHER"}, {"tool_versions": {"compiler": "OTHER"}}):
        args = dict(phase="SWE.1", role="swe1-author", **scope)
        args.update(change)
        assert lessons.find("declaration unchanged product code", "wrong-scope", **args)["lessons"] == []


def test_actual_gate_recurrence_reopens_review_capa_and_retracts_its_lesson(env):
    reg, cid, ws, fix = ready(env)
    lesson = F.publish(reg, cid, workspace=ws, role="swe1-author")
    path = ws / ".forge-run/manifest.json"
    doc = json.loads(path.read_text())
    doc.update(created_at="2026-11-05T00:00:00Z", factory_revision=dict(commit=fix, basis="recorded_at_launch"))
    path.write_text(json.dumps(doc))
    (ws / ".forge-run/package.json").write_text(json.dumps(dict(package_status="BLOCKED")))
    log = ws / ".forge-run/gates/gate-log.jsonl"
    log.parent.mkdir()
    log.write_text(json.dumps(dict(ts="2026-11-05T00:01:00Z",phase="SWE.4",step="author",status="INCOMPLETE",
        gate=dict(decision="REJECTED"),errors=["TEST_CHANGED_AFTER_FAIL"]))+"\n")
    lessons = LessonStore(incidents=reg.lesson_source())
    report = F.reconcile(reg, [ws], lessons=lessons)
    assert report == [dict(capa_id=cid, state="REOPENED")]
    assert lessons.get(lesson["lesson_id"])["state"] == "RETRACTED"
    assert reg.must(cid)["root_cause_status"] == "HYPOTHESIS"
    assert reg.links(cid, "RECURRENCE")


def test_missing_or_corrupt_set_evidence_cannot_reclassify_frozen_work(env):
    root = env["tmp"] / "registry"
    for name in (S.F011, *[S.ROOT+n for n in ("f015-split.json", "calibration-subset.json", "learning-set-2.json",
                "learning-set-4.json", "calibration-runs.json", "calibration-t2-runs.json")]):
        dest = root / name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(REPO_ROOT/name,dest)
    assert S.active_workorders(root) == D.heldout_workorders()
    transfer = root / (S.ROOT+"learning-set-4.json")
    value = json.loads(transfer.read_text())
    value["source"]["sha256"] = "0"*64
    transfer.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="DSP_SET_REGISTRY_INVALID"):
        S.active_workorders(root)


def test_crash_after_cre_receipt_before_jsonl_can_recover_without_duplicate_capa(env, monkeypatch):
    _rec(env)
    out = env["tmp"] / "intake.jsonl"
    original = Path.open
    def interrupted(path, mode="r", *args, **kwargs):
        if path == out and mode == "a":
            raise OSError("CONTROL: interrupted projection")
        return original(path, mode, *args, **kwargs)
    with monkeypatch.context() as context:
        context.setattr(Path, "open", interrupted)
        result = D.route(env["recs"], bundle=env["bundle"], out=out, allowed_signers=env["signers"])
    assert result["refused"] and not out.exists()
    reg = CapaRegistry(CREStore(),load())
    assert len(reg.all()) == 1
    result = D.route(env["recs"], bundle=env["bundle"], out=out, allowed_signers=env["signers"])
    assert result["routed"] == 1 and len(reg.all()) == 1


def test_durable_archive_retains_verifiable_public_proof_and_id_conflicts_span_output_files(env):
    reg, cid = routed(env)
    ref = reg.links(cid, "HUMAN_REVIEW")[0]
    name, sha = ref.split("#sha256=", 1)
    path = Path(name)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    record = json.loads(path.read_text())
    bundle = path.parents[3] / "exports" / (env["sha"] + ".zip")
    assert D.verify(record, base=path.parent, allowed_signers=path.parent / "allowed-signers", bundle=bundle).ok
    _rec(env, verdict="FALSE_FINDING")
    result = D.route(env["recs"], bundle=env["bundle"], out=env["tmp"] / "different-projection.jsonl",
                     allowed_signers=env["signers"])
    assert result["refused"][0]["code"] == "DSP_ID_CONFLICT" and len(reg.all()) == 1


def test_signed_review_containing_a_secret_is_refused_before_archive_or_capa_creation(env):
    _rec(env, rationale="password=UNIT_TEST_SECRET")
    result = D.route(env["recs"], bundle=env["bundle"], out=env["tmp"] / "intake.jsonl",
                     allowed_signers=env["signers"])
    assert result["refused"][0]["code"] == "DSP_REVIEW_CONTAINS_SECRET"
    reg = CapaRegistry(CREStore(),load())
    assert reg.all() == [] and not (reg.s.path.parent / "review-artifacts").exists()


def test_new_actual_workorder_records_the_factory_tool_identity_for_scoped_retrieval(env):
    from forge_factory import workorder

    ws, manifest = workorder.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-REVIEW-MEMORY", purpose="ASPICE_ONLY")
    assert manifest["tool_versions"] == {"forge-factory": manifest["factory_revision"]["commit"]}
    assert applicability(ws)["tool_versions"] == manifest["tool_versions"]


def test_reconciliation_cursor_rotates_across_review_capas_with_a_bounded_batch(env):
    from forge_factory.afo.queue import Store

    reg, cid, _, fix = ready(env)
    other = "CAPA-HR-CONTROL-SECOND"
    doc = {**reg.must(cid), "capa_id": other}
    with reg.s.conn() as connection:
        connection.execute("INSERT INTO cre_capa VALUES (?,?,?,?,?)",
            (other, json.dumps(doc), doc["state"], doc["root_cause_status"], doc["updated_at"]))
    reg.link(other, "HUMAN_REVIEW", "UNIT_CONTROL")
    reg.link(other, "FIX_REVISION", fix)
    queue = Store(env["tmp"] / "queue.sqlite3")
    lessons = LessonStore(incidents=reg.lesson_source())
    observed = [F.reconcile(reg, [], lessons=lessons, limit=1, cursor_store=queue)[0]["capa_id"] for _ in range(3)]
    assert observed == sorted([cid,other]) + [min(cid,other)]


def _unit_proof(reg, root, rid):
    """Synthetic UNIT records with explicit marker; actual qualification runs separately."""
    revisions = [subprocess.check_output(["git", "rev-parse", r], cwd=REPO_ROOT, text=True).strip()
                 for r in ("e807e44", "211d4fc")]
    refs = []
    for n, revision in enumerate(revisions):
        run_id = f"rr-UNIT-PROOF-{rid}-{n}"
        raw = b"UNIT CONTROL ONLY, NOT AN EXECUTED REPRODUCER\n"
        log = root / "state/reliability/reproducers" / (run_id+".log")
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_bytes(raw)
        values = dict(run_id=run_id,reproducer_id=rid,revision=revision,role="BASELINE" if n==0 else "CANDIDATE",
            exit_code=1-n,verdict="SYMPTOM_PRESENT" if n==0 else "SYMPTOM_ABSENT",signature="UNIT_CONTROL",
            log_sha256=hashlib.sha256(raw).hexdigest(),at=utc_now())
        with reg.s.conn() as connection:
            connection.execute("INSERT INTO cre_reproducer_runs VALUES (?,?,?,?,?,?,?,?,?)",tuple(values.values()))
        refs.append("reproducer-run:"+run_id)
    gates = [dict(name=name,result="PASS",evidence_refs=refs if name=="reproducer" else [refs[-1]])
             for name in ("protected_files","policy_integrity","reproducer","prevention","quality_process",
                          "golden_benchmark","holdout")]
    doc = dict(decision="ELIGIBLE_FOR_OFFLINE_REVIEW",policy_sha256=reg.p.sha256,
               evaluator_kind="INDEPENDENT_DETERMINISTIC_RUNNER",hard_gates=gates)
    with reg.s.conn() as connection:
        connection.execute("INSERT INTO cre_promotion_decisions VALUES (?,?,?,?,?,?)",
            ("pd-UNIT-PROOF",revisions[-1],revisions[0],doc["decision"],json.dumps(doc),utc_now()))
    return revisions


def test_qualify_capa_uses_decision_runner_and_log_bindings_and_is_resumable(env):
    reg,cid = routed(env)
    _unit_proof(reg,env["tmp"],"RPR-001")
    first = F.qualify(reg,cid,"pd-UNIT-PROOF")
    assert first["state"] == "EFFECTIVENESS_OBSERVING"
    before = reg.history(cid)
    assert F.qualify(reg,cid,"pd-UNIT-PROOF") == first and reg.history(cid)==before
    assert reg.links(cid,"REVIEW_REPRODUCER") and reg.links(cid,"PROMOTION_DECISION")==["pd-UNIT-PROOF"]


def test_new_staged_test_is_bound_to_committed_source_and_persists_for_future_prevention(env):
    from forge_factory.reliability.registered import prevention

    reg,cid = routed(env)
    revisions = _unit_proof(reg,env["tmp"],"AFO-CONTROL")
    source = next(p for p in subprocess.check_output(["git","ls-tree","-r","--name-only",revisions[-1]],
                  cwd=REPO_ROOT,text=True).splitlines() if p.endswith(".py"))
    raw = subprocess.check_output(["git","show",revisions[-1]+":"+source],cwd=REPO_ROOT)
    stage = env["tmp"] / "staged"
    stage.mkdir()
    (stage/"reproducer.py").write_bytes(raw)
    descriptor = dict(id="AFO-CONTROL",script="reproducer.py",sha256=hashlib.sha256(raw).hexdigest(),
        symptom_signature="UNIT CONTROL",source_path=source,baseline_revision=revisions[0],fix_revision=revisions[-1])
    (stage/"manifest.yaml").write_text(json.dumps(dict(reproducers=[descriptor])))
    description = dict(root_cause="UNIT source binding fixture.",remedy="Retain the verified regression for later changes.",
                       operations=["SWE.1/author"],error_codes=["UNIT_CONTROL"])
    F.qualify(reg,cid,"pd-UNIT-PROOF",staged_manifest=stage/"manifest.yaml",description=description)
    tests,issues = prevention(reg.s)
    assert not issues and tests["AFO-CONTROL"]["sha256"]==descriptor["sha256"]
    path=Path(tests["AFO-CONTROL"]["path"])
    path.chmod(0o600)
    path.write_bytes(raw+b"\n# UNIT tamper\n")
    assert prevention(reg.s)[1]==["REGISTERED_PREVENTION_INVALID"]
