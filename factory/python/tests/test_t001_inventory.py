"""T001: inventory records actual installed versions, licences and a CycloneDX SBOM; no proprietary deps."""
import json

from forge_factory import inventory


def test_inventory_probes_real_host(tmp_path):
    assert inventory.main(["--out-dir", str(tmp_path)]) == 0
    inv = json.loads((tmp_path / "tool-inventory.json").read_text())
    names = {t["name"]: t for t in inv["tools"]}
    assert names["python3"]["status"] == "INSTALLED" and names["python3"]["version"].startswith("Python 3")
    assert names["git"]["status"] == "INSTALLED"
    for t in inv["tools"]:
        assert t["status"] in {"INSTALLED", "MISSING", "UNKNOWN_VERSION", "PROBE_FAILED"}
        assert t["licence"] and "proprietary" not in t["licence"].lower()
    assert inv["policy"]["allow_paid_api"] is False
    assert not [i for i in inv["licence_issues"] if i.startswith("NON_OSS")]
    deps = {d["name"].lower(): d for d in inv["python_dependencies"]}
    assert deps["mcp"]["status"] == "INSTALLED" and deps["mcp"]["version"] == "2.3.0"
    sbom = json.loads((tmp_path / "sbom.cdx.json").read_text())
    assert sbom["bomFormat"] == "CycloneDX" and len(sbom["components"]) > 20


def test_missing_tool_is_recorded_not_assumed():
    rec = inventory.probe_tool("nonexistent", ["definitely-not-a-forge-tool"], ["--version"])
    assert rec["status"] == "MISSING" and rec["version"] is None


def test_proprietary_licence_flagged():
    issues = inventory.licence_issues([{"name": "x", "licence": "Proprietary", "status": "INSTALLED"}])
    assert issues == ["NON_OSS_LICENCE:x:Proprietary"]
