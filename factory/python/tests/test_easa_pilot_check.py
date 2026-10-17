"""EASA-T079 / AT-094: the pilot check passes only with all six matrices fully covered and names the failing one."""
import zipfile

from forge_factory.assurance import pilot


def _zip(tmp_path, drop=None, uncovered=None):
    z = tmp_path / "WO-X" / "p.zip"
    z.parent.mkdir(parents=True)
    with zipfile.ZipFile(z, "w") as f:
        for m in pilot.MATRICES:
            if m == drop:
                continue
            f.writestr(pilot.PREFIX + m + ".csv", "a,b,status\nx,y,VERIFIED\n")
            f.writestr(pilot.PREFIX + m + ".md", f"# {m}\n\nUncovered items: {uncovered if m == pilot.MATRICES[4] and uncovered else 'none'}\n")
    return z


def test_at094_complete_package_passes(tmp_path):
    r = pilot.check(_zip(tmp_path))
    assert r["status"] == "PASS" and r["archive_unchanged"] and len(r["matrices"]) == 6


def test_at094_missing_or_uncovered_relation_is_named(tmp_path):
    r = pilot.check(_zip(tmp_path / "a", drop=pilot.MATRICES[2]))
    assert r["status"] == "FAIL" and r["failing_relations"] == ["MATRIX_MISSING:matrix_3_code_to_unitspec"]
    r = pilot.check(_zip(tmp_path / "b", uncovered="IF-03"))
    assert r["failing_relations"] == ["MATRIX_UNCOVERED:matrix_5_integrationtest_to_architecture:IF-03"]
