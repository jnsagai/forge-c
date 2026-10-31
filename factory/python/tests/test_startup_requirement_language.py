"""Replay a real Qwen startup invariant refused only for a qualified reset phrase."""
import json
from pathlib import Path

import pytest
from forge_factory import workorder
from forge_factory.common import REPO_ROOT
from forge_factory.inspection import test_mapping as mapping
from forge_factory.lrtx import review, review_semantic, swe1


@pytest.mark.parametrize("event", ["reset", "a reset", "the reset", "an RCC reset", "an IWDG reset",
                                  "a power-on reset", "a TIMER7 domain reset", "an STM32 peripheral domain reset"])
def test_existing_startup_classifiers_agree_for_qualified_reset_events(event):
    statement = f"While no LL function has been called after {event}, the driver shall not write any register."
    assert swe1.STARTUP.match(statement)
    assert mapping.STARTUP.search(statement)
    assert review_semantic.STARTUP.search("**SWR-001** " + statement).group(1) == "SWR-001"


@pytest.mark.parametrize("event", ["before reset", "after a reset-control bit write", "after a reset_code update",
                                  "after a resettable field update"])
def test_register_names_or_operations_are_not_startup_reset_events(event):
    statement = f"While no LL function has been called {event}, the driver shall not write any register."
    assert not swe1.STARTUP.match(statement)
    assert not mapping.STARTUP.search(statement)


@pytest.fixture
def replay(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws, _ = workorder.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-REAL-QWEN-STARTUP-REPLAY", purpose="QM")
    # Native 01M65P3JYHR82VVYR5K1FCK1YQ, job afo-product-109acc58b919a37613210e04.
    # This is designated engineering output, not prompts or hidden reasoning.
    doc = json.loads((Path(__file__).parent / "fixtures/qm-rcc-crosscutting-20261030.json").read_text())
    return ws, doc


def test_full_original_qwen_packet_passes_the_unchanged_remaining_validators(replay):
    ws, doc = replay
    assert _validate(ws, doc) == []


def test_qualified_startup_still_requires_target_verification(replay):
    ws, doc = replay
    doc["requirements"][0]["verified_by"] = "host_unit_test"
    assert any("target_robot_test" in error for error in _validate(ws, doc))


def _validate(ws, doc):
    from forge_factory.assurance.hardware import index

    return swe1.validate_group(ws, doc, None, swe1.system_name(ws), index(ws / "inputs/sections/RM0486"))


def test_original_packet_has_a_causal_legacy_classifier_reproducer(replay, monkeypatch):
    import re

    ws, doc = replay
    current = swe1.STARTUP
    monkeypatch.setattr(swe1, "STARTUP", re.compile(r"^\s*While no .*after reset", re.I))
    refused = _validate(ws, doc)
    assert len(refused) == 1 and "must state the reset/startup behaviour" in refused[0]
    monkeypatch.setattr(swe1, "STARTUP", current)
    assert _validate(ws, doc) == []


def test_review_facts_and_semantic_reset_inventory_retain_qualified_startup(replay):
    ws, doc = replay
    statement = doc["requirements"][0]["statement"]
    path = ws / "workproducts/SWE.1/software_requirements.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("- **SWR-001** " + statement + "\n")
    facts = {"reqs": {"SWR-001": {"statement": statement}}}
    assert review_semantic.startup_requirements(facts) == {"SWR-001": statement}
    refutations = review.fact_conflicts(ws, "SWE.1", "SWE1-03", ["The requirements have no startup behaviour."])
    assert len(refutations) == 1 and "SWR-001 specifies it" in refutations[0]

