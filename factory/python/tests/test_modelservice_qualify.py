"""Feature 017 T044: the qualification report (FR-014 to FR-016, FR-030, SC-005)."""
import json

import pytest
from forge_factory.modelservice import qualify as Q


def _export(root, runs):
    for rid, (created, visits) in runs.items():
        d = root / "runs" / f"WO-X__{rid}"
        d.mkdir(parents=True)
        d.joinpath("run.json").write_text(json.dumps({"run": {"run_id": rid, "created_ms": created, "completed_ms": created + 3_600_000},
                                                       "visits": {f"{n}@{i}": {"node": n, **s} for i, (n, s) in enumerate(visits)}}))
    return root


def _stats(p, o, ms, cache=0, r=0, retries=0):
    return {"prompt_tokens": p, "output_tokens": o, "model_ms": ms, "cache_reused_tokens": cache, "reasoning_tokens": r,
            "retries": retries}


T0 = 1_762_600_000_000  # 2025-11-08 in ms; only relative times matter


def _params(**over):
    base = {"reference_precision": "fp8", "reference_context": 65536, "reference_sequences": 2, "gpu_vram_mib": 49140}
    prod = {"reference_precision": "bf16", "reference_context": 262144, "reference_sequences": 11, "gpu_vram_mib": 144384}
    mk = lambda d, site: {"site": site, "parameters": {k: {"value": v, "description": k} for k, v in d.items()},  # noqa: E731
                          "not_proven_here": ["BF16 precision"] if site == "omniverse2" else []}
    return mk({**base, **over}, "omniverse2"), mk(prod, "production")


def _set(cand_outcome="PASS", cand_runs=("c1",), capa=None):
    return {"baseline_setup": {"label": "ornith-owned", "identity": {"name": "ornith"}},
            "candidate_setup": {"label": "qwen3.6-fp8-external", "identity": {"name": "qwen3.6-35b-a3b-fp8"}},
            "phases": [{"phase": "SWE.1", "lineage": "CRC-HAL", "baseline": {"runs": ["b1"], "gate_outcome": "PASS", "evidence": "ev/b1"},
                        "candidate": {"runs": list(cand_runs), "gate_outcome": cand_outcome if cand_runs else None},
                        **({"capa": capa} if capa else {})}]}


def test_side_by_side_rows_per_node_and_swaps(tmp_path):
    b = _export(tmp_path / "b", {"b1": (T0, [("swe1-author", _stats(20000, 30000, 900000, 5000, 29000)),
                                             ("swe1_inspector", _stats(90000, 2000, 300000, 80000))])})
    c = _export(tmp_path / "c", {"c1": (T0, [("swe1-author", _stats(18000, 3000, 120000, 6000)),
                                             ("swe1_inspector", _stats(85000, 1800, 200000, 76000))])})
    out = tmp_path / "outcomes.jsonl"
    ts = lambda ms: __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime(ms / 1000))  # noqa: E731
    out.write_text("\n".join(json.dumps(e) for e in [
        {"kind": "swap", "outcome": "OK", "ts": ts(T0 + 60_000), "drain_ms": 1000, "unload_ms": 2000, "load_ms": 9000},
        {"kind": "swap", "outcome": "OK", "ts": ts(T0 + 9_000_000), "drain_ms": 1, "unload_ms": 1, "load_ms": 1},
        {"kind": "swap", "outcome": "LOAD_FAILED", "ts": ts(T0 + 120_000)}]) + "\n")
    mirror, prod = _params()
    r = Q.build(_set(), b, c, mirror, prod, out)
    assert r["verdict"] == "QUALIFIED_FOR_OWNER_REVIEW"
    author = next(x for x in r["rows"] if x["node"] == "swe1-author")
    assert author["baseline"]["output_tokens"] == 30000 and author["candidate"]["output_tokens"] == 3000
    assert author["baseline"]["reasoning_tokens"] == 29000 and author["candidate"]["model_time_s"] == 120.0
    assert author["candidate"]["swaps"] == 1 and author["candidate"]["swap_wait_s"] == 12.0  # only the swap inside the run
    assert author["baseline"]["cache_reuse_ratio"] == 0.25
    props = {d["property"]: d for d in r["deviations"]}
    assert props["reference_precision"]["production_value"] == "bf16" and props["reference_sequences"]["mirror_value"] == 2
    assert any(d["property"] == "not_proven_here" for d in r["deviations"])
    assert "QUALIFIED_FOR_OWNER_REVIEW" in Q.render_md(r)


def test_missing_candidate_is_not_run_and_incomplete(tmp_path):
    b = _export(tmp_path / "b", {"b1": (T0, [("swe1-author", _stats(1, 1, 1))])})
    mirror, prod = _params()
    r = Q.build(_set(cand_runs=()), b, tmp_path / "none", mirror, prod)
    assert r["verdict"] == "INCOMPLETE" and r["rows"][0]["candidate"]["status"] == "NOT_RUN"


@pytest.mark.parametrize("capa,status,verdict", [(None, "OPEN", "NOT_QUALIFIED"), ("CAPA-201", "OPEN", "NOT_QUALIFIED")])
def test_regression_is_a_blocking_finding_with_a_capa(tmp_path, capa, status, verdict):
    b = _export(tmp_path / "b", {"b1": (T0, [("swe1-author", _stats(1, 1, 1))])})
    c = _export(tmp_path / "c", {"c1": (T0, [("swe1-author", _stats(1, 1, 1))])})
    mirror, prod = _params()
    r = Q.build(_set(cand_outcome="FAIL", capa=capa), b, c, mirror, prod)
    f = r["blocking_findings"][0]
    assert r["verdict"] == verdict and f["status"] == status and f["capa_id"] == (capa or "CAPA-PENDING")
    assert f["evidence"] == ["ev/b1"]


def test_report_is_schema_checked(tmp_path):
    with pytest.raises(ValueError, match="QUALIFICATION_REPORT_INVALID"):
        Q.validate({"report_id": "x"})


def test_set_takes_only_runs_whose_gate_passed(tmp_path):
    _export(tmp_path / "exp", {"r1": (T0, [("a", _stats(1, 1, 1))]), "r2": (T0 + 10, [("a", _stats(1, 1, 1))]),
                                     "r3": (T0 + 20, [("a", _stats(1, 1, 1))])})
    wo = {"r1": "WO-F014-SWE1-CRCHAL-L1", "r2": "WO-F014-SWE1-CRCHAL-L2", "r3": "WO-F014-SWE2-CRCHAL-L3"}
    for f in (tmp_path / "exp/runs").glob("*/run.json"):
        d = json.loads(f.read_text())
        d["run"].update(wo=wo[d["run"]["run_id"]], status="succeeded")
        f.write_text(json.dumps(d))
    gates = {"WO-F014-SWE1-CRCHAL-L1": "PASS", "WO-F014-SWE1-CRCHAL-L2": "FAIL", "WO-F014-SWE2-CRCHAL-L3": None}
    for w, decision in gates.items():
        g = tmp_path / "wos" / w / "workspace/.forge-run/gates"
        g.mkdir(parents=True)
        lines = [{"step": "author", "result": "FROZEN"}]
        if decision:
            lines.append({"step": "inspect", "gate": {"decision": decision}})
        g.joinpath("gate-log.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    spec = [{"phase": "SWE.1", "lineage": "CRC", "patterns": ["SWE1-CRCHAL-"]}, {"phase": "SWE.2", "lineage": "CRC", "patterns": ["SWE2-CRCHAL-"]}]
    doc = Q.build_set(tmp_path / "exp", tmp_path / "wos", spec, {"label": "b", "identity": {}}, {"label": "c", "identity": {}})
    swe1, swe2 = doc["phases"]
    assert swe1["baseline"]["runs"] == ["r1"] and swe1["baseline"]["order"] == "WO-F014-SWE1-CRCHAL-L1"  # L2 failed its gate
    assert swe2["baseline"]["runs"] == [] and swe2["baseline"]["gate_outcome"] is None  # no gate decision: never assumed



def _gate_log(ws, entries):
    import json as _j
    d = ws / ".forge-run/gates"
    d.mkdir(parents=True)
    (d / "gate-log.jsonl").write_text("".join(_j.dumps(e) + "\n" for e in entries))


def test_a_phase_that_ran_out_of_rework_rounds_is_blocked_not_not_run(tmp_path):
    """Qualification window 4 (2026-11-12): the last inspection said REWORK and the route stopped the phase."""
    from forge_factory.modelservice import qualify as Q
    _gate_log(tmp_path / "a", [{"step": "inspect", "gate": {"decision": "REWORK"}},
                               {"step": "route", "gate": {"decision": "BLOCKED", "reason": "rework budget exhausted (3 failed cycles)"}}])
    _gate_log(tmp_path / "b", [{"step": "inspect", "gate": {"decision": "REWORK"}}, {"step": "inspect", "gate": {"decision": "PASS"}}])
    _gate_log(tmp_path / "c", [{"step": "author", "result": "REJECTED"}])
    assert Q.gate_outcome(tmp_path / "a") == "BLOCKED"
    assert Q.gate_outcome(tmp_path / "b") == "PASS"
    assert Q.gate_outcome(tmp_path / "c") == "BLOCKED"
    assert Q.gate_outcome(tmp_path / "none") is None
    _gate_log(tmp_path / "d", [{"step": "route", "gate": {"decision": "BLOCKED"}}, {"step": "inspect", "gate": {"decision": "PASS"}}])
    assert Q.gate_outcome(tmp_path / "d") == "PASS"  # an upstream loop that later passed


def test_candidates_from_several_windows_pass_only_when_every_sample_passed(tmp_path):
    import json as _j

    from forge_factory.modelservice import qualify as Q
    lane, kept = tmp_path / "lane", tmp_path / "lane/kept-w3"
    for root, wo, ok, at in ((kept, "WO-F017Q-SWE1-CRCHAL-a", True, "1"), (lane / "state/workorders", "WO-F017Q-SWE1-CRCHAL-b", False, "2"),
                             (kept, "WO-F017Q-SWE2-CRCHAL-a", True, "1")):
        ws = root / wo / "workspace"
        _gate_log(ws, [{"step": "inspect", "gate": {"decision": "PASS" if ok else "REWORK"}}]
                  + ([] if ok else [{"step": "route", "gate": {"decision": "BLOCKED"}}]))
        (ws / ".forge-run/fabro_run_id").write_text("RUN-" + wo[-1])
    (kept / "qualification-ledger.json").write_text(_j.dumps({"orders": {
        "WO-F017Q-SWE1-CRCHAL-a": {"phase": "SWE.1", "at": "1"}, "WO-F017Q-SWE2-CRCHAL-a": {"phase": "SWE.2", "at": "1"}}}))
    (lane / "qualification-ledger.json").write_text(_j.dumps({"orders": {"WO-F017Q-SWE1-CRCHAL-b": {"phase": "SWE.1", "at": "2"}}}))
    qset = {"phases": [{"phase": "SWE.1"}, {"phase": "SWE.2"}, {"phase": "SWE.3"}]}
    out = Q.fill_candidates(qset, [lane / "qualification-ledger.json", kept / "qualification-ledger.json"])
    c1, c2, c3 = (p["candidate"] for p in out["phases"])
    assert c1["gate_outcome"] == "BLOCKED" and c1["pass_ratio"] == "1/2" and c1["runs"] == ["RUN-a", "RUN-b"]
    assert c2["gate_outcome"] == "PASS" and c2["pass_ratio"] == "1/1"
    assert c3 == {"runs": [], "gate_outcome": None}
