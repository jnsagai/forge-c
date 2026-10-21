"""Feature 010 LRTX-T024: campaign definition, freeze and summary arithmetic (no model run)."""
from __future__ import annotations

import json

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import campaign

CAMPAIGN = REPO_ROOT / "specs/010-local-rtx-optimization/campaign.yaml"


def test_frozen_case_mix_covers_both_peripherals_and_layers():
    c = campaign.load(CAMPAIGN)
    runs = campaign.expand(c)
    assert len(runs) == 30 and len({r["run"] for r in runs}) == 30
    assert {r["id"] for r in runs} == {"IWDG-LL", "RCC-LL", "IWDG-HAL", "RCC-HAL"}
    assert all((REPO_ROOT / r["example"] / "workorder.json").is_file() for r in runs)


def test_wilson_interval_and_summary_count_every_attempt():
    assert campaign.wilson(27, 30) == (0.744, 0.965)
    c = {"tag": "t", "cases": [{"id": "A", "example": "x", "repeat": 3}]}
    rows = [{"run": f"A-t0{i}", "package_status": s, "wall_s": 100.0, "classification": {"blocked_phase": p},
             "metrics": {"calls": {"prompt_tokens": {"sum": 1000}}, "energy": {"gpu_board_wh": 1.0}}}
            for i, (s, p) in enumerate((("READY_FOR_OFFLINE_REVIEW", None), ("BLOCKED", "SWE.1"), ("BLOCKED", "SWE.1")))]
    s = campaign.summary(c, rows, "h")
    assert s["ready"] == 1 and s["per_accepted_work_order"]["wall_s"] == 300.0
    assert s["per_accepted_work_order"]["prompt_tokens"] == 3000 and s["blocked_or_failed_by_phase"] == {
        "none": 1, "SWE.1": 2}


def test_a_changed_campaign_is_refused_for_an_existing_output(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "campaign.sha256").write_text("0" * 64)
    with pytest.raises(SystemExit, match="CAMPAIGN_CHANGED_AFTER_START"):
        campaign.main(["--campaign", str(CAMPAIGN), "--out", str(out)])
    assert json.loads(json.dumps({"ok": True}))
