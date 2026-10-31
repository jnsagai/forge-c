"""Joint field obligations must fit one packet; unrelated legacy grouping stays stable."""
import json

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import swe1


def inventory(names, links=(), register="CRC_CR"):
    return {"registers": [{"register": register, "section": "test", "file": "test.md", "pages": [],
                          "fields": dict.fromkeys(names, {})}],
            "coherent_field_sets": [list(x) for x in links]}


def test_actual_crc_coupled_reversal_fields_cannot_cross_packet_boundaries():
    # RM field order, as present in the observed live inventory.
    names = ["RTYPE_OUT", "RTYPE_IN", "REV_OUT", "REV_IN", "POLYSIZE", "RESET"]
    inv = inventory(names, [("CRC_CR.REV_OUT", "CRC_CR.RTYPE_OUT"), ("CRC_CR.REV_IN", "CRC_CR.RTYPE_IN")])
    parts = [set(g["fields"]) for g in swe1.groups(inv)]
    assert any({"REV_IN", "RTYPE_IN"} <= p for p in parts), parts
    assert any({"REV_OUT", "RTYPE_OUT"} <= p for p in parts), parts
    assert set.union(*parts) == set(names) and sum(map(len, parts)) == len(names)
    assert all(len(p) <= swe1.MAX_FIELDS for p in parts)


def test_an_oversized_joint_obligation_blocks_instead_of_being_silently_split():
    names = [f"F{i}" for i in range(swe1.MAX_FIELDS + 1)]
    inv = inventory(names, [[f"DEV_CR.{f}" for f in names]], "DEV_CR")
    with pytest.raises(ValueError, match="COHERENT_SCOPE_GROUP_EXCEEDS_FIELD_LIMIT"):
        swe1.groups(inv)


def test_legacy_inventory_keeps_the_existing_balanced_partition_exactly():
    inv = inventory(["A", "B", "C", "D", "E", "F"])
    inv.pop("coherent_field_sets")
    assert [list(g["fields"]) for g in swe1.groups(inv)] == [["A", "B", "C"], ["D", "E", "F"]]


def test_owner_clause_dependencies_are_generic_and_ignore_explicit_exclusions():
    from forge_factory.lrtx.obligations import scope_field_sets

    scope = json.loads((REPO_ROOT / "examples/0014c-st-cube-crc/workorder.json").read_text())["scope"]
    links = scope_field_sets(scope)
    assert ["CRC_CR.REV_IN", "CRC_CR.RTYPE_IN"] in links
    assert ["CRC_CR.REV_OUT", "CRC_CR.RTYPE_OUT"] in links
    assert scope_field_sets(["Configure (DEV_CFG.VALUE with DEV_CFG.SCALE).",
                             "Out of scope: (DEV_CFG.IRQ with DEV_CFG.FLAG)."]) == [["DEV_CFG.VALUE", "DEV_CFG.SCALE"]]


def test_transitive_joint_fields_keep_global_coverage_and_unique_ownership():
    names = ["A", "B", "C", "D", "E", "F", "G"]
    links = [("DEV_CR.A", "DEV_CR.C"), ("DEV_CR.C", "DEV_CR.F")]
    parts = [set(g["fields"]) for g in swe1.groups(inventory(names, links, "DEV_CR"))]
    assert any({"A", "C", "F"} <= p for p in parts)
    assert set.union(*parts) == set(names) and sum(map(len, parts)) == len(names)


def test_unknown_member_of_a_joint_obligation_is_not_dropped():
    inv = inventory(["A", "B"], [("DEV_CR.A", "DEV_CR.MISSING")], "DEV_CR")
    with pytest.raises(ValueError, match="COHERENT_SCOPE_FIELD_NOT_IN_INVENTORY"):
        swe1.groups(inv)


@pytest.mark.parametrize("cross_register", [False, True])
def test_unrepresentable_obligation_blocks_before_any_model_request(tmp_path, monkeypatch, cross_register):
    names = [f"F{i}" for i in range(swe1.MAX_FIELDS + 1)]
    links = [["DEV_CR." + f for f in names]]
    if cross_register:
        links = [["DEV_CR.F0", "OTHER_CR.F0"]]
    inv = {**inventory(names, links, "DEV_CR"), "missing_sections": []}
    monkeypatch.setattr(swe1, "inventory", lambda ws: inv)
    from forge_factory.lrtx import structured

    def unexpected_call(*args, **kwargs):
        pytest.fail("A model cannot repair unsupported administrative partitioning")

    monkeypatch.setattr(structured, "call", unexpected_call)
    reply = swe1._visit(tmp_path, "unused-model", {"calls": 0, "max_calls": 10, "log": []}, {})
    assert reply["status"] == "FAILED" and reply["issues"][0].startswith("CAPABILITY_LIMIT:COHERENT_SCOPE_")
    assert json.loads((tmp_path / ".forge-run/lrtx/SWE.1/reply.json").read_text()) == reply


def test_actual_inventory_uses_scope_dependencies_only_with_the_opt_in_profile(tmp_path, monkeypatch):
    from test_lrtx_swe1 import ws as iwdg_fixture

    ws = iwdg_fixture.__wrapped__(tmp_path, monkeypatch)
    path = ws / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["scope"].append("Status observation (IWDG_SR.PVU with IWDG_SR.RVU).")
    for profile_id, enabled in [("local-rtx-v2-omniverse2-q38-quality", False),
                                ("local-rtx-v2-omniverse2-q38-aspice", True)]:
        manifest["local_profile"] = {"id": profile_id}
        path.write_text(json.dumps(manifest))
        inv = swe1.inventory(ws)
        assert ("coherent_field_sets" in inv) is enabled
        if enabled:
            assert ["IWDG_SR.PVU", "IWDG_SR.RVU"] in inv["coherent_field_sets"]
            assert any({"PVU", "RVU"} <= set(g["fields"]) for g in swe1.groups(inv))
