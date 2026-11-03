"""CAPA-133: an inspection is bound to the checklist items that apply to its work order, not the whole file."""
import copy
import functools
import json
import shutil
import subprocess

import pytest
import yaml
from forge_factory.common import REPO_ROOT
from forge_factory.inspection import assessment_context, engine
from forge_factory.inspection import item_binding as B
from forge_factory.inspection.engine import Store
from forge_factory.release import aspice

OVERLAY = "factory/checklists/v0.4/SWE.2.yaml"
BASE = "factory/release-manager/checklists/SWE.2.yaml"


@pytest.fixture(autouse=True)
def _scratch(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    B._history.cache_clear()
    yield
    B._history.cache_clear()


def _order(path, layer="LL", purpose=aspice.PURPOSE, trace=False):
    (path / ".forge-run").mkdir(parents=True)
    man = {"work_order": f"WO-T133-{path.name}", "layer": layer, "purpose": purpose, "created_at": "2026-11-03T00:00:00Z",
           "scope": ["synthetic"], "target": {}, "budgets": {}}
    if purpose == aspice.PURPOSE:
        man["aspice_development"] = aspice.binding()
        man[assessment_context.FIELD] = assessment_context.binding(man)
    if trace:
        man["trace_profile"] = "owner-2026-10-17"
    (path / ".forge-run/manifest.json").write_text(json.dumps(man))
    for rel in ("workproducts/SWE.1/software_requirements.md", "workproducts/SWE.2/software_architecture.md"):
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text("# synthetic\n")
    st = Store(path)
    st.deterministic_items = lambda phase, checklist: {}
    st.freeze("SWE.1", "swe1-author")
    return st


def _pass(st, legacy=False):
    bl = st.freeze("SWE.2", "swe2-author")
    checks = st.checklist("SWE.2")["checks"]
    v = {c["id"]: {"verdict": "PASS", "evidence_refs": ["workproducts/SWE.2/software_architecture.md"], "findings": []}
         for c in checks}
    rec = st.record_inspection("SWE.2", "swe2-inspector", bl["baseline_id"], v)
    assert rec["verdict"] == "PASS" and st.gate("SWE.2")["decision"] == "PASS"
    if legacy:  # an inspection recorded before CAPA-133: only the whole-file sha
        p = st.insp / "SWE.2" / f"{rec['inspection_id']}.json"
        data = json.loads(p.read_text())
        data.pop(B.FIELD)
        p.write_text(json.dumps(data))
    return rec


# ---- applicability ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("layer,selector,expected", [
    ("LL", None, True), ("LL", {"layer": ["HAL"]}, False), ("HAL", {"layer": ["HAL"]}, True),
    ("LL+HAL", {"layer": ["HAL"]}, True), ("LL", {"layer": ["LL+HAL"]}, False), ("LL", {"layer": "LL"}, True),
    ("LL", {"layer": ["HAL"], "unknown_key": ["x"]}, False), ("LL", {"unknown_key": ["x"]}, True),
    ("LL", {"purpose": ["QM"]}, False), ("LL", {"purpose": [aspice.PURPOSE]}, True), ("LL", "HAL", True)])
def test_applies_to_selector(tmp_path, layer, selector, expected):
    st = _order(tmp_path / "o", layer)
    item = {"id": "X", **({"applies_to": selector} if selector is not None else {})}
    assert B.applies(item, st.workspace) is expected
    assert (len(st.applicable({"checks": [item]})["checks"]) == 1) is expected


def test_owner_trace_profile_applicability_unchanged(tmp_path):
    item = {"id": "X", "applies_when": "owner_trace_profile"}
    assert not B.applies(item, _order(tmp_path / "a").workspace)
    assert B.applies(item, _order(tmp_path / "b", trace=True).workspace)


def test_item_hash_covers_every_ask_field_but_not_provenance():
    item = {"id": "X", "required": True, "severity_if_failed": "major", "criterion": "c", "evidence": ["e"],
            "deterministic_check": "d", "tool": "t", "applies_to": {"layer": ["HAL"]}, "source": "s"}
    h = B.item_sha256(item)
    assert B.item_sha256({**item, "source": "other", "revisions": [{"x": 1}]}) == h
    for k, v in (("required", False), ("severity_if_failed", "minor"), ("criterion", "c2"), ("evidence", ["e", "f"]),
                 ("deterministic_check", None), ("tool", "t2"), ("applies_to", {"layer": ["LL"]}), ("rules", ["r"])):
        assert B.item_sha256({**item, k: v}) != h, k


# ---- gate on the real SWE.2 checklist, through a scratch repository history -----------------------------------------
def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                   capture_output=True)


@pytest.fixture
def history(tmp_path, monkeypatch):
    """A scratch repository whose checklists start as the real ones (commit A); `edit` commits a changed SWE.2."""
    root = tmp_path / "repo"
    for rel in (OVERLAY, BASE):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, root / rel)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "A")
    monkeypatch.setattr(engine, "load_checklist", functools.partial(engine.load_checklist, root=root))
    monkeypatch.setattr(B, "REPO_ROOT", root)

    def edit(change, commit=True):
        ov = yaml.safe_load((root / OVERLAY).read_text())
        change({c["id"]: c for c in ov["additional_checks"]}, ov)
        (root / OVERLAY).write_text(yaml.safe_dump(ov, sort_keys=False))
        if commit:
            _git(root, "commit", "-qam", "B")
        return ov
    return edit


def _hal_clause(items, ov):
    items["SWE2-08"]["criterion"] = items["SWE2-08"]["criterion"].replace("a timeout path", "a bounded timeout path")


def _revision(layers):
    def change(items, ov):
        old = B.item_sha256(items["SWE2-08"])
        _hal_clause(items, ov)
        items["SWE2-08"]["revisions"] = [{"previous_item_sha256": old, "item_sha256": B.item_sha256(items["SWE2-08"]),
                                          "unchanged_for": {"layer": layers}, "decision": "test"}]
    return change


@pytest.mark.parametrize("legacy", [False, True])
def test_unrelated_item_edit_keeps_verdict_but_applicable_edit_reinspects(tmp_path, history, legacy):
    st = _order(tmp_path / "o")
    _pass(st, legacy)
    history(lambda items, ov: items["SWE2-09"].update(criterion="trace-profile only edit"))  # not applicable: no trace
    assert st.gate("SWE.2")["decision"] == "PASS"
    history(lambda items, ov: items["SWE2-09"].update(source="provenance only"))
    assert st.gate("SWE.2")["decision"] == "PASS"
    history(_hal_clause)  # SWE2-08 applies to LL and has no owner revision record: conservative
    g = st.gate("SWE.2")
    assert g["decision"] == "REINSPECT" and g["reason"] == "INSPECTION_ASSESSMENT_CONTEXT_CHANGED"


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("layer,expected", [("LL", "PASS"), ("HAL", "REINSPECT"), ("LL+HAL", "REINSPECT")])
def test_owner_revision_record_bridges_only_the_listed_layer(tmp_path, history, legacy, layer, expected):
    st = _order(tmp_path / "o", layer)
    _pass(st, legacy)
    history(_revision(["LL"]))
    assert st.gate("SWE.2")["decision"] == expected


def test_revision_record_is_void_after_a_later_edit_of_the_item(tmp_path, history):
    st = _order(tmp_path / "o")
    _pass(st)
    history(_revision(["LL"]))
    assert st.gate("SWE.2")["decision"] == "PASS"
    history(lambda items, ov: items["SWE2-08"].update(criterion=items["SWE2-08"]["criterion"] + " Also X."))
    assert st.gate("SWE.2")["decision"] == "REINSPECT"


@pytest.mark.parametrize("change", [
    lambda items, ov: items["SWE2-07"].update(severity_if_failed="minor"),
    lambda items, ov: items["SWE2-07"].update(evidence=["recorded_verdict"]),
    lambda items, ov: items["SWE2-07"].update(required=False),
    lambda items, ov: items["SWE2-07"].update(deterministic_check="architecture_views"),
    lambda items, ov: ov["additional_checks"].append({**copy.deepcopy(items["SWE2-07"]), "id": "SWE2-10"}),
    lambda items, ov: ov["additional_checks"].append({**copy.deepcopy(items["SWE2-07"]), "id": "SWE2-10",
                                                      "required": False}),
    lambda items, ov: ov["additional_checks"].remove(items["SWE2-07"]),
    lambda items, ov: ov["additional_checks"].reverse(),
    lambda items, ov: items["SWE2-09"].pop("applies_when"),  # becomes applicable
    lambda items, ov: ov.update(version="0.4.1"),
], ids=["severity", "evidence", "required", "deterministic", "added_required", "added_optional", "removed",
        "reordered", "now_applicable", "version"])
def test_conservative_changes_reinspect(tmp_path, history, change):
    st = _order(tmp_path / "o")
    _pass(st, legacy=True)
    history(change)
    assert st.gate("SWE.2")["decision"] == "REINSPECT"


def test_legacy_record_without_resolvable_history_reinspects(tmp_path, history, monkeypatch):
    st = _order(tmp_path / "o")
    _pass(st, legacy=True)
    history(lambda items, ov: items["SWE2-09"].update(criterion="x"))
    assert st.gate("SWE.2")["decision"] == "PASS"
    B._history.cache_clear()
    monkeypatch.setattr(B, "_git", lambda *a: None)  # no git / shallow copy: the inspected checklist is unknown
    assert st.gate("SWE.2")["decision"] == "REINSPECT"


def test_dirty_working_tree_still_resolves_the_committed_history(tmp_path, history):
    st = _order(tmp_path / "o")
    rec = _pass(st, legacy=True)
    history(lambda items, ov: items["SWE2-09"].update(criterion="x"), commit=False)
    assert st.gate("SWE.2")["decision"] == "PASS"  # A (committed) is the recorded checklist
    assert B.recorded(st.workspace, rec, "SWE.2") is not None


def test_new_records_carry_the_item_binding(tmp_path):
    st = _order(tmp_path / "o")
    rec = _pass(st)
    assert rec[B.FIELD] == B.binding(st.workspace, st.checklist("SWE.2"))
    ids = [i for i, _ in rec[B.FIELD]["items"]]
    assert "SWE2-08" in ids and "SWE2-09" not in ids  # SWE2-09 applies only to trace-profile orders


def test_old_context_record_never_binds_a_new_assessment_context(tmp_path):
    st = _order(tmp_path / "o")
    man = json.loads((st.workspace / ".forge-run/manifest.json").read_text())
    context = man.pop(assessment_context.FIELD)
    (st.workspace / ".forge-run/manifest.json").write_text(json.dumps(man))
    _pass(st)
    man[assessment_context.FIELD] = context
    (st.workspace / ".forge-run/manifest.json").write_text(json.dumps(man))
    assert st.gate("SWE.2")["reason"] == "INSPECTION_ASSESSMENT_CONTEXT_CHANGED"
