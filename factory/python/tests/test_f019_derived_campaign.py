"""Feature 019 (owner 2026-11-09): the driver ladder is factory source; every deploy derives the line campaign from it.
Owner ~14:00: SWE.1 first across WWDG LL, WWDG HAL, SPI LL, TIM LL ("just when we are sure that SW1 is really stable,
then we can go for the next one") - the ladder runs one phase stage (LADDER_PHASES) across all steps."""
from __future__ import annotations

import yaml
from forge_factory.afo import line_campaign as LCMP
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import digest

SIX = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
L29 = "WO-F014-SWE6-WWDGL-20261103-L29"


def _sub(doc):
    return yaml.safe_load(yaml.safe_dump(doc, sort_keys=False).replace("@SOURCE@", "a" * 40))


def test_the_ladder_is_the_owner_order_for_the_swe1_stage():
    assert D.LADDER == ("wwdg-ll", "wwdg-hal", "spi-ll", "tim-ll") and D.LADDER_PHASES == ("SWE.1", "SWE.2")
    assert set(D.LADDER) <= set(D._LINEAGE) and len(set(D.LADDER)) == len(D.LADDER)
    assert D.PROVIDED_LL == {"wwdg-hal": L29}  # the WWDG LL that passed all six phases (factory 82fabdb9)


def test_the_derived_campaign_validates_and_follows_the_ladder():
    doc = D.derived_campaign()
    assert doc == D.derived_campaign() and doc["campaign_id"] == D.CAMPAIGN
    assert LCMP.validate(_sub(doc)) == [] and LCMP.contract_errors(_sub(doc)) in ([], None)
    by = {L["id"]: L for L in doc["lineages"]}
    assert list(by) == [L["id"] for L in D.LINEAGES]
    for k, lid in enumerate(D.LADDER):
        L, spec = by[lid], D._LINEAGE[lid]
        assert (L["status"], L["priority"], L["phases"], L["factory_revision"]) == (
            "ACTIVE", 50 - k, ["SWE.1", "SWE.2"], "@SOURCE@")
        assert (L["example"], L["tag"], L["series"], L["driver_class"]) == (
            spec["example"], spec["tag"], spec["series"], spec["driver_class"])
        assert digest(L["quality"]) == D.QUALITY_SHA and (L["profile"], L["run_model"]) == (D.PROFILE, D.RUN_MODEL)
        assert "depends_on" not in L
        if k == 0:
            assert "after" not in L
        else:
            assert L["after"] == {"lineage": D.LADDER[k - 1], "phase": "SWE.2", "verdict": "PASS"}
    assert by["wwdg-hal"]["provided_from"] == L29
    assert all("provided_from" not in by[i] for i in ("wwdg-ll", "spi-ll", "tim-ll"))
    for lid in set(by) - set(D.LADDER):
        assert (by[lid]["status"], by[lid]["priority"], by[lid]["phases"]) == ("ON_HOLD", 30, SIX)


def test_the_derived_campaign_parses_like_a_campaign_file(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(_sub(D.derived_campaign()), sort_keys=False))
    c = LCMP.parse(p, require_approval=False)
    assert [L.id for L in c.lineages] == [L["id"] for L in D.LINEAGES]
    by = {L.id: L for L in c.lineages}
    assert by["wwdg-hal"].provided_from == L29 and by["wwdg-hal"].after["lineage"] == "wwdg-ll"
