"""Feature 008 US3 - FROZEN delivered code: protected by policy, verified by fingerprints, traced by the trace map
(not code tags), CODE defects escalated to the owner, delivery record and findings in the package."""
import json

import pytest
from brownfield_fixtures import HEADER, add_contract, example_copy, pass_swe1
from forge_factory import workorder as WO
from forge_factory.brownfield import gates as G
from forge_factory.brownfield import package as PK
from forge_factory.brownfield import trace as T
from forge_factory.brownfield.inject import inject
from forge_factory.brownfield.verify import verify
from forge_factory.common import sha256_bytes
from forge_factory.policy.authz import Authorizer, Binding


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    w, _ = WO.prepare(example_copy(tmp_path), "WO-F-1")
    add_contract(w)
    pass_swe1(monkeypatch)
    assert inject(w)["status"] == "INJECTED"
    return w


def test_frozen_delivered_code_cannot_be_written_by_any_role(ws):
    for node, role, phase in (("swe3_fix_author", "swe3-author", "SWE.3"), ("swe4_author", "swe4-author", "SWE.4")):
        a = Authorizer(Binding("WO", str(ws), {node: {"role": role, "phase": phase}}))
        d = a.decide(node, "write_file", {"path": "software/ll/stm32n6xx_ll_rcc.h", "content": "x\n"})
        assert not d.allow and d.code in ("DELIVERED_CODE_FROZEN", "WRITE_SCOPE_DENIED"), d
    a = Authorizer(Binding("WO", str(ws), {"swe3_author": {"role": "swe3-author", "phase": "SWE.3"}}))
    assert a.decide("swe3_author", "edit_file", {"path": "software/ll/stm32n6xx_ll_rcc.h"}).code == \
        "DELIVERED_CODE_FROZEN"
    assert a.decide("swe3_author", "write_file", {"path": "workproducts/SWE.3/detailed_design.md",
                                                  "content": "# d\n"}).allow


def test_verify_unchanged_then_mismatch(ws):
    assert verify(ws, "t1")["status"] == "UNCHANGED"
    h = ws / "software/ll/stm32n6xx_ll_rcc.h"
    h.chmod(0o644)
    h.write_text(HEADER + "/* edited */\n")
    r = verify(ws, "t2")
    assert r["status"] == "MISMATCH" and r["issues"] == ["DELIVERY_MISMATCH:software/ll/stm32n6xx_ll_rcc.h (FROZEN)"]
    assert json.loads((ws / ".forge-run/delivery/verification-t2.json").read_text())["status"] == "MISMATCH"


UNITS = [{"id": "SWU-LL-01", "functions": ["LL_RCC_HSI_Enable", "LL_RCC_HSI_Disable", "LL_RCC_HSI_IsReady"],
          "specs": [{"id": "USPEC-LL-01-01"}, {"id": "USPEC-LL-01-02"}]}]


def _map(ws, rows):
    (ws / T.MAP).parent.mkdir(parents=True, exist_ok=True)
    (ws / T.MAP).write_text(json.dumps({"schema": T.SCHEMA, "rows": rows}))


def test_trace_map_seed_and_check(ws):
    assert T.seed(ws)["rows"] == 16
    seed = json.loads((ws / T.SEED).read_text())["rows"]
    facts = json.loads((ws / T.FACTS).read_text())["functions"]
    assert {f["function"] for f in facts} == {r["function"] for r in seed}
    hsi = next(f for f in facts if f["function"] == "LL_RCC_HSI_Enable")
    assert hsi["register_effects"] == [{"register": "RCC_CR", "op": "set", "bits": [3], "via": ""}]
    assert T.check_code(ws, UNITS)["major_findings"][0].startswith("CODE:TRACE_MAP_MISSING")
    sha = sha256_bytes((ws / "software/ll/stm32n6xx_ll_rcc.h").read_bytes())
    rows = [{"function": r["function"], "file": r["file"], "sha256": r["sha256"], "unit": "SWU-LL-01",
             "uspecs": ["USPEC-LL-01-01"] if r["function"].endswith("Enable") else ["USPEC-LL-01-02"]}
            for r in seed if r["function"].startswith("LL_RCC_HSI")]
    rows += [{"function": r["function"], "out_of_scope": True, "reason": "test: only the HSI unit here"} for r in seed
             if not r["function"].startswith("LL_RCC_HSI")]
    _map(ws, rows)
    r = T.check_code(ws, UNITS)
    assert all(f.startswith("CODE:SCOPE_FUNCTION_MARKED_OUT_OF_SCOPE") for f in r["major_findings"]), r
    _map(ws, [dict(rows[0], sha256="0" * 64), dict(rows[1], unit="SWU-LL-09"), dict(rows[2], uspecs=[])])
    f = T.check_code(ws, UNITS)["major_findings"]
    assert any(x.startswith("CODE:TRACE_MAP_FINGERPRINT_MISMATCH:LL_RCC_HSI_Enable") for x in f)
    assert any(x.startswith("CODE:UNKNOWN_UNIT_REF:LL_RCC_HSI_Disable") for x in f)
    assert any(x.startswith("CODE:UNDOCUMENTED_FUNCTION:LL_RCC_HSI_IsReady") for x in f)
    assert any(x.startswith("CODE:SCOPE_FUNCTION_NOT_IN_TRACE_MAP:LL_RCC_ADC12_Enable") for x in f)
    assert sha == rows[0]["sha256"]


def test_swtrace_uses_the_trace_map_for_delivered_code(ws):
    from forge_factory.inspection.swtrace import check_code

    assert check_code(ws, UNITS)["major_findings"][0].startswith("CODE:TRACE_MAP_MISSING")


def test_frozen_code_defect_is_escalated_to_the_owner(ws):
    from forge_factory.inspection import defects

    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n")
    rec = defects.report(ws, detected_phase="SWE.3", reported_by="swe3-inspector", kind="CODE",
                         summary="HSI enable sets the wrong bit", requirement_ids=["SWR-001"], test_files=[],
                         evidence_refs=["software/ll/stm32n6xx_ll_rcc.h:75"],
                         requirement_quote="the RCC LL driver shall set RCC_CR.HSION")
    assert rec["status"] == "ESCALATED" and rec["target_phase"] is None and rec["target_kind"] == "DELIVERED_CODE"
    assert f"escalated_defect:{rec['id']}:CODE" in defects.gaps(ws)


class _Store:
    def __init__(self, ws):
        self.workspace = ws


def _state_log():
    rows = []
    return rows, (lambda ws, ph, payload: rows.append(payload)), (lambda ws, ph, st: 11)


def test_delivery_check_and_verify_nodes(ws, capsys):
    rows, state, fail = _state_log()
    assert G.run(_Store(ws), "SWE.3", "delivery_check", state, fail) == 0
    assert (ws / T.SEED).is_file() and rows[-1]["step"] == "delivery_check"
    assert G.run(_Store(ws), "SWE.3", "delivery", state, fail) == 0
    last = rows[-1]
    assert last["verdict"] == "PASS" and last["delivery"] == "UNCHANGED" and last["conformance_findings"] == 0
    rec = json.loads((ws / G.FINDINGS).read_text())
    assert rec["code_mode"] == "FROZEN" and rec["conformance"] == "CONFORMANT"
    h = ws / "software/ll/stm32n6xx_ll_rcc.h"
    h.chmod(0o644)
    h.write_text(HEADER + "/* edited */\n")
    assert G.run(_Store(ws), "SWE.3", "delivery", state, fail) == 11  # a fingerprint mismatch always fails


def test_package_findings_and_delivery_record(ws, tmp_path):
    assert PK.findings(ws) == []  # unchanged, conformant
    lines = PK.stage(ws, tmp_path / "stage")
    rec = json.loads((tmp_path / "stage/configuration/delivery.json").read_text())
    assert rec["code_mode"] == "FROZEN" and rec["licence"] == "Apache-2.0" and len(rec["files"]) == 2
    assert rec["injection"]["swe1_baseline_id"] == "BL-SWE.1-001"
    assert any("frozen before the delivered code" in x for x in lines)
    calls = json.loads((ws / "workproducts/SWE.2/api_calls.json").read_text())
    calls["calls"]["HSE_READY_QUERY"] = {"function": "NONE", "args": []}
    (ws / "workproducts/SWE.2/api_calls.json").write_text(json.dumps(calls))
    ids = [f["id"] for f in PK.findings(ws)]
    assert any(i.startswith("CONFORMANCE:CF-001:NO_CODE") for i in ids), ids


def test_package_findings_when_never_injected(tmp_path):
    w, _ = WO.prepare(example_copy(tmp_path, name="ni"), "WO-F-2")
    assert [f["id"] for f in PK.findings(w)] == ["DELIVERY:NOT_INJECTED"]


def test_brownfield_graph_has_no_code_generator_and_greenfield_is_unchanged():
    from forge_factory.workflow.builder import build

    g, nodes = build("WO-T", layer="LL", trace=True, brownfield="FROZEN", chunk_lines=150)
    for gen in ("swe3_regmap", "swe3_ll_author", "swe3_hal_author", "swe3_units"):
        assert gen not in nodes and f"  {gen} [" not in g
    assert '  swe1_inspect_gate -> delivery_inject [condition="outcome=succeeded"]' in g
    assert '  delivery_inject -> swe2_author [condition="outcome=succeeded"]' in g
    assert "swe1_inspect_gate -> swe2_author" not in g
    assert '--check delivery"' in g and '--check delivery_check"' in g
    g2, nodes2 = build("WO-T", layer="LL", trace=True, chunk_lines=150)
    assert "delivery" not in g2 and "swe3_regmap" in nodes2 or "  swe3_regmap [" in g2
    assert "DELIVERED CODE" not in g2
