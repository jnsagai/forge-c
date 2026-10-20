"""Feature 009 slice D (PG-T009): register-contract op `write` (a field holds a value after the call, e.g. the
IWDG key register) - validated against the RM field width and checked by the independent oracle on an IWDG LL."""
import json

from forge_factory import workorder as WO
from forge_factory.assurance import oracle_gen
from forge_factory.assurance import register_contract as RC
from test_peripheral_iwdg import EX, SWE2

REQ = ("- **SWR-001** When the start function is called, the IWDG LL driver shall write 0xCCCC to IWDG_KR.KEY.\n"
       "- **SWR-002** When the set prescaler function is called, the IWDG LL driver shall write the prescaler to "
       "IWDG_PR.PR.\n")
LL = ("static inline void LL_IWDG_Enable(void)\n{\n    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x0000CCCCU;\n}\n"
      "static inline void LL_IWDG_SetPrescaler(uint32_t prescaler)\n{\n"
      "    ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] = (prescaler & LL_IWDG_PR_PR_MSK);\n}\n")


def _ws(tmp_path, monkeypatch, ll=LL):
    from forge_factory.inspection import regmap

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    ws, _ = WO.prepare(EX, "WO-IWDG-C")
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQ)
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(SWE2)
    regmap.generate(ws)
    h = ws / "software/ll/stm32n6xx_ll_iwdg.h"
    h.write_text(h.read_text().replace(regmap.functions_marker(ws), regmap.functions_marker(ws) + "\n" + ll))
    (ws / RC.EFFECTS).write_text(json.dumps({"schema": "forge-c/register-effects/1", "effects": [
        {"case": "START", "swr": "SWR-001", "register": "IWDG_KR", "field": "KEY", "op": "write", "value": "0xCCCC"},
        {"case": "PRESCALER_4", "swr": "SWR-002", "register": "IWDG_PR", "field": "PR", "op": "write", "value": 4}]}))
    (ws / RC.CALLS).write_text(json.dumps({"schema": "forge-c/api-calls/1", "calls": {
        "START": {"function": "LL_IWDG_Enable", "args": []},
        "PRESCALER_4": {"function": "LL_IWDG_SetPrescaler", "args": ["4U"]}}}))
    return ws


def test_write_effects_are_valid_contract_entries(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    assert not [x for x in RC.check_effects(ws, "LL") if "WRITE_VALUE" in x or "NOT_IN_RM" in x]
    cs, _ = RC.cases(ws)
    assert [(c["case"], c["value"], c["lsb"]) for c in cs] == [("START", 0xCCCC, 0), ("PRESCALER_4", 4, 0)]
    bad = json.loads((ws / RC.EFFECTS).read_text())
    bad["effects"][1]["value"] = 16  # PR is 4 bits wide
    (ws / RC.EFFECTS).write_text(json.dumps(bad))
    assert any(x.startswith("CONTRACT_WRITE_VALUE:") for x in RC.check_effects(ws, "LL"))


def test_oracle_checks_the_written_value(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    r = oracle_gen.run(ws, [ws / "software/ll"], [ws / "software/src/stm32n6xx_ll_iwdg.c"], "stm32n6xx_ll_iwdg.h")
    assert r["status"] == "PASS", r
    bad = _ws(tmp_path / "b", monkeypatch, LL.replace("0x0000CCCCU", "0x0000AAAAU"))
    r = oracle_gen.run(bad, [bad / "software/ll"], [bad / "software/src/stm32n6xx_ll_iwdg.c"], "stm32n6xx_ll_iwdg.h")
    assert r["status"] == "FAIL", r
