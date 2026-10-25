"""Feature 015 (F015-T002, FR-004..FR-006): the ST-code benchmark queue runs one work order at a time in queue order,
skips peripherals not onboarded and items with a recorded outcome, and records outcomes from the evidence only."""
import json

import pytest
from forge_factory.benchmark import queue as Q


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


def _finish(ws, status, passed, blocked=None):
    (ws / ".forge-run/gates").mkdir(parents=True)
    rows = [{"phase": p, "step": "inspect", "gate": {"decision": "PASS"}} for p in passed]
    if blocked:
        rows.append({"phase": blocked, "step": "route", "gate": {"decision": "BLOCKED"}})
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (ws / ".forge-run/package.json").write_text(json.dumps({"package_status": status, "gap_count": 0 if passed else 9,
                                                            "finalized_at": "2026-10-25T12:00:00Z"}))


def test_the_repository_queue_lists_the_five_st_ll_items_in_order():
    q = Q.load()
    assert [i["id"] for i in q["items"]] == ["crc-st", "spi-st", "usart-st", "gpio-st", "tim-st"]
    assert Q.LINE[:4] == ["--acp-authors", "codex", "--acp-inspectors", "claude"]


def test_items_run_in_order_skip_missing_examples_and_record_outcomes(env):
    q = Q.load()
    launched = []

    def launcher(example, wo):
        launched.append(wo)
        ws = env / wo / "workspace"
        _finish(ws, "READY_FOR_OFFLINE_REVIEW", list(Q.PHASES))
        return {"fabro_run_id": "R" + wo, "workspace": str(ws)}

    st = Q.run(q, launcher=launcher, sleep=lambda s: None)
    assert launched == ["WO-BENCH-CRC-ST-r1"]  # only CRC is onboarded
    assert st["items"]["crc-st"]["status"] == "READY_FOR_OFFLINE_REVIEW"
    assert st["items"]["spi-st"]["status"] == "SKIPPED_NOT_ONBOARDED"
    out = st["items"]["crc-st"]["attempts"][0]["outcome"]
    assert out["phases_passed"] == list(Q.PHASES) and out["blocked_at"] is None
    assert Q.run(q, launcher=launcher, sleep=lambda s: None) and launched == ["WO-BENCH-CRC-ST-r1"]  # recorded: skipped


def test_a_retry_gets_a_new_work_order_id_and_a_blocked_outcome_is_kept(env):
    q = Q.load()

    def blocked(example, wo):
        ws = env / wo / "workspace"
        _finish(ws, "BLOCKED", ["SWE.1", "SWE.2"], blocked="SWE.3")
        return {"fabro_run_id": "R", "workspace": str(ws)}

    st = Q.run(q, only="crc-st", launcher=blocked, sleep=lambda s: None)
    assert st["items"]["crc-st"]["attempts"][0]["outcome"]["blocked_at"] == "SWE.3"
    st = Q.run(q, only="crc-st", retry="crc-st", launcher=blocked, sleep=lambda s: None)
    assert [a["work_order"] for a in st["items"]["crc-st"]["attempts"]] == ["WO-BENCH-CRC-ST-r1", "WO-BENCH-CRC-ST-r2"]


def test_a_failed_launch_is_recorded_not_retried(env):
    q = Q.load()

    def broken(example, wo):
        raise RuntimeError("LAUNCH_FAILED:x")

    st = Q.run(q, only="crc-st", launcher=broken, sleep=lambda s: None)
    assert st["items"]["crc-st"]["status"] == "LAUNCH_FAILED" and "launch_error" in st["items"]["crc-st"]["attempts"][0]
