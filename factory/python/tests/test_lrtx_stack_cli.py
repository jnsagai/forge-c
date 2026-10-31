"""Exercise the CLI used by rendered systemd units and host API exposure."""
import pytest

from forge_factory.lrtx import stack


@pytest.mark.parametrize("header", [
    ["exec", "--profile", "local-test"],
    ["--profile", "local-test", "exec"],
])
def test_exec_parses_stack_options_and_preserves_worker_arguments(monkeypatch, header):
    selected = []
    command = []
    monkeypatch.setattr(stack, "settings", lambda name: selected.append(name) or {})
    monkeypatch.setattr(stack, "exec_in", lambda config, argv: command.extend(argv) or 0)
    worker = ["python", "-m", "worker", "--profile", "worker-only", "--host-port", "9999"]
    assert stack.main(header + ["--"] + worker) == 0
    assert selected == ["local-test"]
    assert command == worker


def test_expose_api_honors_host_port_after_command(monkeypatch):
    selected = []
    exposed = []
    monkeypatch.setattr(stack, "settings", lambda name: selected.append(name) or {})
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(stack, "expose_api", lambda config, port: exposed.append(port) or {})
    assert stack.main(["expose-api", "--profile", "local-test", "--host-port", "32491"]) == 0
    assert selected == ["local-test"]
    assert exposed == [32491]


def test_non_exec_does_not_ignore_unknown_arguments(monkeypatch):
    monkeypatch.setattr(stack, "settings", lambda name: pytest.fail("invalid arguments reached settings"))
    with pytest.raises(SystemExit) as error:
        stack.main(["status", "--unexpected"])
    assert error.value.code == 2
