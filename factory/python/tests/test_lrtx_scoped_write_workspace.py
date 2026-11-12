"""CAPA-075 / RPR-074: a scoped write authorizes against the workspace it writes, never against the absolute
workspace recorded in a copied .forge-run/binding.json (lrtx/modelcmp, lrtx/seeded and lrtx/campaign copy whole
workspaces, binding included)."""
from __future__ import annotations

import json
import shutil

import pytest
from forge_factory import development_execution as D
from forge_factory.lrtx import visit as V


def _workspace(root):
    ws = root / "source" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(
        {"purpose": "QM", "development_execution": D.binding(D.DEMO, "QM")}))
    (ws / ".forge-run/binding.json").write_text(json.dumps(
        {"binding_id": "capa075", "workspace": str(ws),
         "nodes": {"swe1_author": {"role": "swe1-author", "phase": "SWE.1"}}}))
    return ws


def test_copy_write_keeps_development_state_in_the_copy(tmp_path):
    src = _workspace(tmp_path)
    copy = tmp_path / "copy" / "workspace"
    shutil.copytree(src, copy, symlinks=True)
    V.write_scoped(copy, {"workproducts/SWE.1/software_requirements.md": "# copy\n"}, "swe1_author")
    assert (copy / "workproducts/SWE.1/software_requirements.md").read_text() == "# copy\n"
    assert (copy / ".forge-run/lrtx/SWE.1/development-execution.json").is_file()
    assert not (src / ".forge-run/lrtx").exists()
    assert not (src / "workproducts").exists()
    # the copied binding itself is not rewritten by a write (copy tooling owns its data)
    assert json.loads((copy / ".forge-run/binding.json").read_text())["workspace"] == str(src)


def test_own_workspace_write_is_unchanged(tmp_path):
    ws = _workspace(tmp_path)
    V.write_scoped(ws, {"workproducts/SWE.1/software_requirements.md": "# own\n"}, "swe1_author")
    assert (ws / ".forge-run/lrtx/SWE.1/development-execution.json").is_file()


def test_scope_and_role_checks_still_apply_in_a_copy(tmp_path):
    src = _workspace(tmp_path)
    copy = tmp_path / "copy" / "workspace"
    shutil.copytree(src, copy, symlinks=True)
    with pytest.raises(PermissionError, match="LRTX_WRITE_REFUSED"):
        V.write_scoped(copy, {"software/ll/forbidden.h": "x"}, "swe1_author")
    with pytest.raises(PermissionError, match="LRTX_WRITE_REFUSED"):
        V.write_scoped(copy, {"../outside.md": "x"}, "swe1_author")
    assert not (src / ".forge-run/lrtx").exists()
