"""Feature 008 US6 - ST STM32CubeN6 RCC pilot inputs (needs the fingerprinted ST downloads under
$FORGE_DATA_ROOT/inputs/st; skipped where they are absent): intake, scope resolution, conformance of ST's LL to the
r170 requirement contract, and the contract-call compile check against the vendor headers."""
import json
import os
import shutil
from pathlib import Path

import pytest
from brownfield_fixtures import FIX
from forge_factory import workorder as WO
from forge_factory.brownfield import conformance as C
from forge_factory.brownfield import delivery as D
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0008c-st-cube-rcc"
ST = Path(os.path.expandvars("$FORGE_DATA_ROOT/inputs/st/stm32n6xx-hal-driver-v1.4.0/provenance.json"))
pytestmark = pytest.mark.skipif(not ST.is_file() or not shutil.which("arm-none-eabi-gcc"),
                                reason="ST downloads or arm-none-eabi-gcc not available")


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    w, man = WO.prepare(EX, "WO-P-1")
    assert man["delivery_intake"]["status"] == "ACCEPTED" and man["delivery_intake"]["build_check"] == "PASS"
    for rel, data in D.stored("WO-P-1").items():  # as delivery_inject would (SWE.1 passed)
        (w / rel).parent.mkdir(parents=True, exist_ok=True)
        (w / rel).write_bytes(data)
    (w / ".forge-run/delivery").mkdir(parents=True, exist_ok=True)
    shutil.copy(D.store_dir("WO-P-1") / "scope.json", w / ".forge-run/delivery/scope.json")
    return w


def _contract(ws):
    for d, n in (("workproducts/SWE.1", "register_effects.json"), ("workproducts/SWE.2", "software_architecture.md")):
        (ws / d).mkdir(parents=True, exist_ok=True)
        shutil.copy(FIX / n, ws / d / n)
    m = {"HSI_ENABLE": ("LL_RCC_HSI_Enable", []), "HSI_DISABLE": ("LL_RCC_HSI_Disable", []),
         "HSE_ENABLE": ("LL_RCC_HSE_Enable", []), "HSE_DISABLE": ("LL_RCC_HSE_Disable", []),
         "HSI_READY_QUERY": ("LL_RCC_HSI_IsReady", []), "HSE_READY_QUERY": ("LL_RCC_HSE_IsReady", [])}
    for p in ("GPDMA1", "ADC12"):
        a = [f"LL_AHB1_GRP1_PERIPH_{p}"]
        m |= {f"{p}_CLOCK_ENABLE": ("LL_AHB1_GRP1_EnableClock", a), f"{p}_CLOCK_DISABLE": ("LL_AHB1_GRP1_DisableClock", a),
              f"{p}_CLOCK_IS_ENABLED": ("LL_AHB1_GRP1_IsEnabledClock", a),
              f"{p}_RESET_ASSERT": ("LL_AHB1_GRP1_ForceReset", a), f"{p}_RESET_RELEASE": ("LL_AHB1_GRP1_ReleaseReset", a)}
    (ws / "workproducts/SWE.2/api_calls.json").write_text(json.dumps(
        {"schema": "forge-c/api-calls/1", "calls": {k: {"function": f, "args": a} for k, (f, a) in m.items()}}))


def test_st_intake_resolves_the_scope_and_lists_the_rest(ws):
    scope = json.loads((ws / ".forge-run/delivery/scope.json").read_text())
    names = {f["name"]: f for f in scope["functions"]}
    assert len(names) == 11 and names["LL_RCC_HSI_Enable"]["line"] == 1819 and scope["excluded_count"] > 500
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    assert man["delivery"]["licence"] == "BSD-3-Clause"
    assert {d["role"] for d in man["delivered"]} == {"delivered_code", "delivered_dependency"}


def test_st_ll_conforms_to_the_independent_requirement_contract(ws):
    _contract(ws)
    r = C.check(ws, "SWE.3", write=False)
    assert r["status"] == "CONFORMANT", r["findings"]


def test_contract_calls_compile_against_the_vendor_headers(ws):
    from forge_factory.assurance import register_contract as RC

    _contract(ws)
    assert RC.check_compiles(ws, [ws / "software/ll"], "stm32n6xx_ll_rcc.h") == []
