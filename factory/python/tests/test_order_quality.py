"""Owner rule 2026-11-03: every order states its expected quality (target and minimum per metric); the line works
toward the target and progresses with at least the minimum. Without a quality block the owner defaults apply."""
from __future__ import annotations

import copy

import pytest
from forge_factory import quality as Q

BLOCK = {"structural_coverage": {"line": {"target": 100, "minimum": 90}, "branch": {"target": 100, "minimum": 90}},
         "requirements_coverage": {"uspec_tested": {"target": 100, "minimum": 95},
                                   "swr_verified_swe6": {"target": 100, "minimum": 100}},
         "misra": {"open_violations_max": 2, "undeviated_rules_max": 0, "deviation_owner_approval": True}}


def test_a_valid_block_is_taken_from_the_order():
    q, src = Q.resolve({"quality": BLOCK}, "ASPICE_ONLY")
    assert src == "order" and q == BLOCK and q is not BLOCK


@pytest.mark.parametrize("purpose,mcdc", [("ASPICE_ONLY", False), ("QM", False), ("DEVELOPMENT", True)])
def test_without_a_block_the_strict_owner_defaults_apply(purpose, mcdc):
    q, src = Q.resolve({}, purpose)
    assert src == "defaults" and ("mcdc" in q["structural_coverage"]) is mcdc
    pairs = list(q["structural_coverage"].values()) + list(q["requirements_coverage"].values())
    assert all(p == {"target": 100, "minimum": 100} for p in pairs)
    assert q["misra"] == {"open_violations_max": 0, "undeviated_rules_max": 0, "deviation_owner_approval": True}


def _bad(path, value):
    b = copy.deepcopy(BLOCK)
    cur = b
    for k in path[:-1]:
        cur = cur[k]
    if value is None:
        cur.pop(path[-1])
    else:
        cur[path[-1]] = value
    return b


@pytest.mark.parametrize("block,purpose,msg", [
    (_bad(("structural_coverage", "line"), {"target": 90, "minimum": 95}), "ASPICE_ONLY", "minimum <= target"),
    (_bad(("structural_coverage", "branch"), {"target": 101, "minimum": 90}), "ASPICE_ONLY", "<= 100"),
    (_bad(("structural_coverage", "branch"), None), "ASPICE_ONLY", "branch: required"),
    (BLOCK, "DEVELOPMENT", "mcdc: required for the safety purpose DEVELOPMENT"),
    (_bad(("misra", "open_violations_max"), -1), "ASPICE_ONLY", "non-negative integer"),
    (_bad(("requirements_coverage", "extra"), {"target": 1, "minimum": 1}), "ASPICE_ONLY", "unknown metric extra"),
    ("100%", "ASPICE_ONLY", "must be an object")])
def test_invalid_blocks_are_refused(block, purpose, msg):
    with pytest.raises(Q.QualityError, match="QUALITY_BLOCK_INVALID") as e:
        Q.resolve({"quality": block}, purpose)
    assert msg in str(e.value)


def test_mcdc_is_optional_for_aspice_when_the_order_asks_for_it():
    b = copy.deepcopy(BLOCK)
    b["structural_coverage"]["mcdc"] = {"target": 100, "minimum": 50}
    assert Q.validate(b, "ASPICE_ONLY") == []


def test_judge():
    p = {"target": 100, "minimum": 90}
    assert [Q.judge(v, p) for v in (100, 95, 89.9, None)] == ["MET", "BELOW_TARGET", "BELOW_MINIMUM", "NOT_APPLICABLE"]


def test_prepare_records_the_quality_and_refuses_an_invalid_block(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from forge_factory import workorder as WO
    from forge_factory.common import REPO_ROOT

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ex = REPO_ROOT / "examples/0002a-arm_55_rcc_ll"
    spec_path = ex / "workorder.json"
    spec = json.loads(spec_path.read_text())
    override = {}
    real = Path.read_text

    def read_text(self, *a, **k):  # the example spec with an order-stated quality block (repository untouched)
        if self == spec_path and "spec" in override:
            return json.dumps(override["spec"])
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", read_text)
    _ws, m = WO.prepare(ex, "WO-Q-DEF", purpose="ASPICE_ONLY")
    assert m["quality_source"] == "defaults" and m["quality"]["structural_coverage"]["line"]["minimum"] == 100
    override["spec"] = {**spec, "quality": BLOCK}
    _ws, m = WO.prepare(ex, "WO-Q-ORD", purpose="ASPICE_ONLY")
    assert m["quality_source"] == "order" and m["quality"] == BLOCK
    override["spec"] = {**spec, "quality": _bad(("misra", "deviation_owner_approval"), 1)}
    with pytest.raises(Q.QualityError, match="QUALITY_BLOCK_INVALID"):
        WO.prepare(ex, "WO-Q-BAD", purpose="ASPICE_ONLY")


def test_package_shows_quality_achieved_vs_target(tmp_path):
    import json

    from forge_factory.layer import UNIT_VERIFICATION

    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"purpose": "ASPICE_ONLY", "unit_verification":
                                                             UNIT_VERIFICATION, "quality": BLOCK,
                                                             "quality_source": "order"}))
    (ws / "evidence").mkdir()
    (ws / "evidence/tool-results.jsonl").write_text(json.dumps({
        "server": "forge-tests-mcp", "op": "llvm_coverage", "ts_utc": "2026-11-03T01:00:00Z",
        "result": {"status": "PASS", "metrics": {"line_pct": 95.0, "branch_pct": 100.0, "mcdc_pct": None}}}) + "\n")
    stage = tmp_path / "stage"
    rep = Q.stage_into(ws, stage)
    assert not rep["target_met"] and rep["below_minimum"] == [] and rep["source"] == "order"
    kl = (stage / "safety/known_limitations.md").read_text()
    assert "## Quality achieved vs target" in kl and "| statement/line coverage | 100% | 90% | 95.0% | BELOW_TARGET |" in kl
    assert (stage / "quality/quality-achieved.json").is_file()
