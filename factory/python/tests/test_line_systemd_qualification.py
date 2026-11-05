"""The line drill is fenced to OBSERVE/private state before creating any OS unit."""
import pytest
from forge_factory.afo import systemd_qualification as Q


def test_line_drill_refuses_existing_state_before_any_systemd_action(tmp_path, monkeypatch):
    (tmp_path / "state").mkdir()
    monkeypatch.setattr(Q, "call", lambda *_a, **_k: pytest.fail("must refuse before systemd"))
    with pytest.raises(FileExistsError):
        Q.line_run(tmp_path)


def test_line_drill_command_cannot_place_orders_or_query_a_live_fabro(tmp_path):
    command = Q.line_command(tmp_path / "state", tmp_path / "empty-snapshot.json")
    assert command[command.index("--mode") + 1] == "OBSERVE"
    assert command[command.index("--line") + 1] == "drill"
    assert command[command.index("--fabro-snapshot") + 1] == str(tmp_path / "empty-snapshot.json")
    assert command[command.index("--launch-dir") + 1] == str(tmp_path / "state/launch")
