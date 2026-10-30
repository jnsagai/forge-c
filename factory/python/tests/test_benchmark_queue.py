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
    ids = ["crc-st", "spi-st", "usart-st", "gpio-st", "tim-st"]
    assert [i["id"] for i in q["items"]] == ids + [f"{x}-hal" for x in ids]  # F015-T065: ST HAL after the LL items
    assert all(i["layer"] == ("HAL" if i["id"].endswith("-hal") else "LL") for i in q["items"])
    assert Q.LINE[:4] == ["--acp-authors", "codex", "--acp-inspectors", "claude"]
    from forge_factory.afo.runtime import PROFILES

    assert Q.LINE[4:] == ["--model", PROFILES["codex-claude"]["model"], "--provider", PROFILES["codex-claude"]["provider"]]


def test_items_run_in_order_skip_missing_examples_and_record_outcomes(env):
    q = Q.load()
    launched = []

    def launcher(example, wo):
        launched.append(wo)
        ws = env / wo / "workspace"
        _finish(ws, "READY_FOR_OFFLINE_REVIEW", list(Q.PHASES))
        return {"fabro_run_id": "R" + wo, "workspace": str(ws)}

    q["items"].append({"id": "later-st", "example": "examples/0099c-not-onboarded"})  # a peripheral not onboarded
    onboarded = [i for i in q["items"] if (Q.REPO_ROOT / i["example"] / "workorder.json").is_file()]
    assert [i["id"] for i in onboarded][:6] == ["crc-st", "spi-st", "usart-st", "gpio-st", "tim-st", "crc-st-hal"]
    st = Q.run(q, launcher=launcher, sleep=lambda s: None)
    assert launched == [Q.work_order_id(q, i, 1) for i in onboarded]  # queue order, one at a time
    assert st["items"]["crc-st"]["status"] == "READY_FOR_OFFLINE_REVIEW"
    assert st["items"]["later-st"]["status"] == "SKIPPED_NOT_ONBOARDED"
    out = st["items"]["crc-st"]["attempts"][0]["outcome"]
    assert out["phases_passed"] == list(Q.PHASES) and out["blocked_at"] is None
    n = len(launched)
    assert Q.run(q, launcher=launcher, sleep=lambda s: None) and len(launched) == n  # recorded outcomes: skipped


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


def test_a_launched_attempt_without_outcome_is_reported_never_launched_again(env):
    """A runner stopped while its run may still be live: no second attempt without an explicit retry."""
    q = Q.load()
    st = {"queue": q["id"], "items": {"crc-st": {"status": "RUNNING", "attempts": [
        {"work_order": "WO-BENCH-CRC-ST-r1", "started_at": "2026-10-25T09:00:00Z", "fabro_run_id": "R1"}]}}}
    Q.write_state(q, st)
    launched = []

    def launcher(example, wo):
        launched.append(wo)
        raise RuntimeError("LAUNCH_FAILED:not expected")

    st = Q.run(q, only="crc-st", launcher=launcher, sleep=lambda s: None)
    assert launched == [] and st["items"]["crc-st"]["status"] == "UNFINISHED_ATTEMPT"
    st = Q.run(q, only="crc-st", retry="crc-st", launcher=launcher, sleep=lambda s: None)
    assert launched == ["WO-BENCH-CRC-ST-r2"]  # explicit retry: a new recorded identity


def test_every_benchmark_work_order_has_the_rm0486_register_conventions_input():
    """WO-AFO-0756ac55b8ea81e6-a1 (SPI) stopped STUCK at SWE.4 on three escalated CODE defects: host tests preset the
    write-only SPI_IFCR with other bits and ST's SET_BIT kept them. RM0486 1.2 (p.156): reading a write-only (w) bit
    returns the reset value, so on the device ST's code writes exactly the flag; the convention was not an input."""
    q = Q.load()
    for item in q["items"]:
        if not (Q.REPO_ROOT / item["example"] / "workorder.json").is_file():
            continue  # an item not onboarded yet (F015-T065 HAL items follow one by one)
        spec = json.loads((Q.REPO_ROOT / item["example"] / "workorder.json").read_text())
        roles = {i["role"]: i["path"] for i in spec["inputs"]}
        assert roles["reference_manual_register_conventions"].endswith("RM0486-rev4-register-conventions.md"), item
    from forge_factory import peripheral

    for pid, reg in (("spi", "SPI_IFCR"), ("usart", "USART_ICR"), ("gpio", "GPIO_BSRR"), ("tim", "TIM_EGR")):
        pr = peripheral.load(pid)["prompt"]
        assert reg in pr["ut_rule"] and "RM0486 1.2" in pr["ut_rule"] and "RM0486 1.2" in pr["swe1_cover"], pid
