"""Pinned phase capacity reaches all structured authors without resetting an open visit."""
import importlib
import json

import pytest
from forge_factory.lrtx import profile
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import visit as V

PROFILE = "local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector-capacity"
CURRENT = "local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector"
ENTRIES = [("swe2", "visit", "_visit", 256), ("swe3", "visit_code", "_visit_code", 2048),
           ("swe4", "visit_tests", "_visit_tests", 4096), ("swe5", "visit_tests", "_visit_tests", 2048),
           ("swe6", "visit_tests", "_visit_tests", 4096)]


def manifest(ws, selected):
    (ws / ".forge-run").mkdir(exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "local_profile": {"id": selected}}))


@pytest.mark.parametrize("module,entry,worker,capacity", ENTRIES)
def test_real_author_entry_uses_pinned_phase_capacity_and_preserves_explicit_smaller_limit(
    tmp_path, monkeypatch, module, entry, worker, capacity
):
    manifest(tmp_path, PROFILE)
    loaded = importlib.import_module("forge_factory.lrtx." + module)
    monkeypatch.setattr(loaded, worker, lambda ws, model, budget, findings: budget)
    call = getattr(loaded, entry)
    budget = call(tmp_path, "unused")
    assert budget["max_calls"] == capacity
    # Continue the SAME visit after passing35calls; no new author allowance or progress reset.
    state = json.loads(open_state(tmp_path, loaded.PHASE).read_text())
    state["calls"] = 36
    open_state(tmp_path, loaded.PHASE).write_text(json.dumps(state))
    resumed = call(tmp_path, "unused", resume=True)
    assert resumed["calls"] == 36 and resumed["max_calls"] == capacity
    assert call(tmp_path, "unused", max_calls=2)["max_calls"] == 2


def open_state(ws, phase):
    return ws / ".forge-run/lrtx" / phase / "visit-state.json"


@pytest.mark.parametrize("module,entry,worker,capacity", ENTRIES)
def test_existing_profile_without_later_phase_overrides_keeps_registry_default(
    tmp_path, monkeypatch, module, entry, worker, capacity
):
    manifest(tmp_path, CURRENT)
    loaded = importlib.import_module("forge_factory.lrtx." + module)
    monkeypatch.setattr(loaded, worker, lambda ws, model, budget, findings: budget)
    assert getattr(loaded, entry)(tmp_path, "unused")["max_calls"] == 35


def test_larger_phase_allowance_runs_every_coherent_obligation_without_refilling_on_continue(tmp_path, monkeypatch):
    from forge_factory.lrtx import swe4

    manifest(tmp_path, PROFILE)
    calls = []
    marker = "DECISIVE_FINAL_OBLIGATION"

    def answer(packet, **kw):
        ident = packet["task"].removeprefix("test:")
        calls.append(ident)
        return {"doc": {"obligation": ident}, "errors": [], "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                "wall_ms": 1, "finish_reason": "stop"}

    monkeypatch.setattr(S, "call", answer)
    monkeypatch.setattr(S, "schema_mode_for", lambda _: ("json_schema", "fixture"))
    expected = [f"UT-{i:03d}" for i in range(1, 60)] + [marker]

    def run(ws, model, budget, findings):
        results = []
        for ident in expected:
            packet = {"role": "swe4-author", "task": "test:" + ident, "input_hash": ident, "model": model,
                      "accounting": {}, "output_schema": {"type": "object", "required": ["obligation"],
                          "properties": {"obligation": {"enum": [ident]}}, "additionalProperties": False}}
            results.append(V.run_task(ws, "SWE.4", "test:" + ident, lambda *a, p=packet: p,
                                      lambda doc, ident=ident: [] if doc["obligation"] == ident else ["wrong obligation"],
                                      budget))
        return results, budget

    monkeypatch.setattr(swe4, "_visit_tests", run)
    results, budget = swe4.visit_tests(tmp_path, "fixture")
    assert calls == expected and len(results) == len(expected) == 60
    assert all(r["status"] == "VALID" for r in results) and budget["calls"] == 60
    # A real continuation revalidates/checkpoints all60, making no additional model call.
    results, resumed = swe4.visit_tests(tmp_path, "fixture", resume=True)
    assert resumed["calls"] == 60 and len(calls) == 60 and all(r["reused"] for r in results)
    assert not (tmp_path / "inspection").exists()  # A complete authored fixture does not manufacture a quality gate.


def test_candidate_changes_only_finite_author_capacity_not_live_profile_or_physical_resources():
    import copy

    old, candidate = profile.load(CURRENT), profile.load(PROFILE)
    assert old["structured"]["author_max_calls_by_phase"] == {"SWE.1": 256}
    expected = {"SWE.1": 256, **{"SWE." + module[-1]: cap for module, _, _, cap in ENTRIES}}
    assert candidate["structured"]["author_max_calls_by_phase"] == expected
    for key in ("runtime", "gateway", "admission", "models", "afo"):
        assert candidate[key] == old[key]
    stripped = copy.deepcopy(candidate["structured"])
    stripped.pop("author_max_calls_by_phase")
    assert stripped == {k: v for k, v in old["structured"].items() if k != "author_max_calls_by_phase"}
