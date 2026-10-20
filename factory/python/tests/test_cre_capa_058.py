"""CAPA-058 (b006 DEF-003): a delivered function shared by several units lists every owning unit in the trace map."""
import json
import subprocess
import sys

from forge_factory.common import REPO_ROOT


def test_capa058_shared_function_traces_both_units():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr062_trace_map_shared_function.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr


def test_capa058_a_uspec_of_a_unit_not_listed_still_fails(tmp_path):
    from forge_factory.brownfield import trace as T
    from forge_factory.common import sha256_bytes

    hdr = "static inline void LL_A(void) { }\n"
    (tmp_path / "software/ll").mkdir(parents=True)
    (tmp_path / "software/ll/a.h").write_text(hdr)
    (tmp_path / ".forge-run/delivery").mkdir(parents=True)
    (tmp_path / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [{"name": "LL_A"}]}))
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"delivered": [
        {"path": "software/ll/a.h", "role": "delivered_code", "sha256": sha256_bytes(hdr.encode())}], "delivery": {}}))
    (tmp_path / "workproducts/SWE.3").mkdir(parents=True)
    (tmp_path / T.MAP).write_text(json.dumps({"schema": T.SCHEMA, "rows": [
        {"function": "LL_A", "file": "software/ll/a.h", "sha256": sha256_bytes(hdr.encode()), "unit": ["SWU-LL-01"],
         "uspecs": ["USPEC-LL-01-01", "USPEC-LL-02-01"]}]}))
    units = [{"id": "SWU-LL-01", "functions": ["LL_A"], "specs": [{"id": "USPEC-LL-01-01"}]},
             {"id": "SWU-LL-02", "functions": ["LL_B"], "specs": [{"id": "USPEC-LL-02-01"}]}]
    assert "CODE:SPEC_OF_OTHER_UNIT:LL_A:USPEC-LL-02-01" in T.check_code(tmp_path, units)["major_findings"]
