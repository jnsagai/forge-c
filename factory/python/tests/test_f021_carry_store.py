"""Feature 021 FR-001/FR-009 (T005): the validated-item store keys items by (phase, item key, content sha, dependency
set sha), keeps their provenance and refuses a source record that changed after it was stored."""
from pathlib import Path

import pytest
from forge_factory.lrtx import carry_store as CS


@pytest.fixture()
def store(tmp_path):
    return CS.Store(tmp_path / "validated-items.sqlite3")


def _rec(tmp_path, name="r.json", text='{"x": 1}'):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_put_then_find_by_dependency_set(store, tmp_path):
    rec = _rec(tmp_path)
    store.put("SWE.1", "g_state/get_state", content_sha="c" * 64, dep_sha="d" * 64, record=rec,
              source_order="WO-L50", verdicts={"IQ": "PASS"})
    hit = store.find("SWE.1", "g_state/get_state", dep_sha="d" * 64)
    assert hit["content_sha"] == "c" * 64 and hit["source_order"] == "WO-L50" and hit["verdicts"] == {"IQ": "PASS"}
    assert store.find("SWE.1", "g_state/get_state", dep_sha="e" * 64) is None  # another dependency set: not valid


def test_the_newest_source_wins_and_order_priority_is_respected(store, tmp_path):
    r1, r2 = _rec(tmp_path, "a.json"), _rec(tmp_path, "b.json", '{"x": 2}')
    store.put("SWE.1", "k", content_sha="1" * 64, dep_sha="d" * 64, record=r1, source_order="WO-L49", verdicts={})
    store.put("SWE.1", "k", content_sha="2" * 64, dep_sha="d" * 64, record=r2, source_order="WO-L50", verdicts={})
    assert store.find("SWE.1", "k", dep_sha="d" * 64)["source_order"] == "WO-L50"
    assert store.find("SWE.1", "k", dep_sha="d" * 64, sources=["WO-L49", "WO-L50"])["source_order"] == "WO-L49"


def test_a_changed_source_record_is_refused(store, tmp_path):
    rec = _rec(tmp_path)
    store.put("SWE.1", "k", content_sha="c" * 64, dep_sha="d" * 64, record=rec, source_order="WO-L50", verdicts={})
    rec.write_text('{"x": "edited"}')
    with pytest.raises(CS.CarryRefused, match="SOURCE_RECORD_CHANGED"):
        store.find("SWE.1", "k", dep_sha="d" * 64)
    Path(rec).unlink()
    with pytest.raises(CS.CarryRefused, match="SOURCE_RECORD_CHANGED"):
        store.find("SWE.1", "k", dep_sha="d" * 64)
