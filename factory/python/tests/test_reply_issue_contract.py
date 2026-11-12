"""CAPA-098 (runs WO-F014-SWE2-IWDG-20261101-01, WO-F014-SWE4-IWDG-20261101-L1): structured replies cut issues to 300
characters while the protected agent-output contract allows 120, so every long rejection also failed AGENT_OUTPUT_SCHEMA
and the gate kept 120-character fragments. The reply keeps the contract; rework reads the full text."""
import json

from forge_factory.contracts.agent_output import parse
from forge_factory.lrtx import visit as V

LONG = "test:UT-002: call to LL_crc_Read_IDR: a test calls only ut_reset_regs, CHECK and LL_CRC_Read_IDR " + "x" * 150


def test_a_long_issue_keeps_the_contract_and_rework_reads_its_full_text(tmp_path):
    ws = tmp_path
    (ws / ".forge-run/gates").mkdir(parents=True)
    doc = V.reply(ws, "SWE.4", "FAILED", [LONG, "short issue"])
    res = parse(json.dumps(doc))
    assert res.ok and res.errors == [] and res.issues[0] == LONG[:120]
    (ws / ".forge-run/gates/gate-log.jsonl").write_text(json.dumps(
        {"phase": "SWE.4", "step": "author", "result": "REJECTED", "ts": "2026-11-01T22:00:00Z",
         "issues": res.issues}) + "\n")
    assert V.rework_findings(ws, "SWE.4", "2026-11-01T21:00:00Z")[:2] == [LONG, "short issue"]
