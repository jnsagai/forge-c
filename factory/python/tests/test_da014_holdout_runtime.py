"""Acceptance-workflow holdout reaches the real workspace before context retrieval."""

# ruff: noqa: F811
import json

import pytest
from brownfield_fixtures import example_copy
from forge_factory import workorder as W
from forge_factory.afo import runtime
from forge_factory.knowledge.context import applicability
from test_brownfield_resume import pair  # noqa: F401


def test_real_intake_marks_workspace_before_retrieval(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    result = W.run(example_copy(tmp_path), "WO-E2E-HOLDOUT", intake_only=True, evaluation_holdout=True)
    from pathlib import Path

    ws = Path(result["workspace"])
    assert json.loads((ws / ".forge-run/manifest.json").read_text())["evaluation_holdout"] is True
    assert applicability(ws)["holdout"] is True


@pytest.mark.parametrize("heldout", [False, True])
def test_afo_launcher_carries_immutable_intake_scope(heldout, monkeypatch):
    calls = []
    monkeypatch.setattr(W, "run", lambda *a, **kw: calls.append(kw) or {"fabro_run_id": "typed-native-fixture"})
    result = runtime.launcher(
        {"example": "examples/fixture", "model": "local-fixture", "provider": "ollama", "evaluation_holdout": heldout},
        "WO-E2E",
        {},
    )
    assert result["fabro_run_id"] == "typed-native-fixture"
    assert calls[0].get("evaluation_holdout", False) is heldout


def test_resume_cannot_remove_the_ancestors_holdout_before_context(pair, monkeypatch):
    src, old, _, _, _, example = pair
    old["evaluation_holdout"] = True
    (src / ".forge-run/manifest.json").write_text(json.dumps(old))

    class BeforeInference(Exception):
        pass

    def stop(ws, manifest, *a, **kw):
        assert manifest["evaluation_holdout"] is True and applicability(ws)["holdout"] is True
        raise BeforeInference

    monkeypatch.setattr(W, "resume_from", stop)
    with pytest.raises(BeforeInference):
        W.run(example, "WO-E2E-RESUMED", resume="WO-SRC", evaluation_holdout=False)


@pytest.mark.parametrize("invalid", [None, "false", 0, 1])
def test_non_boolean_scope_is_not_silently_coerced(tmp_path, invalid):
    with pytest.raises(ValueError, match="EVALUATION_HOLDOUT_FLAG_INVALID"):
        W.run(tmp_path / "unread-example", "WO-INVALID", intake_only=True, evaluation_holdout=invalid)
