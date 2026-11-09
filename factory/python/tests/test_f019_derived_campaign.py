"""Feature 019 (owner 2026-11-09): the driver ladder is factory source; every deploy derives the line campaign from it."""
from __future__ import annotations

import yaml
from forge_factory.afo import line_campaign as LCMP
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import digest

SIX = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]


def _sub(doc):
    return yaml.safe_load(yaml.safe_dump(doc, sort_keys=False).replace("@SOURCE@", "a" * 40))


def test_the_ladder_is_the_owner_order_and_each_hal_follows_its_ll():
    assert D.LADDER == ("wwdg-ll", "wwdg-hal", "spi-ll", "spi-hal", "tim-ll", "tim-hal")
    assert set(D.LADDER) <= set(D._LINEAGE) and len(set(D.LADDER)) == len(D.LADDER)
    for k, lid in enumerate(D.LADDER):
        ll = D._LINEAGE[lid]["depends_on"]
        if ll is not None:
            assert k > 0 and D.LADDER[k - 1] == ll


def test_the_derived_campaign_validates_and_follows_the_ladder():
    doc = D.derived_campaign()
    assert doc == D.derived_campaign() and doc["campaign_id"] == D.CAMPAIGN
    assert LCMP.validate(_sub(doc)) == [] and LCMP.contract_errors(_sub(doc)) in ([], None)
    by = {L["id"]: L for L in doc["lineages"]}
    assert list(by) == [L["id"] for L in D.LINEAGES]
    for k, lid in enumerate(D.LADDER):
        L, spec = by[lid], D._LINEAGE[lid]
        assert (L["status"], L["priority"], L["phases"], L["factory_revision"]) == ("ACTIVE", 50 - k, SIX, "@SOURCE@")
        assert (L["example"], L["tag"], L["series"], L["driver_class"]) == (
            spec["example"], spec["tag"], spec["series"], spec["driver_class"])
        assert digest(L["quality"]) == D.QUALITY_SHA and (L["profile"], L["run_model"]) == (D.PROFILE, D.RUN_MODEL)
        if k == 0:
            assert "after" not in L and "depends_on" not in L
        elif spec["depends_on"]:
            assert L["depends_on"] == {"lineage": spec["depends_on"], "phase": "SWE.6", "verdict": "PASS"}
            assert "after" not in L
        else:
            assert L["after"] == {"lineage": D.LADDER[k - 1], "phase": "SWE.6", "verdict": "PASS"}
            assert "depends_on" not in L
    for lid in set(by) - set(D.LADDER):
        assert (by[lid]["status"], by[lid]["priority"]) == ("ON_HOLD", 30)


def test_the_derived_campaign_parses_like_a_campaign_file(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(_sub(D.derived_campaign()), sort_keys=False))
    c = LCMP.parse(p, require_approval=False)
    assert [L.id for L in c.lineages] == [L["id"] for L in D.LINEAGES]
    assert {L.id: L.status for L in c.lineages}["wwdg-ll"] == "ACTIVE"
