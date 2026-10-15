"""Human-approved upstream inputs: used only when APPROVED with approver/date and no placeholder."""
import shutil
from pathlib import Path

import yaml
from forge_factory.upstream import UPSTREAM_FILE, load_upstream

EX = Path(__file__).resolve().parents[3] / "examples/0002-arm_55_rcc_st"


def filled(tmp_path, **over):
    d = yaml.safe_load((EX / UPSTREAM_FILE).read_text())

    def fill(n):
        if isinstance(n, dict):
            return {k: fill(v) for k, v in n.items()}
        if isinstance(n, list):
            return [fill(v) for v in n]
        return "X-1" if n == "FILL" else n
    d = fill(d) | {"status": "APPROVED"} | over
    (tmp_path / "upstream").mkdir()
    (tmp_path / UPSTREAM_FILE).write_text(yaml.safe_dump(d))
    return tmp_path


def test_shipped_template_is_not_an_approved_input():
    r = load_upstream(EX)
    assert r["status"] == "NOT_PROVIDED" and r["data"] is None
    assert "NOT_APPROVED:status=DRAFT_TEMPLATE" in r["issues"] and any(i.startswith("PLACEHOLDER:") for i in r["issues"])


def test_complete_and_approved_file_is_used(tmp_path):
    assert load_upstream(filled(tmp_path))["status"] == "APPROVED"


def test_any_placeholder_or_missing_approval_keeps_not_provided(tmp_path):
    r = load_upstream(filled(tmp_path, approval={"approved_by": "TBD", "approved_on": "2026-10-15", "review_record": "R"}))
    assert r["status"] == "NOT_PROVIDED" and "PLACEHOLDER:approval.approved_by" in r["issues"]
    shutil.rmtree(tmp_path / "upstream")
    assert load_upstream(filled(tmp_path, status="DRAFT"))["status"] == "NOT_PROVIDED"
    assert load_upstream(tmp_path / "nowhere")["issues"] == ["UPSTREAM_FILE_MISSING"]
