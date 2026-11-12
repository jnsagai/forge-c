"""CAPA-124 (run WO-F014-SWE2-CRCHAL-20261103-L26): the SWE.2 dynamic view needs a HAL_TIMEOUT path only for a HAL
that waits. The CRC HAL has no wait (crc.yaml, RM0486 26.3.3); IWDG (time base) and RCC (ready-flag waits) keep the
rule, and so does every profile that leaves its HAL wait texts to the RCC default."""
import json
from pathlib import Path

import pytest
from forge_factory import layer
from forge_factory.inspection.views import check_views
from forge_factory.peripheral import DIR, load

FINDING = "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH"
FNS = {"crc": ["HAL_CRC_Init", "HAL_CRC_Calculate"], "iwdg": ["HAL_IWDG_Init", "HAL_IWDG_Refresh"],
       "rcc": ["HAL_RCC_HSI_Enable"], "gpio": ["HAL_GPIO_Init"]}


def _ws(tmp: Path, pid: str, layer_name: str = "HAL", timeout: bool = False) -> Path:
    prof = load(pid)
    hal, ll = Path(prof["hal"]["header"]).stem, Path(prof["ll"]["header"]).stem
    ws = tmp / f"{pid}-{layer_name}-{timeout}"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"peripheral": pid, "layer": layer_name}))
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    rows = "".join(f"| SWR-00{i} | {f} |\n" for i, f in enumerate(FNS[pid], 1))
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# Software architecture\n\n## Requirement allocation table\n\n| SWR | Function |\n|---|---|\n" + rows)
    (ws / "workproducts/SWE.2/architecture_static.puml").write_text(
        f"@startuml\ncomponent {hal}\ncomponent {ll}\n{hal} --> {ll}\n@enduml\n")
    calls = "".join(f"Caller -> HAL : {f}()\nHAL --> Caller : HAL_OK\n" for f in FNS[pid])
    (ws / "workproducts/SWE.2/architecture_dynamic.puml").write_text(
        f"@startuml\nparticipant Caller\nparticipant HAL\n{calls}HAL --> Caller : HAL_ERROR\n"
        + ("HAL --> Caller : HAL_TIMEOUT\n" if timeout else "") + "@enduml\n")
    return ws


def test_hal_waits_from_the_profile(monkeypatch):
    waits = {}
    for p in sorted(DIR.glob("*.yaml")):
        prof = load(p.stem)
        monkeypatch.setattr(layer, "profile", lambda ws=None, _p=prof: _p)
        waits[p.stem] = layer.hal_waits()
    assert waits["crc"] is False and waits["wwdg"] is False  # wwdg: no-wait HAL texts (RM0486 ch.60, CHANGE)
    assert waits["iwdg"] is True and waits["rcc"] is True
    assert all(v is True for k, v in waits.items() if k not in ("crc", "wwdg")), waits  # no own HAL texts: RCC default waits


def test_hal_waits_rules(monkeypatch):
    crc = load("crc")
    monkeypatch.setattr(layer, "profile", lambda ws=None: crc)
    assert layer.hal_waits() is False
    timed = {**crc, "hal": {**crc["hal"], "time_base": "HAL_GetTick"}}
    monkeypatch.setattr(layer, "profile", lambda ws=None: timed)
    assert layer.hal_waits() is True  # a time base means a bounded wait
    for key in layer.HAL_WAIT_TEXTS:
        partial = {**crc, "prompt": {k: v for k, v in crc["prompt"].items() if k != key}}
        monkeypatch.setattr(layer, "profile", lambda ws=None, _p=partial: _p)
        assert layer.hal_waits() is True, key  # the RCC default text (with HAL_TIMEOUT) applies
        named = {**crc, "prompt": {**crc["prompt"], key: crc["prompt"][key] + " or HAL_TIMEOUT"}}
        monkeypatch.setattr(layer, "profile", lambda ws=None, _p=named: _p)
        assert layer.hal_waits() is True, key


@pytest.mark.parametrize("pid,required", [("crc", False), ("iwdg", True), ("rcc", True), ("gpio", True)])
def test_timeout_path_required_only_for_a_waiting_hal(tmp_path, pid, required):
    r = check_views(_ws(tmp_path, pid))
    assert (FINDING in r["major_findings"]) is required, r
    assert r["stats"]["timeout_path_required"] is required
    assert FINDING not in check_views(_ws(tmp_path, pid, timeout=True))["major_findings"]


def test_ll_and_combined_layers_unchanged(tmp_path):
    ll = check_views(_ws(tmp_path, "iwdg", "LL"))
    assert FINDING not in ll["major_findings"] and ll["stats"]["timeout_path_required"] is False
    assert FINDING in check_views(_ws(tmp_path, "rcc", "LL+HAL"))["major_findings"]
    assert FINDING not in check_views(_ws(tmp_path, "crc", "LL+HAL"))["major_findings"]
