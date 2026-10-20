"""OD-2026-10-20-07: an owner disposition (verification-dispositions.yaml, delivered_finding_regex) settles exactly the
delivered-code findings it names; they leave the package gaps and are stated as limitations. Others stay gaps."""
import json

from forge_factory.brownfield import package as BP
from forge_factory.inspection.defects import DISPOSITIONS
from forge_factory.workorder import owner_dispositions_for

FINDINGS = [f"GUIDELINE:GL-ARG-01:software/ll/stm32n6xx_ll_bus.h:{n}" for n in (879, 897, 911, 925, 939)] + \
    ["GUIDELINE:GL-ARG-01:software/ll/stm32n6xx_ll_bus.h:1000", "GUIDELINE:GL-CONST-01:software/ll/stm32n6xx_ll_rcc.h:10"]


def _ws(tmp_path, ods):
    (tmp_path / ".forge-run/delivery").mkdir(parents=True)
    (tmp_path / ".forge-run/delivery/code_findings.json").write_text(json.dumps({"code_checks": {"findings": FINDINGS}}))
    (tmp_path / DISPOSITIONS).write_text(json.dumps(ods))
    return tmp_path


def test_owner_disposition_settles_exactly_the_named_findings(tmp_path):
    ods = owner_dispositions_for("0008c-st-cube-rcc")
    assert [d["id"] for d in ods] == ["OD-2026-10-20-07"]
    ws = _ws(tmp_path, ods)
    settled = [f for f in FINDINGS if BP.disposition_of(ws, f)]
    assert settled == FINDINGS[:5]
    lines = BP.dispositioned(ws)
    assert len(lines) == 5 and all("OD-2026-10-20-07" in x and "Jefferson Nascimento" in x for x in lines)


def test_no_disposition_for_other_examples(tmp_path):
    ws = _ws(tmp_path, owner_dispositions_for("0002a-arm_55_rcc_ll"))
    assert not any(BP.disposition_of(ws, f) for f in FINDINGS) and BP.dispositioned(ws) == []
