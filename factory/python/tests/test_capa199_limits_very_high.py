"""CAPA-199 (owner 2026-11-09: "increase all limits to very high values ... do a complete audit in the factory").

The audit of code/config and of ten days of owner-lane evidence found arbitrary caps that refuse or cut work before a
physical limit is reached. Physical limits (the 262144-token context, VRAM) and signed owner controls are unchanged.
"""
import json

from forge_factory.brownfield import resume
from forge_factory.lrtx import obligations, request_measurement, structured, swe1, visit
from forge_factory.workflow import builder


def test_a_new_root_lineage_gets_a_year_and_ten_thousand_attempts():
    assert resume.DEFAULT_LIMITS == {"max_attempts": 10000, "max_wall_seconds": 31536000}


def test_time_box_continuations_are_not_capped_by_the_rework_budget():
    assert builder.CONTINUATION_MAX_VISITS >= 100_000 > 8 * builder.MAX_VISITS


def test_visit_call_and_time_limits_are_very_high(tmp_path):
    assert visit.MAX_VISIT_CALLS >= 1_000_000 and visit.CALL_TIMEOUT_S == 21600
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({}))
    assert visit.author_call_limit(tmp_path, "SWE.1", 35, explicit=500_000) == 500_000
    import inspect

    assert inspect.signature(structured.call).parameters["timeout"].default == 21600


def test_repair_packets_carry_every_finding():
    assert visit.REPAIR_FINDINGS_MAX >= 200 and visit.KEEP_FIXED_MAX >= 200


def test_whole_functional_chapter_and_large_native_measurement():
    assert swe1.FUNCTIONAL_SOURCE_MAX_CHARS >= 1_048_576
    assert request_measurement.MAX_REQUEST_BYTES >= 64 * 1024 * 1024


def test_an_oversized_coherent_set_is_one_packet_and_other_fields_keep_their_packing():
    big = [f"B{i}" for i in range(7)]
    small = [f"S{i}" for i in range(6)]
    parts = obligations.partition("REG", big + small, [[f"REG.{f}" for f in big], ["REG.S0", "REG.S1"]], 5)
    assert sorted(big) in [sorted(p) for p in parts]
    others = [p for p in parts if not set(p) & set(big)]
    assert all(len(p) <= 5 for p in others) and sorted(sum(others, [])) == sorted(small)
    assert any({"S0", "S1"} <= set(p) for p in others)


def test_registers_without_oversized_sets_are_partitioned_exactly_as_before():
    names = [f"F{i}" for i in range(12)]
    sets = [["REG.F0", "REG.F7"], ["REG.F3", "REG.F4", "REG.F9"]]
    # the output of the partition before CAPA-199 (commit 41513fb8) for the same input
    assert obligations.partition("REG", names, sets, 5) == [
        ["F0", "F5", "F7", "F10"], ["F1", "F2", "F6", "F11"], ["F3", "F4", "F8", "F9"]]
    assert [len(p) for p in obligations.partition("REG", names, [], 5)] == [4, 4, 4]
