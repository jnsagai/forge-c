"""SPEC-001 backlog evidence: a sealed package meets T-003/T-011/T-012/T-017 only when every acceptance artifact is in
it; a missing ELF, a failed unit run or a missing matrix fails the task; the archive is never changed."""
import json
import zipfile

from forge_factory import backlog001 as B

E = "evidence/"
FULL = {
    E + "verification/static/register_map_conformance.json": json.dumps({"verdict": "PASS", "major_findings": []}),
    E + "workproducts/SWE.1/software_requirements.md": "x", E + "workproducts/SWE.2/software_architecture.md": "x",
    E + "configuration/target_baseline.json": "{}", E + "software/hal/a.c": "x", E + "software/hal/a.h": "x",
    E + "software/ll/l.h": "x", E + "software/build/driver.elf": "x", E + "software/build/driver.map": "x",
    E + "workproducts/SWE.3/detailed_design.md": "x", E + "software/tests/unit/test_rcc.c": "x",
    E + "verification/static/analysis_summary.json": "{}", E + "verification/static/misra_coverage_matrix.md": "x",
    E + "evidence-raw/a.log": "x", E + "verification/tool-results.jsonl":
        json.dumps({"op": "run_unit", "result": {"status": "PASS"}}) + "\n",
    **{f"{E}inspection/SWE.{i}/INS-SWE.{i}-001.json": json.dumps({"verdict": "PASS"}) for i in (3, 4)},
    **{f"{E}workproducts/SWE.{i}/r.md": "x" for i in range(1, 7)},
    **{f"{E}traceability/matrices/matrix_{i}.csv": "a,b\n" for i in range(1, 7)},
    "manifest.json": json.dumps({"gaps": ["missing_or_empty_file:safety/x.md"], "gap_count": 1}), "SHA256SUMS.txt": "x",
}


def _zip(tmp_path, drop=(), over=None):
    p = tmp_path / "pkg-review.zip"
    with zipfile.ZipFile(p, "w") as z:
        for k, v in {**FULL, **(over or {})}.items():
            if k not in drop:
                z.writestr(k, v)
    return p


def test_complete_package_meets_the_four_engineering_tasks(tmp_path):
    p = _zip(tmp_path)
    for t in ("T-003", "T-011", "T-012", "T-017"):
        assert B.main([str(p), "--task", t]) == 0, t


def test_missing_or_failed_artifacts_fail_the_task(tmp_path):
    assert B.main([str(_zip(tmp_path, drop=(E + "software/build/driver.elf",))), "--task", "T-011"]) == 1
    bad = {E + "verification/tool-results.jsonl": json.dumps({"op": "run_unit", "result": {"status": "FAIL"}}) + "\n"}
    assert B.main([str(_zip(tmp_path, over=bad)), "--task", "T-012"]) == 1
    assert B.main([str(_zip(tmp_path, drop=(E + "traceability/matrices/matrix_6.csv",))), "--task", "T-017"]) == 1
    reg = {E + "verification/static/register_map_conformance.json": json.dumps({"verdict": "PASS",
                                                                                  "major_findings": ["X"]})}
    assert B.main([str(_zip(tmp_path, over=reg)), "--task", "T-003"]) == 1
