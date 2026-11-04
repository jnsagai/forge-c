"""Actual M3 records feed existing factual memory, never driver control or trusted repair instructions."""
import json

import pytest
from forge_factory.afo import line_lessons as L, line_orders as LO
from forge_factory.afo.queue import Store
from forge_factory.afo.durable import Refused
from forge_factory.knowledge.store import LessonStore
from test_line_conductor_m3 import env, write_campaign, grant, lineage, placer  # noqa: F401


@pytest.fixture
def finished(env):
    write_campaign(env, [lineage("crc-hal", "CRCHAL", "20261104-L37")])
    grant(env)
    p = placer(env)
    p.cycle()
    wo = env["line"].launched[-1]["wo"]
    env["line"].finish(wo)
    p.cycle()
    s = Store(LO.supervisor_dir() / "line-queue.sqlite3")
    # The ACT hook already captured into the default store. Rewind only the test cursor for the isolated store.
    with s.tx() as c:
        c.execute("DELETE FROM afo_control WHERE key=?", (L.CURSOR,))
    return env, s, wo, LessonStore(env["tmp"] / "lessons.sqlite3")


def test_terminal_m3_experience_is_durable_and_does_not_create_or_validate_lessons(finished):
    env, store, wo, lessons = finished
    before = store.orders(), [store.attempts(o["order_id"]) for o in store.orders()]
    result = L.capture(store, lessons)
    assert result["processed_attempts"] == 1 and result["experience_refs"]
    assert result["model_calls"] == result["new_lessons"] == 0
    assert lessons.list("VALIDATED") == []
    from forge_factory.knowledge.experience import report
    count = report(lessons)["unique_experiences"]
    L.capture(store, lessons)  # resets bounded cursor
    L.capture(store, lessons)  # replay deduplicates the same native facts
    assert report(lessons)["unique_experiences"] == count
    assert before == (store.orders(), [store.attempts(o["order_id"]) for o in store.orders()])


def test_missing_source_is_a_capture_gap_and_never_blocks_a_driver(finished):
    env, store, wo, lessons = finished
    (env["line"].workspace(wo) / ".forge-run/manifest.json").unlink()
    before = store.orders()
    result = L.capture(store, lessons)
    assert result["status"] == "CAPTURE_GAPS" and result["gaps"]
    assert before == store.orders()
    assert lessons.list("VALIDATED") == []


def test_holdout_scope_is_retained_for_future_independent_qualification(finished):
    env, store, wo, lessons = finished
    path = env["line"].workspace(wo) / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["evaluation_holdout"] = True
    path.write_text(json.dumps(manifest))
    L.capture(store, lessons)
    with lessons._conn() as c:
        records = [json.loads(r[0]) for r in c.execute("SELECT record FROM job_experience")]
    assert records and all(r["cohort"]["evaluation_holdout"] is True for r in records)


def test_unknown_store_or_unbounded_capture_is_refused(finished):
    env, store, _, lessons = finished
    for limit in [0, 33, True]:
        with pytest.raises(Refused, match="BOUND_REQUIRED"):
            L.capture(store, lessons, limit=limit)
    with pytest.raises(Refused, match="STORE_SCOPE_MISMATCH"):
        L.capture(Store(env["tmp"] / "foreign.sqlite"), lessons)


def test_existing_act_cycle_records_bounded_model_free_capture_without_validating_lessons(finished):
    path = LO.supervisor_dir() / "line-learning.json"
    assert path.is_file()
    report = json.loads(path.read_text())
    assert report["model_calls"] == report["new_lessons"] == 0
    assert report["processed_attempts"] <= 8
