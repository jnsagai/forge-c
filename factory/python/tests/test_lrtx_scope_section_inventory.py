"""Literal owner scope cannot silently disappear behind a peripheral's seed catalog."""
import json

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import swe1
from forge_factory.lrtx.obligations import CoherentScopeRefused, scope_sections


def test_real_rcc_scope_includes_every_declared_bus_and_reset_section():
    scope = json.loads((REPO_ROOT / "examples/0002a-arm_55_rcc_ll/workorder.json").read_text())["scope"]
    selected = scope_sections(scope, "RM0486", ["14.10.1", "14.10.2", "14.10.79", "14.10.64"])
    required = {f"14.10.{n}" for n in [1, 2, *range(64, 75), *range(79, 91)]}
    assert set(selected) == required and len(selected) == len(required) == 25


def test_generic_manual_lists_revision_and_exclusions_do_not_change_authority():
    scope = ["Controls from MANUAL42 Rev. 3, sections 7.2.1–7.2.3, 7.2.5 and 7.2.7.",
             "OTHER42 7.2.8; protocol version 1.2.3.", " Out of scope: MANUAL42 7.2.9."]
    assert scope_sections(scope, "MANUAL42", ["7.2.1"]) == ["7.2.1", "7.2.2", "7.2.3", "7.2.5", "7.2.7"]


@pytest.mark.parametrize("span", ["2.3.5-2.3.1", "2.3.1-3.4.1", "2.3.1-2.3.1025", "2.3.1-5"])
def test_invalid_or_unbounded_ranges_refuse_instead_of_truncating(span):
    with pytest.raises(CoherentScopeRefused, match="SCOPE_SECTION_RANGE_UNREPRESENTABLE"):
        scope_sections(["RM0001 " + span], "RM0001", [])


def test_deeper_section_numbers_are_not_silently_shortened():
    assert scope_sections(["DOC9 § 3.2.1.4–3.2.1.6"], "DOC9", []) == ["3.2.1.4", "3.2.1.5", "3.2.1.6"]


def test_excessive_catalog_or_union_blocks_instead_of_truncating():
    with pytest.raises(CoherentScopeRefused, match="SCOPE_SECTION_INVENTORY_EXCEEDS_BOUND"):
        scope_sections([], "DOC9", [f"1.2.{i}" for i in range(1025)])
    with pytest.raises(CoherentScopeRefused, match="SCOPE_SECTION_INVENTORY_EXCEEDS_BOUND"):
        scope_sections(["DOC9 1.2.1025"], "DOC9", [f"1.2.{i}" for i in range(1024)])


def test_actual_inventory_expands_scope_without_losing_legacy_behavior(tmp_path, monkeypatch):
    from forge_factory import workorder

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, manifest = workorder.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-SCOPE-INVENTORY",
                                    purpose="ASPICE_ONLY")
    legacy = swe1.inventory(ws)
    manifest["local_profile"] = {"id": "local-rtx-v2-omniverse2-q38-aspice-stepwise-medium"}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    full = swe1.inventory(ws)
    assert not full["missing_sections"]
    assert len(full["scope_sections"]["required_sections"]) == 25
    assert len(full["registers"]) == 25 and len(legacy["registers"]) == 4
    assert set(legacy["items"]) < set(full["items"])
    assert any(item.startswith("RCC_APB") for item in full["items"])
    owned = [f"{g['register']}.{field}" for g in swe1.groups(full) for field in g["fields"]]
    assert set(owned) == set(full["items"]) and len(owned) == len(set(owned))
    assert all(len(g["fields"]) <= swe1.MAX_FIELDS for g in swe1.groups(full))


def test_missing_referenced_primary_section_blocks_before_inference(tmp_path, monkeypatch):
    from forge_factory import workorder
    from forge_factory.lrtx import structured

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, manifest = workorder.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-SCOPE-MISSING",
                                    purpose="ASPICE_ONLY")
    manifest["local_profile"] = {"id": "local-rtx-v2-omniverse2-q38-aspice-stepwise-medium"}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    p = ws / "inputs/index.md"
    p.write_text("\n".join(line for line in p.read_text().splitlines() if not line.startswith("14.10.90 |")) + "\n")
    monkeypatch.setattr(structured, "call", lambda *a, **k: pytest.fail("missing primary evidence is not an author task"))
    result = swe1._visit(ws, "unused", {"calls": 0, "max_calls": 100}, {})
    assert result["status"] == "FAILED" and "LRTX_INVENTORY_SECTION_MISSING:14.10.90" in result["issues"]


def test_full_scope_visit_uses_pinned_call_envelope_and_explicit_smaller_limit(tmp_path, monkeypatch):
    from forge_factory import workorder
    from forge_factory.lrtx import visit

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, manifest = workorder.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-SCOPE-CALLS",
                                    purpose="ASPICE_ONLY")
    assert visit.author_call_limit(ws, "SWE.1", 35) == 35
    manifest["local_profile"] = {"id": "local-rtx-v2-omniverse2-q38-aspice-stepwise-medium"}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(swe1, "_visit", lambda ws, model, budget, routed: budget)
    assert swe1.visit(ws, "unused")["max_calls"] == 256
    assert swe1.visit(ws, "unused", max_calls=2)["max_calls"] == 2
    assert visit.author_call_limit(ws, "SWE.2", 35) == 35


@pytest.mark.parametrize("value", [True, 0, -1, 4097, 2.5, "256"])
def test_invalid_profile_call_limits_cannot_expand_admission(tmp_path, monkeypatch, value):
    from forge_factory.lrtx import profile, visit

    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {"id": "fixture"}}))
    monkeypatch.setattr(profile, "load", lambda name: {"structured": {"author_max_calls_by_phase": {"SWE.1": value}}})
    with pytest.raises(ValueError, match="PROFILE_AUTHOR_CALL_LIMIT_INVALID"):
        visit.author_call_limit(tmp_path, "SWE.1", 35)
