"""CAPA-208 (owner 2026-11-09 "implement the 3 points that could make it faster"): in SPI LL L41N, 13 of 17 first
drafts failed (56% of the author's wall time); the largest class acted on a field that a sibling task of the same split
register owns (SPI_CR1.SPE in SPI_CR1_1, SPI_CFG2.MASTER in SPI_CFG2_4). WWDG, whose registers are not split, passed
every first draft. The first-draft prompt of a split register now names the sibling tasks and their fields, and the
checker names the owning task id; unsplit registers' packets are unchanged."""
from __future__ import annotations

from test_lrtx_swe1 import ws  # noqa: F401 - the IWDG LL workspace fixture (IWDG_SR splits into _1 and _2)

from forge_factory.lrtx import swe1


def _groups(ws):
    return {g["id"]: g for g in swe1.groups(swe1.inventory(ws))}


def test_a_split_register_task_names_its_siblings_and_their_fields(ws):  # noqa: F811
    gs = _groups(ws)
    sr1, sr2 = gs["IWDG_SR_1"], gs["IWDG_SR_2"]
    text = swe1.group_packet(ws, sr1, "qwen3-coder:30b")["instructions"]
    assert "Register IWDG_SR is split into 2 tasks" in text
    assert f"task IWDG_SR_2: {', '.join(sr2['fields'])}" in text and "This task is IWDG_SR_1" in text


def test_an_unsplit_register_packet_is_unchanged(ws):  # noqa: F811
    p = swe1.group_packet(ws, _groups(ws)["IWDG_KR"], "qwen3-coder:30b")
    assert "is split into" not in p["instructions"] and swe1.sibling_rule(ws, _groups(ws)["IWDG_KR"]) == ""


def test_the_checker_names_the_owning_sibling_task(ws):  # noqa: F811
    gs = _groups(ws)
    sr1, sr2 = gs["IWDG_SR_1"], gs["IWDG_SR_2"]
    other = next(iter(sr2["fields"]))
    doc = {"requirements": [{"key": "k", "statement": f"When requested, the x shall set IWDG_SR.{other}.",
                             "source_page": sr1["pages"][0], "verification": "passes when", "verified_by":
                             "host_unit_test", "effects": [{"case": "c", "register": "IWDG_SR", "field": other,
                                                            "op": "set", "value": "", "requested": ""}]}],
           "not_covered": [], "open_points": []}
    out = swe1.validate_group(ws, doc, sr1, "x", {g["register"]: {"fields": g["fields"]} for g in gs.values()})
    assert any(f"acts on IWDG_SR.{other}, which task IWDG_SR_2 covers" in f for f in out), out
