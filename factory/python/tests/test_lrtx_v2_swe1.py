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


def test_swe2_name_drift_from_the_frozen_requirement_is_rejected_with_its_target(iwdg, monkeypatch):
    """F011-AT-024: a clean interface built from the frozen semantic requirements passes the unchanged SWE.2 check;
    renaming the query the requirement names (IsActive -> IsEnabled) is rejected with the requirement, the exact
    name to define and the allocation to fix."""
    import re

    from forge_factory.lrtx import swe2

    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    reqs, cl = swe2.requirements(iwdg), swe2.component_level(iwdg)
    func = {k: v for k, v in reqs.items() if k not in cl}
    rx = swe2._fn_rx(iwdg)
    named = {s: sorted(set(rx.findall(t)) - {n for n in rx.findall(t) if n.endswith(("_OFFSET", "_MSK", "_POS"))})
             for s, t in func.items()}
    eff = swe2.effects(iwdg)
    fields = {}
    for e in eff:
        for n in named[e["swr"]]:
            fields.setdefault(n, set()).add(f"{e['register']}.{e['field']}")
    fns = sorted({n for v in named.values() for n in v})
    params = {e["swr"] for e in eff if e["op"] == "write"}
    doc = {"functions": [{"name": n, "returns": "uint32_t" if "Is" in n else "void",
                          "params": [{"type": "uint32_t", "name": "value"}] if any(
                              n in named[s] for s in params) and "Is" not in n and not swe2._ident(iwdg)["void"] else [],
                          "operation": "op", "fields": sorted(fields.get(n, set()))} for n in fns],
           "allocation": [{"swr": s, "functions": v, "responsibility": "r"} for s, v in named.items()],
           "calls": [{"case": e["case"], "function": named[e["swr"]][0],
                      "args": [str(e["value"]) + "U"] if e["op"] == "write" and not swe2._ident(iwdg)["void"]
                      and "Is" not in named[e["swr"]][0] else []} for e in eff]}
    from forge_factory.assurance.hardware import index

    idx = index(iwdg / "inputs/sections/RM0486")
    clean = [f for f in swe2.validate_interfaces(iwdg, doc, idx) if "argument" not in f]
    assert not [f for f in clean if "names" in f or "not allocated" in f or "not defined" in f], clean
    drift = json.loads(json.dumps(doc).replace('"LL_IWDG_IsActive"', '"LL_IWDG_IsEnabled"'))
    out = swe2.validate_interfaces(iwdg, drift, idx)
    target = [f for f in out if "names LL_IWDG_IsActive, which is not a defined function" in f]
    assert target and all(re.match(r"SWR-\d{3} names", f) for f in target), out
    assert "define the function as LL_IWDG_IsActive" in target[0] and "allocate" in target[0]


# ---- F011-T034: the frozen SWE.1 carries the SafeC register-image oracle; the EASA C oracle runs it ------------------

def _ll_impl(rec: dict, block: str, mutate: dict | None = None) -> str:
    """A header-only LL implementation generated from the contract operations (one function per intent), with
    optional per-function replacement bodies (mutants)."""
    key_fn = {i: FN[i.split(":", 1)[1]] for i in rec["case_of_intent"]}
    lines = ["#include <stdint.h>"]
    for op in rec["operations"]:
        fn, w = key_fn[op["intent_id"]], int(op["offset"], 16) // 4
        mask = op["field_mask"]
        if op["write_kind"] == "none":
            sig, body = f"static inline uint32_t {fn}(void)", f"return ({block}[{w}] & {mask}U) >> {op['lsb']}U;"
        elif op["action"] == "write_field":
            sig = f"static inline void {fn}(uint32_t v)"
            body = f"{block}[{w}] = ({block}[{w}] & ~{mask}U) | ((v << {op['lsb']}U) & {mask}U);"
        elif op["write_kind"] == "full_register_write":
            sig, body = f"static inline void {fn}(void)", f"{block}[{w}] = {op['encoded_value']}U;"
        else:
            sig, body = f"static inline void {fn}(void)", f"{block}[{w}] = ({block}[{w}] & ~{mask}U) | {op['encoded_value']}U;"
        if mutate and fn in mutate:
            body = mutate[fn].format(b=block, w=w)
        lines.append(f"{sig} {{ {body} }}")
    return "\n".join(lines) + "\n"


def test_frozen_swe1_carries_a_verified_oracle_and_the_c_oracle_catches_mutants_on_target(iwdg, monkeypatch, tmp_path):
    """F011-AT-027/028: expected register images come from the contract only. A correct LL implementation passes
    every case from both initial images; an inverted key, an absent write, a wrong read and a read that writes each
    fail on their own case only. A tampered oracle blocks instead of being used."""
    import shutil

    from forge_factory.assurance import oracle_gen
    from forge_factory.assurance import safec_oracle as SO
    from forge_factory.layer import api_header, profile

    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    rep = SEM.visit(iwdg, "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    rec, issues = SO.verified(iwdg)
    assert issues == [] and rec["oracle"]["contract_semantic_digest"] == rec["contract_semantic_digest"]
    eff = json.loads((iwdg / "workproducts/SWE.1/register_effects.json").read_text())["effects"]
    assert set(rec["case_of_intent"].values()) <= {e["case"] for e in eff}
    calls = {}
    for iid, case in rec["case_of_intent"].items():
        op = next(o for o in rec["operations"] if o["intent_id"] == iid)
        calls[case] = {"function": FN[iid.split(":", 1)[1]],
                       "args": [f"{op['logical_value']}U"] if op["action"] == "write_field" else []}
    (iwdg / "workproducts/SWE.2").mkdir(parents=True, exist_ok=True)
    (iwdg / "workproducts/SWE.2/api_calls.json").write_text(json.dumps({"schema": "forge-c/api-calls/1",
                                                                        "calls": calls}))
    (iwdg / "workproducts/SWE.2/software_architecture.md").write_text("# SWE.2 (test stub)\n")
    block, hdr = profile(iwdg)["ll"]["register_block"], api_header("LL", iwdg)

    def run(mutate=None):
        d = tmp_path / ("mut" if mutate else "ok")
        (d / hdr).parent.mkdir(parents=True, exist_ok=True)
        (d / hdr).write_text(_ll_impl(rec, block, mutate))
        return oracle_gen.run(iwdg, [d], [], hdr)

    good = run()
    sc = [r for r in good["results"] if "@0x" in r[2]]
    assert good["status"] == "PASS" and len(sc) == len(rec["oracle"]["cases"]), good.get("reason") or good["results"]
    start, onf = rec["case_of_intent"]["IWDG_KR:start"], rec["case_of_intent"]["IWDG_SR_1:onf"]
    for mutant, case in (({"LL_IWDG_Enable": "{b}[{w}] = 0x0000AAAAU;"}, start),           # inverted key
                         ({"LL_IWDG_Enable": "(void)0;"}, start),                           # absent write
                         ({"LL_IWDG_IsActive": "return ({b}[{w}] >> 1U) & 1U;"}, onf),     # wrong read
                         ({"LL_IWDG_IsActive": "{b}[{w}] = 0U; return 0U;"}, onf)):         # a read that writes
        r = run(mutant)
        failed = {x[2].split("@")[0] for x in r["results"] if x[3] == "FAIL" and "@0x" in x[2]}
        assert r["status"] == "FAIL" and failed == {case}, (mutant, failed)
    raw = json.loads((iwdg / SO.FILE).read_text())
    raw["oracle"]["cases"][0]["expected_after"] = "0x00000000"
    (iwdg / SO.FILE).write_text(json.dumps(raw))
    blocked = run()
    assert blocked["status"] == "BLOCKED" and blocked["reason"].startswith("SAFEC_ORACLE_BLOCKED"), blocked


def test_cbmc_proves_each_register_effect_for_every_initial_value(iwdg, monkeypatch, tmp_path):
    """F011-T035/AT-029: the contract operations become CBMC properties over ANY initial register value on the real
    LL code. A mutant that is wrong only for one initial value passes the four-image C oracle and is FAILED here, on
    its own operation; the correct implementation is PROVED for every operation within the stated model."""
    from forge_factory.assurance import oracle_gen, register_proof
    from forge_factory.assurance.formal import tool
    from forge_factory.layer import api_header, profile

    if tool("cbmc") is None:
        pytest.skip("CBMC not installed on this host")
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    from forge_factory.assurance import safec_oracle as SO

    rec, _ = SO.verified(iwdg)
    calls = {}
    for iid, case in rec["case_of_intent"].items():
        op = next(o for o in rec["operations"] if o["intent_id"] == iid)
        calls[case] = {"function": FN[iid.split(":", 1)[1]],
                       "args": [f"{op['logical_value']}U"] if op["action"] == "write_field" else []}
    (iwdg / "workproducts/SWE.2").mkdir(parents=True, exist_ok=True)
    (iwdg / "workproducts/SWE.2/api_calls.json").write_text(json.dumps({"calls": calls}))
    (iwdg / "workproducts/SWE.2/software_architecture.md").write_text("# SWE.2 (test stub)\n")
    block, hdr = profile(iwdg)["ll"]["register_block"], api_header("LL", iwdg)

    def impl(name, mutate=None):
        d = tmp_path / name
        (d / hdr).parent.mkdir(parents=True, exist_ok=True)
        (d / hdr).write_text(_ll_impl(rec, block, mutate))
        return d

    ok = register_proof.prove(iwdg, [impl("ok")], hdr)
    assert ok["status"] == "PROVED" and set(ok["operations"]) == {o["intent_id"] for o in rec["operations"]}, ok
    sneaky = {"LL_IWDG_SetReloadCounter":
              "if ({b}[{w}] != 0x00000123U) {{ {b}[{w}] = ({b}[{w}] & ~0x00000FFFU) | ((v << 0U) & 0x00000FFFU); }}"}
    d = impl("sneaky", sneaky)
    assert oracle_gen.run(iwdg, [d], [], hdr)["status"] == "PASS"  # the concrete images never start at 0x123
    bad = register_proof.prove(iwdg, [d], hdr)
    failed = {i for i, v in bad["operations"].items() if v["status"] == "FAILED"}
    assert bad["status"] == "FAILED" and failed == {"IWDG_RLR:reload"}, bad["operations"]
    ident = {t["tool"]: t for t in register_proof.identity()}
    assert ident["cbmc"]["status"] == "PRESENT" and len(ident["cbmc"]["sha256"]) == 64
    assert ident["kind2"]["applicability"].startswith("UNSUPPORTED")


def test_wp_proves_each_register_effect_and_leaves_each_mutant_open_on_its_own_operation(iwdg, monkeypatch,
                                                                                         tmp_path):
    """F011-T033/AT-029: SafeC's C11/ACSL obligations, re-derived by Forge-C and frozen with SWE.1, are proved by
    Frama-C WP on the real LL code for every operation. Each seeded mutant (inverted key, absent write, wrong-bit
    read, a read that writes, a write to another register) leaves its own operation, and only it, NOT_PROVED.
    Bit preservation is not claimed by WP; it stays with the CBMC proof."""
    from forge_factory.assurance import register_wp
    from forge_factory.assurance.formal import tool
    from forge_factory.layer import api_header, profile

    if tool("frama-c") is None:
        pytest.skip("Frama-C not installed on this host")
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    rep = SEM.visit(iwdg, "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    if not (iwdg / register_wp.OBLIGATIONS_FILE).is_file():
        pytest.skip("pinned engine predates derive_contracts")
    rec, issues = register_wp.verified(iwdg)
    assert issues == [], issues
    calls = {}
    for iid, case in rec["case_of_intent"].items():
        op = next(o for o in rec["operations"] if o["intent_id"] == iid)
        calls[case] = {"function": FN[iid.split(":", 1)[1]],
                       "args": [f"{op['logical_value']}U"] if op["action"] == "write_field" else []}
    (iwdg / "workproducts/SWE.2").mkdir(parents=True, exist_ok=True)
    (iwdg / "workproducts/SWE.2/api_calls.json").write_text(json.dumps({"calls": calls}))
    block, hdr = profile(iwdg)["ll"]["register_block"], api_header("LL", iwdg)

    def impl(name, mutate=None):
        d = tmp_path / name
        (d / hdr).parent.mkdir(parents=True, exist_ok=True)
        (d / hdr).write_text(_ll_impl(rec, block, mutate))
        return d

    ok = register_wp.prove(iwdg, [impl("ok")], hdr)
    assert ok["status"] == "PROVED" and set(ok["operations"]) == {o["intent_id"] for o in rec["operations"]}, ok
    rmw = [i for i, v in ok["operations"].items() if "PRESERVED_BITS" in v["left_to_cbmc"]]
    assert rmw and all("PRESERVED_BITS" not in v["obligations"] for v in ok["operations"].values())
    assert {t["tool"] for t in ok["tools"]} == {"frama-c", "why3", "alt-ergo", "cvc5"}
    mutants = {
        "inverted key": ({"LL_IWDG_Enable": "{b}[{w}] = 0x0000CCCDU;"}, "IWDG_KR:start"),
        "absent write": ({"LL_IWDG_ReloadCounter": "(void)0;"}, "IWDG_KR:refresh"),
        "wrong-bit read": ({"LL_IWDG_IsActive": "return ({b}[{w}] & 0x00000002U) >> 1U;"}, "IWDG_SR_1:onf"),
        "read that writes": ({"LL_IWDG_IsActiveFlag_RVU": "{b}[{w}] = 0U; return 0U;"}, "IWDG_SR_2:rvu"),
        "other register": ({"LL_IWDG_SetPrescaler": "{b}[{w}] = ({b}[{w}] & ~0x0000000FU) | ((v << 0U) & 0x0000000FU); "
                                                   "{b}[0] = 0U;"}, "IWDG_PR:prescaler"),
    }
    for what, (mutate, target) in mutants.items():
        bad = register_wp.prove(iwdg, [impl(what.replace(" ", "_"), mutate)], hdr)
        open_ops = {i for i, v in bad["operations"].items() if v["status"] != "PROVED"}
        assert bad["status"] == "NOT_PROVED" and open_ops == {target}, (what, bad["operations"])


def test_contract_mutants_come_from_the_contract_and_the_safec_oracle_kills_each(iwdg, monkeypatch, tmp_path):
    """F011-T034/AT-027: requirement-level faults (another documented key, a neighbouring field bit, an omitted
    register write, a write to a read-only register) are derived from the verified contract, never from the code.
    The SafeC register oracle kills every one of them on a correct LL; a unit test that does not observe register
    effects lets them survive, and the SWE.4 mutation verifier reports survivors as findings."""
    import shutil

    from forge_factory.assurance import mutation, oracle_gen
    from forge_factory.assurance import safec_oracle as SO
    from forge_factory.layer import api_header, profile

    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    rec, _ = SO.verified(iwdg)
    calls = {}
    for iid, case in rec["case_of_intent"].items():
        op = next(o for o in rec["operations"] if o["intent_id"] == iid)
        calls[case] = {"function": FN[iid.split(":", 1)[1]],
                       "args": [f"{op['logical_value']}U"] if op["action"] == "write_field" else []}
    (iwdg / "workproducts/SWE.2").mkdir(parents=True, exist_ok=True)
    (iwdg / "workproducts/SWE.2/api_calls.json").write_text(json.dumps({"calls": calls}))
    (iwdg / "workproducts/SWE.2/software_architecture.md").write_text("# SWE.2 (test stub)\n")
    pr = profile(iwdg)
    block, count, hdr = pr["ll"]["register_block"], pr["ll"]["register_count"], api_header("LL", iwdg)
    ops = mutation.register_ops(iwdg)
    names = {o[0] for o in ops}
    assert {"KEY_SWAP", "FIELD_BIT_SHIFT", "OMIT_WRITE"} <= names, names
    good = _ll_impl(rec, block)
    ms = mutation.mutants(good, "IWDG", ops)
    ms = [m for m in ms if m["op"] in names]
    assert len(ms) >= len(rec["operations"])
    from forge_factory.assurance import register_proof
    from forge_factory.assurance.formal import tool

    killed_by, survived = {"oracle": 0, "cbmc": 0}, []
    for n, m in enumerate(ms):
        d = tmp_path / f"m{n}"
        (d / hdr).parent.mkdir(parents=True, exist_ok=True)
        (d / hdr).write_text(m["text"])
        if oracle_gen.run(iwdg, [d], [], hdr)["status"] == "FAIL":
            killed_by["oracle"] += 1
        elif tool("cbmc") is not None and register_proof.prove(iwdg, [d], hdr)["status"] == "FAILED":
            killed_by["cbmc"] += 1  # a fault visible only from an initial value no concrete image uses
        else:
            survived.append((m["op"], m["original"]))
    print("CONTRACT_MUTANTS", len(ms), json.dumps(killed_by), sorted(names))
    assert survived == [], survived
    assert killed_by["oracle"] >= len(ms) - 2, killed_by  # measured: two clear-mask shifts need CBMC
    # the campaign carries the contract operators; a test that only calls the functions observes nothing
    sw = tmp_path / "sw"
    (sw / "ll").mkdir(parents=True)
    (sw / "ll" / Path(hdr).name).write_text(good)
    weak = tmp_path / "test_weak.c"
    body = "\n".join(f"    (void){FN[i.split(':', 1)[1]]}({'5U' if 'prescaler' in i else ('4095U' if 'reload' in i else '')});"
                     for i in rec["case_of_intent"])
    weak.write_text(f"#include <stdint.h>\nvolatile uint32_t {block}[{count}];\n#include \"{Path(hdr).name}\"\n"
                    f"int main(void)\n{{\n{body}\n    return 0;\n}}\n")
    c = mutation.run_campaign(sw, f"ll/{Path(hdr).name}", [weak], prefix="IWDG", ll_unit="none.c", extra_ops=ops)
    assert "forge-mut-rio/1" in c["record"]["operator_set"] and c["schema_issues"] == []
    contract_survivors = {m["op"] for m in c["mutants"] if m["outcome"] == "SURVIVED"} & names
    assert {"KEY_SWAP", "OMIT_WRITE"} <= contract_survivors, c["mutants"]
    assert mutation.validate_campaign(c["record"]) == []


def test_target_oracle_on_the_iwdg_model_states_what_it_cannot_set(iwdg, monkeypatch, tmp_path):
    """F011-T034 (SWE.5/SWE.6): the frozen oracle on the Renode IWDG model. The key register is write-only, the
    configuration registers are write-protected until unlocked and the status flags are driven by the model, so no
    case's initial image can be held: every case is NOT_SETTABLE, none is reported passed or failed, and the SWE.5
    verifier turns that into stated limitations only."""
    import shutil

    from forge_factory.assurance import safec_oracle as SO
    from forge_factory.assurance import target_oracle, verifiers
    from forge_factory.layer import api_header, profile
    from forge_factory.mcp.servers import sim

    if sim.renode_bin() is None or shutil.which("arm-none-eabi-gcc") is None:
        pytest.skip("Renode or the GNU Arm toolchain not installed")
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    rec, _ = SO.verified(iwdg)
    calls = {}
    for iid, case in rec["case_of_intent"].items():
        op = next(o for o in rec["operations"] if o["intent_id"] == iid)
        calls[case] = {"function": FN[iid.split(":", 1)[1]],
                       "args": [f"{op['logical_value']}U"] if op["action"] == "write_field" else []}
    (iwdg / "workproducts/SWE.2").mkdir(parents=True, exist_ok=True)
    (iwdg / "workproducts/SWE.2/api_calls.json").write_text(json.dumps({"calls": calls}))
    hdr = api_header("LL", iwdg)
    (iwdg / "software/ll").mkdir(parents=True, exist_ok=True)
    (iwdg / "software/ll" / Path(hdr).name).write_text(_ll_impl(rec, profile(iwdg)["ll"]["register_block"]))
    r = target_oracle.run(iwdg, [iwdg / "software/ll"], Path(hdr).name)
    assert r["status"] == "NOT_SUPPORTED" and r["counts"]["PASS"] == r["counts"]["FAIL"] == 0, r["counts"]
    assert r["counts"]["NOT_SETTABLE"] == len(r["cases"]) > 0
    f = verifiers._target_oracle_findings(iwdg)
    assert f and all(x.startswith("LIMITATION:") for x in f), f[:3]


def test_v2_swe2_fixes_the_names_the_frozen_requirements_name(iwdg, monkeypatch, tmp_path):
    """F011-T031/T032: under local-rtx-v2 each function a frozen requirement names is a key of the SWE.2 output
    schema, so the measured IsActive -> IsEnabled rename cannot be produced; other workspaces keep the feature 010
    schema unchanged."""
    from forge_factory.lrtx import swe2

    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    assert swe2.named_mode(iwdg)
    names = swe2.named_functions(iwdg)
    assert "LL_IWDG_IsActive" in names and all(n.startswith("LL_IWDG_") for n in names)
    schema = swe2.interfaces_packet(iwdg, "qwen3-coder:30b")["output_schema"]
    assert schema["properties"]["named_functions"]["required"] == names
    detail = {"returns": "uint32_t", "params": [], "operation": "query the enable flag", "fields": ["IWDG_SR.ONF"]}
    good = {"named_functions": {n: detail for n in names}, "other_functions": [], "allocation": [], "calls": []}
    assert not [e for e in S.validate(good, schema) if "named_functions" in e]
    renamed = json.loads(json.dumps(good).replace('"LL_IWDG_IsActive"', '"LL_IWDG_IsEnabled"'))
    assert S.validate(renamed, schema)  # the renamed key is refused by the schema itself
    flat = swe2.normalize_interfaces(iwdg, good)
    assert [f["name"] for f in flat["functions"]] == names and "named_functions" not in flat
    man = json.loads((iwdg / ".forge-run/manifest.json").read_text())
    man.pop("local_profile", None)
    (iwdg / ".forge-run/manifest.json").write_text(json.dumps(man))
    assert not swe2.named_mode(iwdg) and swe2.interfaces_schema(iwdg) is swe2.INTERFACES_SCHEMA
