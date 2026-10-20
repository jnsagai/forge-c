"""Feature 008 US4 - FIX_ALLOWED: delivered code changes only while a CODE defect is in fix, only inside the scope's
functions, never as a new file; the change report links each change to its defect (FR-014, SC-003)."""
import json

import pytest
from brownfield_fixtures import HEADER, add_contract, example_copy, pass_swe1
from forge_factory import workorder as WO
from forge_factory.brownfield import trace as T
from forge_factory.brownfield.inject import inject
from forge_factory.brownfield.verify import verify
from forge_factory.common import sha256_bytes
from forge_factory.policy.authz import Authorizer, Binding

H = "software/ll/stm32n6xx_ll_rcc.h"
C = "software/src/stm32n6xx_ll_rcc.c"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    def fix_allowed(spec):
        spec["delivery"]["code_mode"] = "FIX_ALLOWED"
        spec["delivery"]["scope"]["functions"] = [f for f in spec["delivery"]["scope"]["functions"]
                                                  if f != "LL_RCC_ADC12_ReleaseReset"]
    w, man = WO.prepare(example_copy(tmp_path, mutate=fix_allowed), "WO-X-1")
    assert man["code_mode"] == "FIX_ALLOWED"
    add_contract(w)
    pass_swe1(monkeypatch)
    assert inject(w)["status"] == "INJECTED"
    return w


def _defect(ws, status, evidence=None, n=1):
    d = ws / ".forge-run/defects"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"DEF-{n:03d}.json").write_text(json.dumps({"id": f"DEF-{n:03d}", "kind": "CODE", "status": status,
                                                     "target_phase": "SWE.3", "evidence_refs": evidence or [],
                                                     "summary": "HSI enable must set HSION"}))


def _auth(ws):
    return Authorizer(Binding("WO", str(ws), {"swe3_fix_author": {"role": "swe3-author", "phase": "SWE.3"},
                                              "swe4_author": {"role": "swe4-author", "phase": "SWE.4"}}))


def test_write_window_opens_only_while_a_code_defect_is_in_fix(ws):
    a = _auth(ws)
    w = {"path": H, "content": "x\n"}
    assert a.decide("swe3_fix_author", "write_file", w).code == "DELIVERED_CODE_NO_DEFECT"
    _defect(ws, "IN_FIX")
    assert a.decide("swe3_fix_author", "write_file", w).allow
    assert a.decide("swe4_author", "write_file", w).code in ("DELIVERED_CODE_FIX_ROLE_ONLY", "WRITE_SCOPE_DENIED")
    assert a.decide("swe3_fix_author", "write_file", {"path": "software/ll/extra.c", "content": "x\n"}).code == \
        "BROWNFIELD_NEW_CODE_FILE"
    _defect(ws, "VERIFIED")
    assert a.decide("swe3_fix_author", "write_file", w).code == "DELIVERED_CODE_NO_DEFECT"


def test_a_defect_naming_another_file_does_not_open_this_one(ws):
    _defect(ws, "IN_FIX", evidence=[f"{C}:3"])
    a = _auth(ws)
    assert a.decide("swe3_fix_author", "write_file", {"path": H, "content": "x\n"}).code == "DELIVERED_CODE_NO_DEFECT"
    assert a.decide("swe3_fix_author", "write_file", {"path": C, "content": "x\n"}).allow


def _edit(ws, old, new):
    p = ws / H
    p.write_text(p.read_text().replace(old, new, 1))


def test_change_report_links_the_fix_to_its_defect(ws):
    _defect(ws, "FIXED")
    _edit(ws, "    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;",
          "    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= (LL_RCC_CR_HSION_MSK);")
    r = verify(ws, "package")
    assert r["status"] == "CHANGED_BY_FIX" and r["issues"] == []
    rep = json.loads((ws / ".forge-run/delivery/change_report.json").read_text())
    ch = rep["changes"][0]
    assert ch["path"] == H and ch["defects"] == ["DEF-001"] and ch["original_sha256"] == sha256_bytes(HEADER.encode())
    assert "+    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= (LL_RCC_CR_HSION_MSK);" in ch["diff"]
    rows = {x["path"]: x["status"] for x in r["files"]}
    assert rows[C] == "UNCHANGED"  # untouched delivered files stay byte-identical


def test_unlinked_change_is_a_mismatch(ws):
    _edit(ws, "|= LL_RCC_CR_HSION_MSK;", "|= (LL_RCC_CR_HSION_MSK);")
    r = verify(ws, "package")
    assert r["status"] == "MISMATCH" and r["issues"] == [f"DELIVERY_MISMATCH:{H}"]


def test_change_outside_the_scope_functions_is_refused(ws):
    _defect(ws, "FIXED")
    p = ws / H
    t = p.read_text()
    i = t.find("LL_RCC_ADC12_ReleaseReset(void)")
    j = t.find("&= ~", i)
    p.write_text(t[:j] + "&= ~ " + t[j + 4:])
    r = verify(ws, "package")
    assert r["status"] == "MISMATCH"
    assert any(x.startswith(f"DELIVERY_CHANGE_OUTSIDE_SCOPE:{H}:LL_RCC_ADC12_ReleaseReset") for x in r["issues"])


def test_trace_map_keeps_the_delivered_fingerprint_after_a_fix(ws):
    T.seed(ws)
    seed = json.loads((ws / T.SEED).read_text())["rows"]
    _defect(ws, "FIXED")
    _edit(ws, "|= LL_RCC_CR_HSION_MSK;", "|= (LL_RCC_CR_HSION_MSK);")
    units = [{"id": "SWU-LL-01", "functions": [r["function"] for r in seed], "specs": [{"id": "USPEC-LL-01-01"}]}]
    (ws / T.MAP).write_text(json.dumps({"schema": T.SCHEMA, "rows": [dict(r, unit="SWU-LL-01",
                                                                           uspecs=["USPEC-LL-01-01"]) for r in seed]}))
    assert not [f for f in T.check_code(ws, units)["major_findings"] if "FINGERPRINT" in f]
