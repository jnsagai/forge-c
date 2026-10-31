"""C parameter notation is independently compiled; context cannot waive a review."""
import json
import re
import shutil
import subprocess

import pytest

from forge_factory import workorder
from forge_factory.lrtx import c_language_context as C
from forge_factory.lrtx import profile, review, structured, swe1
from forge_factory.workflow.builder import build

PROFILE = "local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp"
FINDING = (
    "The scope section of workproducts/SWE.1/software_requirements.md is inconsistent with SWR-005 through SWR-013, "
    "SWR-016, and SWR-019: the scope describes the LL functions as '(void) functions', while those requirements "
    "require query or is-enabled functions to return 1U or 0U."
)


def workspace(root, peripheral="rcc"):
    (root / ".forge-run").mkdir(parents=True)
    (root / "configuration").mkdir()
    (root / "inputs").mkdir()
    manifest = {"layer": "LL", "peripheral": peripheral, "target": {},
                "purpose": "ASPICE_ONLY", "evaluation_holdout": True,
                "scope": ["Synthetic C API fixture: (void) functions."],
                "local_profile": {"id": PROFILE}}
    (root / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    name = "RCC LL driver" if peripheral == "rcc" else "IWDG LL driver"
    (root / "configuration/system_names.json").write_text(json.dumps([name]))
    (root / "inputs/index.md").write_text("")
    (root / "inputs/register.md").write_text("# Synthetic input for context-assembly tests only\n")
    req = root / "workproducts/SWE.1/software_requirements.md"
    req.parent.mkdir(parents=True)
    req.write_text("# Synthetic C requirements\n" + "\n".join(
        f"- **SWR-{n:03d}** When the query is called, the {name} shall return the flag value.\n"
        "  - Source: synthetic fixture\n  - Verification: Pass when the returned value equals the flag.\n"
        for n in range(1, 31)))
    return root


def test_void_parameters_with_a_value_return_are_valid_c_and_execute(tmp_path):
    compiler = shutil.which("clang")
    assert compiler, "pinned real C compiler required"
    source = tmp_path / "c_parameter_fact.c"
    source.write_text("#include <stdint.h>\n"
                      "static uint32_t flag;\n"
                      "static inline uint32_t query(void) { return flag; }\n"
                      "static inline void update(void) { flag = UINT32_C(1); }\n"
                      "int main(void) { if (query() != 0U) return 1; update(); return query() == 1U ? 0 : 2; }\n")
    binary = tmp_path / "compiled"
    built = subprocess.run([compiler, "-std=c11", "-pedantic-errors", "-Wstrict-prototypes", "-Wall", "-Wextra",
                            "-Werror", str(source), "-o", str(binary)], capture_output=True, timeout=30)
    assert built.returncode == 0, built.stderr.decode()
    assert subprocess.run([str(binary)], capture_output=True, timeout=5).returncode == 0


def test_an_actual_void_return_type_cannot_return_a_value(tmp_path):
    compiler = shutil.which("clang")
    assert compiler
    source = tmp_path / "genuine_type_conflict.c"
    source.write_text("static inline void query(void) { return 1U; }\nint main(void) { query(); return 0; }\n")
    built = subprocess.run([compiler, "-std=c11", "-pedantic-errors", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(tmp_path / "must-not-build")], capture_output=True, timeout=30)
    assert built.returncode != 0 and not (tmp_path / "must-not-build").exists()


@pytest.mark.parametrize("peripheral", ["rcc", "iwdg"])
def test_complete_author_and_reviewer_context_includes_the_fact_without_changing_evidence(tmp_path, monkeypatch, peripheral):
    ws = workspace(tmp_path / peripheral, peripheral)
    group = {"id": "SYNTH_CTRL", "register": "SYNTH_CTRL", "section": "1", "file": "inputs/register.md",
             "pages": [1], "fields": {"FLAG": {"lsb": 0, "msb": 0, "access": ["rw"], "description": "Synthetic flag"}}}
    token = structured.RECOVERY_WORKSPACE.set(ws)
    try:
        with monkeypatch.context() as old:
            old.setattr(C, "selected", lambda _p: False)
            before = swe1.group_packet(ws, group, "synthetic-model")
        after = swe1.group_packet(ws, group, "synthetic-model")
        cross = swe1.crosscut_packet(ws, [], "synthetic-model")
        source = structured.source(ws, "workproducts/SWE.1/software_requirements.md")
        checked = review.item_packet(ws, "SWE.1", {"id": "SWE1-02", "criterion": "Synthetic verifiability criterion"},
                                     {"baseline_id": "BL-FIXTURE", "baseline_hash": "a" * 64}, [source], "synthetic-model")
    finally:
        structured.RECOVERY_WORKSPACE.reset(token)
    for packet in (after, cross, checked):
        assert C.NOTE in "\n".join(m["content"] for m in packet["_messages"])
        assert packet["accounting"]["fits"]
    assert after["sources"] == before["sources"] and after["criteria"] == before["criteria"]
    assert after["output_schema"] == before["output_schema"] and after["input_hash"] != before["input_hash"]
    assert (after["accounting"]["complete_serialized_request"]["serialized_bytes"]
            > before["accounting"]["complete_serialized_request"]["serialized_bytes"])


@pytest.mark.parametrize("peripheral", ["rcc", "iwdg"])
@pytest.mark.parametrize("layer", ["LL", "HAL"])
def test_native_swe1_roles_receive_the_same_optional_note(peripheral, layer):
    controls = {"phases": [], "inspect_phases": [], "reinspect": False, "model": "synthetic-model",
                "timeout_s": 3600, "visit_time_s": 1200, "c_parameter_list_note": True}
    graph, _ = build("WO-C-NOTATION", layer=layer, peripheral=peripheral, structured=controls)
    prompts = dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', graph))
    assert C.NOTE in prompts["swe1_author"] and C.NOTE in prompts["swe1_inspector"]
    assert C.NOTE not in prompts["swe2_author"]


@pytest.mark.parametrize("layer", ["LL", "HAL"])
def test_selected_profile_forwards_the_note_even_when_roles_use_native_mcp(layer):
    p = profile.load(PROFILE)
    controls = workorder.local_profile_structured(p, {"layer": layer}, p["models"]["default"])
    assert controls["c_parameter_list_note"] is True


def test_context_does_not_refute_or_accept_the_original_finding(tmp_path):
    ws = workspace(tmp_path / "current")
    verdict = {"verdict": "FAIL", "findings": [FINDING],
               "evidence_checked": ["workproducts/SWE.1/software_requirements.md"]}
    assert C.NOTE in review._notes(ws, "SWE.1", "SWE1-02")
    assert review.fact_conflicts(ws, "SWE.1", "SWE1-02", [FINDING]) == []
    assert review.validate_verdict(verdict, set(verdict["evidence_checked"]), ws, "SWE.1", "SWE1-02") == []
    assert verdict["verdict"] == "FAIL" and verdict["findings"] == [FINDING]


def test_unselected_profiles_keep_their_context_and_invalid_policy_is_refused(tmp_path):
    ws = workspace(tmp_path / "legacy")
    p = ws / ".forge-run/manifest.json"
    m = json.loads(p.read_text());m.pop("local_profile");p.write_text(json.dumps(m))
    assert C.for_workspace(ws) == ""
    graph, _ = build("WO-C-NOTATION-LEGACY", layer="LL")
    assert C.NOTE not in graph
    with pytest.raises(ValueError, match="POLICY_INVALID"):
        C.selected({"structured": {"c_parameter_list_note": "true"}})

