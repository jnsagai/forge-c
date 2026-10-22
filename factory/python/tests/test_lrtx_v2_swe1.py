"""Feature 011 M3 (F011-T020..T023): the semantic-first SWE.1 author of local-rtx-v2 with a scripted model and the
real pinned SafeC engine.

The model only chooses intents. SafeC validates them, Forge-C renders the requirements, and the assembled work
products must pass the UNCHANGED SWE.1 author gate. A wrong value comes back as the engine's named finding with
its repair. The same rejected answer twice stops the task as STUCK.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import runner, swe1
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1_semantic as SEM
from test_lrtx_swe1 import _gate, _scripted

V2 = yaml.safe_load((REPO_ROOT / "config/factory/profiles/local-rtx-v2.yaml").read_text())
ENGINE = Path(V2["safec"]["engine"]["binary"])
DS = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/DS14791-rev9-stm32n6x5-x7-datasheet.md"
pytestmark = pytest.mark.skipif(not (ENGINE.is_file() and DS.is_file()),
                                reason="pinned SafeC engine or owner inputs (git-ignored) not on this host")


def _ws(tmp_path, monkeypatch, example: str, wo: str, peripheral: str):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    from forge_factory import workorder
    from forge_factory.workflow.builder import binding_for, build

    w, _m = workorder.prepare(REPO_ROOT / "examples" / example, wo)
    _g, nodes = build(wo, layer="LL", trace=True, peripheral=peripheral)
    binding_for(wo, str(w), nodes).dump(w / ".forge-run/binding.json")
    man = json.loads((w / ".forge-run/manifest.json").read_text())
    man["local_profile"] = {"id": "local-rtx-v2", "version": 1, "config": "config/factory/profiles/local-rtx-v2.yaml",
                            "config_sha256": "0" * 64, "status": V2["status"]}
    (w / ".forge-run/manifest.json").write_text(json.dumps(man, indent=2))
    return w


@pytest.fixture()
def iwdg(tmp_path, monkeypatch):
    return _ws(tmp_path, monkeypatch, "0009a-iwdg-ll", "WO-T-V2-IWDG", "iwdg")


FN = {"start": "LL_IWDG_Enable", "refresh": "LL_IWDG_ReloadCounter", "unlock": "LL_IWDG_EnableWriteAccess",
      "lock": "LL_IWDG_DisableWriteAccess", "prescaler": "LL_IWDG_SetPrescaler", "reload": "LL_IWDG_SetReloadCounter",
      "onf": "LL_IWDG_IsActive", "pvu": "LL_IWDG_IsActiveFlag_PVU", "rvu": "LL_IWDG_IsActiveFlag_RVU"}


def _i(key, request, field, action, facts, value=None):
    d = {"key": key, "function": FN.get(key, "LL_IWDG_Other"), "request": request, "field": field, "action": action,
         "source_fact_ids": facts}
    if value is not None:
        d["logical_value"] = value
    return d


SEM_ANSWERS = {
    "requirements:IWDG_KR": {"intents": [
        _i("start", "start the watchdog", "IWDG_KR.KEY", "write_key_sequence", ["F-IWDG_KR-KEY-V-CCCC"], "0xCCCC"),
        _i("refresh", "refresh the watchdog counter", "IWDG_KR.KEY", "write_key_sequence", ["F-IWDG_KR-KEY-V-AAAA"],
           "0xAAAA"),
        _i("unlock", "enable write access to the configuration registers", "IWDG_KR.KEY", "write_key_sequence",
           ["F-IWDG_KR-KEY-V-5555"], "0x5555"),
        # as qwen3-coder:30b answered in the M3 trial (2026-10-22): the key from its cited fact, no logical_value
        _i("lock", "disable write access to the configuration registers", "IWDG_KR.KEY", "write_key_sequence",
           ["F-IWDG_KR-KEY-V-0"])], "not_covered": [], "open_points": []},
    "requirements:IWDG_PR": {"intents": [
        _i("prescaler", "set the prescaler divider", "IWDG_PR.PR", "write_field", ["F-IWDG_PR-PR"], "5")],
        "not_covered": [], "open_points": []},
    "requirements:IWDG_RLR": {"intents": [
        _i("reload", "set the counter reload value", "IWDG_RLR.RL", "write_field", ["F-IWDG_RLR-RL"], "4095")],
        "not_covered": [], "open_points": []},
    "requirements:IWDG_SR_1": {"intents": [
        _i("onf", "query the watchdog enable status", "IWDG_SR.ONF", "read_field", ["F-IWDG_SR-ONF"])],
        "not_covered": [{"field": "IWDG_SR.EWIF", "reason": "early wake-up interrupt out of scope"},
                        {"field": "EWU", "reason": "early wake-up interrupt out of scope"}], "open_points": []},
    "requirements:IWDG_SR_2": {"intents": [
        _i("pvu", "query the prescaler update flag", "IWDG_SR.PVU", "read_field", ["F-IWDG_SR-PVU"]),
        _i("rvu", "query the reload update flag", "IWDG_SR.RVU", "read_field", ["F-IWDG_SR-RVU"])],
        "not_covered": [{"field": "IWDG_SR.WVU", "reason": "window option out of scope"}], "open_points": []},
    "requirements:crosscutting": {"rules": ["status_query_no_wait", "write_only_named_field"],
                                  "open_points": ["none observed"]},
}


def test_runner_dispatch_is_by_profile_only(iwdg, tmp_path):
    assert runner.author_module(iwdg, "author", "SWE.1") == "swe1_semantic"
    assert runner.author_module(iwdg, "author", "SWE.2") == "swe2"
    assert runner.author_module(iwdg, "inspect", "SWE.1") == "swe1"
    assert runner.inspector_module(iwdg, "SWE.1") == "review_semantic"
    assert runner.inspector_module(iwdg, "SWE.2") == "review"
    man = json.loads((iwdg / ".forge-run/manifest.json").read_text())
    man["local_profile"]["id"] = "local-rtx-v1"
    (iwdg / ".forge-run/manifest.json").write_text(json.dumps(man))
    assert runner.author_module(iwdg, "author", "SWE.1") == "swe1"
    assert runner.inspector_module(iwdg, "SWE.1") == "review"
    (iwdg / ".forge-run/manifest.json").write_text(json.dumps({k: v for k, v in man.items() if k != "local_profile"}))
    assert runner.author_module(iwdg, "author", "SWE.1") == "swe1"


def test_semantic_visit_renders_work_products_the_unchanged_gate_freezes(iwdg, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, calls))
    rep = SEM.visit(iwdg, "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    md = (iwdg / swe1.REQS).read_text()
    assert ("When LL_IWDG_Enable is called to start the watchdog, the IWDG LL driver shall write the key value 0xCCCC "
            "to IWDG_KR.KEY.") in md
    assert ("When LL_IWDG_SetReloadCounter is called to set the counter reload value with a value from 0 to 4095, the "
            "IWDG LL driver shall write that value to IWDG_RLR.RL.") in md
    assert "passes when IWDG_KR equals 0x0000cccc" in md
    assert "SafeC register-io: ERRATA_NOT_BASELINED" in md
    assert ("While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register."
            in md)
    assert "When the caller queries a status flag, the IWDG LL driver shall return the value read" in md
    eff = {e["case"]: e for e in json.loads((iwdg / swe1.EFFECTS).read_text())["effects"]}
    assert (eff["START"]["op"], eff["START"]["value"]) == ("write", "0xCCCC")
    assert (eff["LOCK"]["op"], eff["LOCK"]["value"]) == ("write", "0x0")
    assert eff["ONF"]["op"] == "no_write"
    sem = json.loads((iwdg / ".forge-run/lrtx/SWE.1/semantic.json").read_text())
    assert len(sem["contract_semantic_digest"]) == 64 and sem["engine"]["binary_sha256"] == V2["safec"]["engine"][
        "binary_sha256"]
    # the model answers were intents only: no packet asked for statements, masks or pages
    reg_calls = [p for p in calls if p["task"] != "requirements:crosscutting"]
    assert reg_calls and all("intents" in p["output_schema"]["properties"] for p in reg_calls)
    cross = [p for p in calls if p["task"] == "requirements:crosscutting"]
    assert cross and all(set(p["output_schema"]["properties"]) == {"rules", "open_points"} for p in cross)
    assert _gate(iwdg, monkeypatch) == 0  # frozen by the unchanged SWE.1 author gate


def test_mask_as_value_is_repaired_with_the_engines_finding(iwdg, monkeypatch):
    calls = []
    bad = {"intents": [_i("prescaler", "set the prescaler divider", "IWDG_PR.PR", "write_field", ["F-IWDG_PR-PR"],
                          "16")], "not_covered": [], "open_points": []}

    def pr(p):
        return SEM_ANSWERS["requirements:IWDG_PR"] if p["findings"] else bad
    monkeypatch.setattr(S, "call", _scripted({**SEM_ANSWERS, "requirements:IWDG_PR": pr}, calls))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    pr_calls = [p for p in calls if p["task"] == "requirements:IWDG_PR"]
    assert len(pr_calls) == 2 and "RIO-VALUE-OVERFLOW" in pr_calls[1]["findings"][0]


def test_an_identical_rejected_answer_stops_the_task_as_stuck(iwdg, monkeypatch):
    calls = []
    inverted = {"intents": [_i("start", "start the watchdog", "IWDG_KR.KEY", "write_key_sequence",
                               ["F-IWDG_KR-KEY-V-AAAA"], "0xCCCC")], "not_covered": [], "open_points": []}
    monkeypatch.setattr(S, "call", _scripted({**SEM_ANSWERS, "requirements:IWDG_KR": inverted}, calls))
    rep = SEM.visit(iwdg, "qwen3-coder:30b")
    assert rep["status"] == "FAILED"
    kr = [p for p in calls if p["task"] == "requirements:IWDG_KR"]
    assert len(kr) == 2  # the repair returned the same intents: STUCK, no third call
    assert any("STUCK" in i for i in rep["issues"]) and any("RIO-KEY-FACT-MISMATCH" in i for i in rep["issues"])
    assert not (iwdg / swe1.REQS).is_file()  # nothing partial is assembled


def test_scope_and_schema_keep_the_model_inside_its_task(iwdg):
    ctx = SEM.Context(iwdg)
    g = next(g for g in swe1.groups(swe1.inventory(iwdg)) if g["id"] == "IWDG_KR")
    schema = SEM.group_schema(g, ctx)
    it = schema["properties"]["intents"]["items"]["properties"]
    assert it["field"]["enum"] == ["IWDG_KR.KEY"]
    assert set(it["source_fact_ids"]["items"]["enum"]) == {"F-IWDG_KR-KEY", "F-IWDG_KR-KEY-V-AAAA",
                                                           "F-IWDG_KR-KEY-V-5555", "F-IWDG_KR-KEY-V-CCCC",
                                                           "F-IWDG_KR-KEY-V-0"}
    assert S.validate({"intents": [{"key": "x1", "function": "LL_IWDG_Enable", "request": "start the watchdog",
                                    "field": "IWDG_PR.PR",
                                    "action": "set_field", "source_fact_ids": ["F-IWDG_KR-KEY"]}],
                       "not_covered": [], "open_points": []}, schema)
    errs = SEM.local_checks(iwdg, {"intents": [_i("w", "set the window", "IWDG_KR.KEY", "write_key_sequence",
                                                  ["F-IWDG_KR-KEY-V-5555"], "0x5555")], "not_covered": [
        {"field": "IWDG_KR.KEY", "reason": "x"}], "open_points": []}, g)
    assert any("also listed in not_covered" in e for e in errs)


@pytest.mark.parametrize("sysname", ["IWDG LL driver", "RCC LL driver"])
def test_every_catalogue_rule_renders_ears_conformant(sysname):
    """Trial batch 2: a rendered rule the model cannot repair must pass the unchanged EARS checker by construction."""
    from forge_factory.inspection.ears import Requirement, check_statement

    texts = [r["statement"].format(sys=sysname) for r in SEM.CROSS_RULES.values()]
    texts.append(SEM.STARTUP_RULE["statement"].format(sys=sysname, layer="LL", pfx=sysname.split()[0]))
    for t in texts:
        assert check_statement(Requirement("x", t, 0), {sysname}).findings == [], t


def test_the_named_function_binds_swe2_to_the_exact_name(iwdg, monkeypatch):
    """F011-T031: the rendered requirement names the LL function, so the unchanged SWE.2 rule forces that exact name
    (the IsActive/IsEnabled drift of the feature 010 SWE.2 trial becomes an actionable finding)."""
    from forge_factory.lrtx import swe2

    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    reqs = swe2.requirements(iwdg)
    named = {n for t in reqs.values() for n in swe2._fn_rx(iwdg).findall(t)}
    assert {"LL_IWDG_Enable", "LL_IWDG_IsActive", "LL_IWDG_IsActiveFlag_PVU"} <= named
    g = next(g for g in swe1.groups(swe1.inventory(iwdg)) if g["id"] == "IWDG_KR")
    schema = SEM.group_schema(g, SEM.Context(iwdg))
    bad = {"intents": [{"key": "x1", "function": "HAL_IWDG_Start", "request": "start the watchdog",
                        "field": "IWDG_KR.KEY", "action": "write_key_sequence",
                        "source_fact_ids": ["F-IWDG_KR-KEY-V-CCCC"]}], "not_covered": [], "open_points": []}
    assert S.validate(bad, schema)  # the function prefix is enforced by the schema
