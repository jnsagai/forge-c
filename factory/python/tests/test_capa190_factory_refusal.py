"""CAPA-190: a refusal the factory raises before any model call is a factory defect, not an UNKNOWN dead end.

Omniverse2 owner lane 2026-11-07 18:45 UTC: WO-F014-SWE1-GPIOL-20261107-L40C (V21.3, f283dbae) refused its SWE.1 visit
with LRTX_INVENTORY_SECTION_MISSING:15.3.3-5 (CAPA-189). CRE leaves that text UNCLASSIFIED, it became the bundle's
dominant observation and recovery closed the order UNKNOWN_NOT_RECOVERABLE_BY_AFO: no maintainer, no planner.
"""
import json

import pytest
from forge_factory.afo import bundle, recovery

ISSUES = ["MISSING_REQUIRED_OUTPUT:workproducts/SWE.1/software_requirements.md",
          "MISSING_REQUIRED_OUTPUT:traceability/requirements_to_tests.csv",
          "CONTRACT_MISSING:workproducts/SWE.1/register_effects.json",
          "LRTX_TASK_INVALID:LRTX_INVENTORY_SECTION_MISSING:15.3.3",
          "LRTX_TASK_INVALID:LRTX_INVENTORY_SECTION_MISSING:15.3.4"]


def _ws(tmp_path, issues, status="INCOMPLETE"):
    ws = tmp_path / "WO-F014-SWE1-GPIOL-20261107-L40C" / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(
        {"work_order": "WO-F014-SWE1-GPIOL-20261107-L40C", "created_at": "2026-11-07T18:43:38Z",
         "factory_revision": {"commit": "f283dbaeb2d83407e426dd099853d436224c0a88", "basis": "manifest"},
         "driver": "STM32N6_GPIO_LL_ST", "target": {"core": "cortex-m55"}}))
    rows = [{"issues": issues, "phase": "SWE.1", "result": "REJECTED", "status": status, "step": "author",
             "ts": "2026-11-07T18:45:07.862309Z"},
            {"gate": {"decision": "BLOCKED", "phase": "SWE.1",
                      "reason": "STUCK: repeated rejection without changed evidence; external diagnosis required"},
             "phase": "SWE.1", "step": "route", "ts": "2026-11-07T18:45:08.153861Z"}]
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return ws


def test_capa190_a_pre_model_factory_refusal_is_a_factory_defect(tmp_path):
    b = bundle.build(_ws(tmp_path, ISSUES), "afo-o", "afo-o-a1", open_capa=set())
    assert (b["phase"], b["failure_class"], b["error_code"]) == ("SWE.1", "FACTORY_CODE_DEFECT",
                                                                  "LRTX_INVENTORY_SECTION_MISSING")
    # the line worker sends FACTORY_CODE_DEFECT to isolated maintenance; the rule path never reads it as UNKNOWN
    plan = recovery.rule_plan(b, ws=None, order_env={}, tried_models=set(), eff=None,
                              attempt_started_utc="2026-11-07T18:43:38Z", allowed_models=[])
    assert plan["rationale_code"] == "FACTORY_DEFECT_NEEDS_EXTERNAL_CHANGE"


@pytest.mark.parametrize("raw", ["LRTX_TASK_INVALID:LRTX_RUNNER_ERROR:KeyError:'x'",
                                 "LRTX_TASK_INVALID:LRTX_SEMANTIC_ENGINE_FAULT: boom",
                                 "LRTX_TASK_INVALID:LRTX_SWE2_LAYER_NOT_SUPPORTED_YET (structured SWE.2 covers LL)"])
def test_capa190_every_listed_factory_refusal(tmp_path, raw):
    b = bundle.build(_ws(tmp_path, ["MISSING_REQUIRED_OUTPUT:workproducts/SWE.1/software_requirements.md", raw]),
                     "afo-o", "afo-o-a1", open_capa=set())
    assert b["failure_class"] == "FACTORY_CODE_DEFECT" and b["error_code"] == raw.split(":")[1].split()[0]


def test_capa190_model_output_and_agent_reported_issues_are_unchanged(tmp_path):
    # a product finding of a visit that did call the model keeps CRE's class (no factory refusal present)
    b = bundle.build(_ws(tmp_path, ISSUES[:3] + ["LRTX_TASK_INVALID:requirements:gpio: SWR id missing"]),
                     "afo-o", "afo-o-a1", open_capa=set())
    assert b["failure_class"] != "FACTORY_CODE_DEFECT"
    # an agent-reported (not deterministic) issue never becomes a factory defect by its text alone
    b = bundle.build(_ws(tmp_path / "r", ISSUES, status="DONE"), "afo-o", "afo-o-a1", open_capa=set())
    assert b["failure_class"] != "FACTORY_CODE_DEFECT"
    assert bundle.factory_refusal({"source_kind": "GATE", "failure_class": "PRODUCT_QUALITY",
                                   "excerpt": "LRTX_TASK_INVALID:LRTX_RUNNER_ERROR:x"}) is None
