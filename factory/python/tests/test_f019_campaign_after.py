"""Feature 019 (owner 2026-11-09): campaign key `after` - a lineage waits for another lineage's phase without
building on it (no provided_from)."""
from __future__ import annotations

import pytest
import yaml
from forge_factory.afo import line_campaign as LCMP
from test_line_conductor_m3 import lineage

AFTER = {"lineage": "a-ll", "phase": "SWE.6", "verdict": "PASS"}


def _doc(lins):
    return {"schema": LCMP.SCHEMA_ID, "campaign_id": "CMP-TEST-1", "line": "local", "wo_prefix": "WO-F014",
            "lineages": lins}


def test_after_is_accepted_by_code_and_contract():
    d = _doc([lineage("a-ll", "AL", "20261109-L1"), lineage("b-ll", "BL", "20261109-L2", after=AFTER)])
    assert LCMP.validate(d) == []
    assert LCMP.contract_errors(d) in ([], None)


@pytest.mark.parametrize("bad", [
    {"lineage": "zz-ll", "phase": "SWE.6", "verdict": "PASS"},
    {"lineage": "b-ll", "phase": "SWE.6", "verdict": "PASS"},
    {"lineage": "a-ll", "phase": "SWE.6", "verdict": "FAIL"},
    {"lineage": "a-ll", "phase": "SWE.9", "verdict": "PASS"},
    {"lineage": "a-ll", "verdict": "PASS"},
    "a-ll",
])
def test_a_malformed_after_is_refused(bad):
    errs = LCMP.validate(_doc([lineage("a-ll", "AL", "20261109-L1"), lineage("b-ll", "BL", "20261109-L2", after=bad)]))
    assert any(e.endswith("FIELD_INVALID:after") for e in errs), errs


def test_a_cycle_over_after_and_depends_on_is_refused():
    d = _doc([lineage("a-ll", "AL", "20261109-L1", after={"lineage": "b-hal", "phase": "SWE.6", "verdict": "PASS"}),
              lineage("b-hal", "BH", "20261109-L2", depends_on=AFTER)])
    assert any(e.startswith("DEPENDENCY_CYCLE") for e in LCMP.validate(d))


def test_after_survives_parsing(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(_doc([lineage("a-ll", "AL", "20261109-L1"),
                                      lineage("b-ll", "BL", "20261109-L2", after=AFTER)]), sort_keys=False))
    c = LCMP.parse(p, require_approval=False)
    assert c.lineages[1].after == AFTER and c.lineages[1].depends_on is None and c.lineages[0].after is None
