"""Reconcile exact JUnit identities; never relabel the failed original invocation."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / "reconciliation-inputs.json").read_bytes())
for name, sha in manifest["inputs"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name


def cases(name):
    raw = (ROOT / name).read_bytes()
    assert len(raw) <= 16 * 1024**2
    result = {}
    for row in ET.fromstring(raw).iter("testcase"):
        key = row.attrib["classname"] + "::" + row.attrib["name"]
        assert key not in result, key
        status = next((tag.upper() for tag in ("error", "failure", "skipped") if row.find(tag) is not None), "PASS")
        result[key] = {"status": status, "source": name}
    return result


initial = json.loads((ROOT / manifest["base_invocation"]).read_bytes())
revision = manifest["tested_revision"]
assert initial["git_head"] == initial["end_head"] == revision
assert initial["start_dirty"] == initial["end_dirty"] == ""
assert initial["results"][0]["exit_code"] == 1  # preserve actual failing batch
result = cases(manifest["base"])
original = dict(result)
for overlay in manifest["overlays"]:
    invocation = json.loads((ROOT / overlay["invocation"]).read_bytes())
    assert invocation["git_head"] == invocation["end_head"] == revision and invocation["exit_code"] == 0
    assert invocation.get("end_dirty", invocation.get("end_tracked_diff")) == ""
    rows = cases(overlay["xml"])
    assert rows.keys() <= original.keys(), "overlay cannot invent additional tests"
    assert all(row["status"] == "PASS" for row in rows.values()), "retry is not passing"
    result.update(rows)
assert result.keys() == original.keys()
assert all(row["status"] in ("PASS", "SKIPPED") for row in result.values())
counts = {status: sum(r["status"] == status for r in result.values()) for status in ("PASS", "SKIPPED", "ERROR", "FAILURE")}
output = {"scope": "DETERMINISTIC_TEST_CASE_RECONCILIATION_NOT_SINGLE_GREEN_INVOCATION_OR_RUNTIME_QUALIFICATION",
          "tested_revision": revision, "original_core_exit_code": 1,
          "original_errors_preserved": sum(r["status"] == "ERROR" for r in original.values()),
          "unique_cases": len(result), "results": counts, "cases": result}
(ROOT / "reconciled-cases.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
print(json.dumps({k: v for k, v in output.items() if k != "cases"}, sort_keys=True))
