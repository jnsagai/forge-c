"""M7 (T042–T047, T049): budget governor, bounded payloads, resumable idempotent stages, v0.4 package,
finalizer on every terminal path, separated defect routing, threat-model checks."""
import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT, canonical_json
from forge_factory.inspection.engine import PHASES, Store, load_checklist
from forge_factory.mcp import sdk
from forge_factory.policy import governor as G
from forge_factory.release import finalize as F


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "archives"))
    return tmp_path


class FakeFabro:
    def __init__(self, stages, status="running"):
        self.stages, self.status, self.cancelled = stages, status, False

    def usage(self, run_id):
        return {"stages": [{"stage": {"id": n}, "model": {"model_id": "qwen3:8b", "provider": "ollama"},
                            "usage": {"tokens": {"input": i, "output": o}}, "state": "succeeded"}
                           for n, i, o in self.stages]}

    def cancel(self, run_id):
        self.cancelled = True
        return 202

    def get_run(self, run_id):
        return {"lifecycle": {"status": {"kind": self.status}}}


# ---------------- T042 ------------------------------------------------------------------------------------
def test_t042_turn_budget_blocks_and_resets_per_visit(env):
    for _ in range(20):
        ok, n, lim = G.count_tool_call("b", "R", "swe3_author", "swe3-author")
        assert ok
    ok, n, lim = G.count_tool_call("b", "R", "swe3_author", "swe3-author")
    assert not ok and n == 21 and lim == 20
    G.reset_node("b", "R", "swe3_author")
    assert G.count_tool_call("b", "R", "swe3_author", "swe3-author")[0]


def test_t042_hook_returns_turn_budget_exhausted(env, tmp_path):
    from forge_factory.policy.authz import Binding
    from forge_factory.policy.fabro_hook import handle
    b = Binding("b2", str(tmp_path), {"insp": {"role": "swe1-inspector", "phase": "SWE.1"}})
    ctx = {"event": "pre_tool_use", "node_id": "insp", "run_id": "R", "tool_name": "read_file",
           "tool_input": {"file_path": "x"}}
    decisions = [handle(ctx, b) for _ in range(21)]
    assert all(d.allow for d in decisions[:20]) and decisions[20].code == "TURN_BUDGET_EXHAUSTED"
    assert handle({"event": "stage_start", "node_id": "insp", "run_id": "R"}, b).allow
    assert handle(ctx, b).allow


def test_t042_token_exhaustion_cancels_and_blocks_never_false_pass(env, tmp_path):
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    fake = FakeFabro([("swe3_author", 150_000, 2_000), ("swe1_author", 1000, 100)])
    out = G.check_run("RUN-X", {"swe3_author": {"role": "swe3-author"}, "swe1_author": {"role": "swe1-author"}}, ws, fake)
    assert out["status"] == "TOKEN_BUDGET_EXHAUSTED" and fake.cancelled and out["basis"] == "reported"
    assert [e["node"] for e in out["exceeded"]] == ["swe3_author"]
    assert "TOKEN_BUDGET_EXHAUSTED" in (ws / ".forge-run/gates/gate-log.jsonl").read_text()
    ok = G.check_run("RUN-Y", {"swe1_author": {"role": "swe1-author"}}, ws, FakeFabro([("swe1_author", 10, 1)]))
    assert ok["status"] == "WITHIN_BUDGET"


# ---------------- T043 ------------------------------------------------------------------------------------
def test_t043_5mb_tool_log_small_payload_full_log_hashed(env, tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "software/src").mkdir(parents=True)
    (ws / "software/tests/unit").mkdir(parents=True)
    (ws / "software/src/drv.c").write_text("int drv(void){return 0;}\n")
    (ws / "software/tests/unit/test_big.c").write_text(
        '#include <stdio.h>\nint main(void){for(int i=0;i<100000;i++)printf("line %06d %s\\n",i,'
        '"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");return 1;}\n')
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_ROLE", "swe4-author")
    monkeypatch.setenv("FORGE_WORKSPACE", str(ws))
    from forge_factory.mcp.servers import tests as T
    op = next(o for o in T.OPERATIONS if o.name == "run_unit")
    out = sdk.invoke("forge-tests-mcp", op, {"coverage": False})
    assert out["status"] == "FAIL" and len(canonical_json(out)) <= 2048
    raw = ws / "evidence/raw" / (out["artifact_refs"][0].split(":")[-1] + ".log")
    assert raw.stat().st_size > 5_000_000 and b"line 099999" in raw.read_bytes()
    from forge_factory.contracts.agent_output import parse
    assert parse('{"status":"PASS","artifacts":[],"issues":[],"next_action":"next"}').human_status().startswith("PASS")


# ---------------- T044 ------------------------------------------------------------------------------------
def test_t044_interrupted_stage_resume_is_idempotent_and_never_rewrites_evidence(env, tmp_path):
    ws = tmp_path / "ws"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("- **SWR-001** The RCC driver shall reset.\n")
    s = Store(ws)
    b1 = s.freeze("SWE.1", "swe1-author")
    first = (ws / f"configuration/baselines/SWE.1/{b1['baseline_id']}.json").read_bytes()
    b2 = s.freeze("SWE.1", "swe1-author")  # "resumed" stage re-runs the same freeze
    assert b2["baseline_id"] == b1["baseline_id"] and len(s.baselines("SWE.1")) == 1
    assert (ws / f"configuration/baselines/SWE.1/{b1['baseline_id']}.json").read_bytes() == first
    out = env / "archives/WO-T044"
    F.finalize(ws, "WO-T044")
    h = F.verify_archive(next(out.glob("*.zip")))
    again = F.finalize(ws, "WO-T044")  # replayed finalizer must not rewrite a released archive
    assert "write-once" in again["note"] and F.verify_archive(next(out.glob("*.zip"))) == h
    r = subprocess.run([os.environ.get("FORGE_FABRO_BIN", "fabro"), "resume", "--help"], capture_output=True, text=True,
                       env={**os.environ, "HOME": os.environ.get("FORGE_FABRO_HOME", str(Path.home()))})
    assert "Resume an interrupted workflow run" in r.stdout  # verified Fabro capability (ADR-0002)


# ---------------- T045 ------------------------------------------------------------------------------------
def complete_workspace(ws: Path) -> None:
    """Synthetic, test-only workspace satisfying every policy item via the real engines (NOT product evidence)."""
    from test_swe2_architecture import ARCH_MIN
    files = {
        "workproducts/SWE.1/software_requirements.md": "- **SWR-001** The RCC driver shall enable the HSI oscillator.\n",
        "workproducts/SWE.2/software_architecture.md": ARCH_MIN,
        "workproducts/SWE.3/detailed_design.md": "# Design\nsynthetic\n",
        "workproducts/SWE.4/unit_verification_report.md": "# UV\nsynthetic\n",
        "workproducts/SWE.5/integration_verification_report.md": "# IV\nsynthetic\n",
        "workproducts/SWE.6/software_verification_report.md": "# SV\nsynthetic\n",
        "safety/software_safety_requirements.md": "synthetic\n", "safety/software_safety_analysis.md": "synthetic\n",
        "safety/tool_assurance_assessment.md": "synthetic\n",
        "traceability/requirements_to_tests.csv": "requirement_id,test_id,test_file\nSWR-001,UT-001,software/tests/unit/t.c\n",
        "software/src/drv.c": "int drv(void){return 0;}\n", "software/include/drv.h": "int drv(void);\n",
        "software/tests/unit/t.c": "int main(void){return 0;}\n", "verification/static/misra_coverage_matrix.md": "x\n",
        "configuration/system_names.json": '["RCC driver"]',
    }
    from test_guideline_check import HAL_C, HAL_H, LL_H
    files.update({"software/hal/stm32n6xx_hal_rcc.h": HAL_H, "software/hal/stm32n6xx_hal_rcc.c": HAL_C,
                  "software/ll/stm32n6xx_ll_rcc.h": LL_H})
    for rel, txt in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
    (ws / "build/target-cm55-gcc").mkdir(parents=True)
    (ws / "build/target-cm55-gcc/driver.elf").write_bytes(b"\x7fELF-synthetic")
    (ws / "build/target-cm55-gcc/driver.map").write_text("synthetic map\n")
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"budgets": {"flash_bytes": 4096, "static_ram_bytes": 64,
                                                                         "stack_bytes": 128}, "target": {"part": "x"}}))
    s = Store(ws)
    for p in PHASES:
        s.freeze(p, f"swe{p[-1]}-author")
        v = {c["id"]: {"verdict": "PASS", "evidence_refs": ["x"]} for c in load_checklist(p)["checks"]}
        assert s.record_inspection(p, f"swe{p[-1]}-inspector", s.latest_baseline(p)["baseline_id"], v)["verdict"] == "PASS"
    ok = {"status": "PASS", "summary": "target", "artifact_refs": [], "issues": [], "provenance": {}, "metrics": {}}
    rows = [("forge-analysis-mcp", "cppcheck", ok), ("forge-analysis-mcp", "clang_analyze", ok),
            ("forge-tests-mcp", "run_unit", ok), ("forge-tests-mcp", "run_integration", ok),
            ("forge-build-mcp", "measure_elf", {**ok, "summary": "text=10 (target-cm55-gcc)",
                                                "metrics": {"flash_bytes": 100, "ram_bytes": 8}}),
            ("forge-build-mcp", "stack_usage", {**ok, "summary": "max frame (target-cm55-gcc)",
                                                "metrics": {"max_frame_bytes": 16}}),
            ("forge-sim-mcp", "run_hwsim", ok)]
    (ws / "evidence").mkdir(exist_ok=True)
    (ws / "evidence/tool-results.jsonl").write_text("".join(json.dumps({"server": a, "op": b, "result": r}) + "\n"
                                                            for a, b, r in rows))


def test_t045_v04_policy_superset_and_operational_inventory_hashed(env, tmp_path):
    v3 = json.loads((REPO_ROOT / "factory/release-manager/policies/release-package-policy.json").read_text())
    v4 = json.loads(F.POLICY_V04.read_text())
    assert set(v3["required_files"]) <= set(v4["required_files"]) and set(v3["required_sections"]) <= set(v4["required_sections"])
    assert v4["required_quality_checks"] == v3["required_quality_checks"] and v4["require_no_open_findings"]
    import hashlib
    assert v4["extends"]["sha256"] == hashlib.sha256(
        (REPO_ROOT / "factory/release-manager/policies/release-package-policy.json").read_bytes()).hexdigest()
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)
    out = F.finalize(ws, "WO-T045")
    with zipfile.ZipFile(out["archive"]) as z:
        names = set(z.namelist())
        man = json.loads(z.read("manifest.json"))
    for rel in [f for f in v4["required_files"] if f.startswith("operations/")]:
        assert "evidence/" + rel in names, rel
    hashed = {f["path"] for f in man["files"]}
    assert all("evidence/" + r in hashed for r in v4["required_files"] if ("evidence/" + r) in names)
    assert man["scope"] == "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"


def test_t045_ready_requires_every_check_and_tamper_detected(env, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)
    out = F.finalize(ws, "WO-READY")
    assert out["package_status"] == "READY_FOR_OFFLINE_REVIEW", out["gaps"]
    a = Path(out["archive"])
    assert F.verify_archive(a)["integrity"] == "PASS"
    t = tmp_path / "tampered.zip"   # AT-25: corrupt a member after generation
    with zipfile.ZipFile(a) as zin, zipfile.ZipFile(t, "w") as zout:
        for n in zin.namelist():
            data = zin.read(n)
            zout.writestr(n, data + b"tamper" if n.endswith("final-gates.json") else data)
    assert F.verify_archive(t)["integrity"] == "FAIL"


# ---------------- T046 ------------------------------------------------------------------------------------
def test_t046_failing_swe3_static_check_blocked_archive_no_human(env, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)
    rows = [json.loads(x) for x in (ws / "evidence/tool-results.jsonl").read_text().splitlines()]
    rows.append({"server": "forge-analysis-mcp", "op": "cppcheck", "result": {"status": "FAIL", "summary": "MISRA-17.7",
                                                                              "artifact_refs": [], "issues": ["x"],
                                                                              "provenance": {}, "metrics": {}}})
    (ws / "evidence/tool-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = F.finalize(ws, "WO-T046")
    assert out["package_status"] == "BLOCKED" and "failed_or_missing_quality_check:static_analysis" in out["gaps"]


def test_t046_external_finalizer_packages_crashed_run(env, monkeypatch):
    from forge_factory.supervisor import service as S
    ws = env / "state/workorders/WO-CRASH/workspace"
    (ws / ".forge-run").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    (ws / ".forge-run/fabro_run_id").write_text("RUN-CRASH")
    import forge_factory.fabro.client as C
    monkeypatch.setattr(C, "FabroClient", lambda **kw: FakeFabro([], status="failed"))
    sup = S.Supervisor(S.load_policy(), None, home=env / "sup", dispatch_enabled=False)
    sup.external_finalizer()
    pkg = json.loads((ws / ".forge-run/package.json").read_text())
    assert pkg["package_status"] == "BLOCKED"


# ---------------- T047 ------------------------------------------------------------------------------------
def test_t047_product_defect_loops_swe_infra_defect_routes_repair(env, tmp_path):
    from forge_factory.supervisor.probes import Sample
    from forge_factory.supervisor.router import Router, RouterState
    from forge_factory.supervisor.service import load_policy
    from forge_factory.supervisor.store import IncidentStore
    from forge_factory.workflow.builder import build
    ws = tmp_path / "ws"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("- **SWR-001** clocks quickly.\n")  # driver defect
    s = Store(ws)
    bl = s.freeze("SWE.1", "swe1-author")
    s.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], {})
    assert s.gate("SWE.1")["decision"] == "REWORK"
    st = IncidentStore()
    assert st.all() == []  # a product defect never opens an infrastructure incident
    r = Router(load_policy(), st, RouterState())
    r.observe([Sample("mcp:forge-docs-mcp", "mcp_handshake", "DOWN", fault_type="MCP_HANDSHAKE_FAILURE")])
    assert [i["fault_type"] for i in st.all()] == ["MCP_HANDSHAKE_FAILURE"]
    dot, _ = build("wo")
    assert "fabric-repair" not in dot and "repair" not in {n.split()[0] for n in dot.splitlines() if "[" in n}
    assert dot.count("max_visits=4") == 12  # bounded SWE loops (6 authors + 6 inspectors)


# ---------------- T049 ------------------------------------------------------------------------------------
def test_t049_forged_ai_pass_cannot_pass_gate(env, tmp_path):
    ws = tmp_path / "ws"
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text("# A\n")
    r = subprocess.run([os.sys.executable, "-m", "forge_factory.inspection.gate", "--workspace", str(ws), "--phase", "SWE.2",
                        "--step", "inspect"], input=b'{"status":"PASS","artifacts":["inspection/SWE.2/INS-SWE.2-001.json"],'
                       b'"issues":[],"next_action":"next"}', capture_output=True)
    assert r.returncode != 0  # an agent's PASS without a recorded, current inspection is never accepted
