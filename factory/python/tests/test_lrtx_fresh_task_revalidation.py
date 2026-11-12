"""Explicit fresh-source task revalidation never carries a previous phase verdict."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory import workorder as W
from forge_factory.common import sha256_file
from forge_factory.fabro import client as F


@pytest.mark.parametrize("flag", ["true", 1, None])
def test_revalidation_flag_is_strictly_typed_before_any_preparation(flag):
    with pytest.raises(ValueError, match="AUTHOR_TASK_REVALIDATION_FLAG_INVALID"):
        W.run(Path("missing-example"), "WO-NO-EFFECT", revalidate_author_tasks=flag)


def test_revalidation_without_source_cannot_prepare_or_launch():
    with pytest.raises(ValueError, match="AUTHOR_TASK_REVALIDATION_SOURCE_REQUIRED"):
        W.run(Path("missing-example"), "WO-NO-EFFECT", revalidate_author_tasks=True)


@pytest.mark.parametrize("enabled", [False, True])
def test_fresh_preparation_records_explicit_source_hash_before_build_with_no_phase_import(tmp_path, monkeypatch, enabled):
    state = tmp_path / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    parent = state / "workorders/WO-PARENT/workspace/.forge-run"
    parent.mkdir(parents=True)
    (parent / "manifest.json").write_text(json.dumps({"work_order": "WO-PARENT", "factory_revision": {"commit": "a" * 40}}))
    (parent / "fabro_run_id").write_text("OLD-TERMINAL")
    example = tmp_path / "example"
    example.mkdir()
    (example / "workorder.json").write_text("{}")
    child = state / "workorders/WO-CHILD/workspace"
    (child / ".forge-run").mkdir(parents=True)
    (child / "inputs").mkdir()
    (child / "inputs/index.md").write_text("")
    manifest = {"work_order": "WO-CHILD", "driver": "test driver", "layer": "LL", "target": {}, "scope": []}
    (child / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(F, "client_for_workspace", lambda _: SimpleNamespace(
        get_run=lambda _: {"lifecycle": {"status": {"kind": "SUCCEEDED"}}}))
    monkeypatch.setattr(W, "prepare", lambda *a, **kw: (child, manifest))

    class BeforeNative(Exception):
        pass

    def build(*args, **kwargs):
        raise BeforeNative

    monkeypatch.setattr(W, "build", build)
    with pytest.raises(BeforeNative):
        W.run(example, "WO-CHILD", model="fixture-model", provider="ollama", fresh_recovery_from="WO-PARENT",
              revalidate_author_tasks=enabled)
    record = json.loads((child / ".forge-run/manifest.json").read_text())["fresh_recovery_from"]
    assert record["work_order"] == "WO-PARENT" and record["source_manifest_sha256"] == sha256_file(parent / "manifest.json")
    assert record.get("revalidate_author_tasks", False) is enabled
    assert not (child / "inspection").exists() and not (child / "configuration/baselines").exists()
