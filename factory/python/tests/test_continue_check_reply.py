"""CAPA-100 (run WO-F014-SWE3-IWDG-20261101-L3): the continuation check of the code (SWE.3) and tests (SWE.4-6) steps
read the inspector's reply, found nothing and sent an unfinished visit on (design FAILED: no valid code task)."""
import json

import pytest
from forge_factory.lrtx import runner


@pytest.mark.parametrize("of", ["author", "code", "tests"])
def test_an_author_side_continue_reply_continues(tmp_path, of):
    d = tmp_path / ".forge-run/lrtx/SWE.3"
    d.mkdir(parents=True)
    (d / "reply.json").write_text(json.dumps({"status": "CONTINUE"}))
    assert runner.main(["continue-check", "--phase", "SWE.3", "--workspace", str(tmp_path), "--of", of]) == 0


def test_the_inspector_continue_reply_is_read_for_inspect(tmp_path):
    d = tmp_path / ".forge-run/lrtx/SWE.3"
    d.mkdir(parents=True)
    (d / "reply.json").write_text(json.dumps({"status": "CONTINUE"}))
    (d / "inspect-reply.json").write_text(json.dumps({"status": "PASS"}))
    assert runner.main(["continue-check", "--phase", "SWE.3", "--workspace", str(tmp_path), "--of", "inspect"]) == 1
