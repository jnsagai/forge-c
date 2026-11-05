"""DA-T046/050 CONTROL: line deployment rendering and public startup fences.

No installed unit, model, grant or production state is used by these controls.
"""
import json
from pathlib import Path

import pytest
from forge_factory.afo import line_conductor, operations, services


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("FORGE_VENV", str(tmp_path / "venv"))
    launch = tmp_path / "line"
    return dict(intent=tmp_path / "private/intent.json", launch_dir=launch,
                watchdog_code=tmp_path / "host/watchdog.zip", watchdog_dependencies=tmp_path / "host/deps",
                watchdog_python=Path("/usr/bin/python3"))


def test_line_renderer_selects_only_its_existing_three_units(deployment):
    units = services.render_line(**deployment)
    assert set(units) == {"forge-line-conductor-local.service", "forge-line-watchdog-local.service",
                          "forge-line-watchdog-local.timer"}
    conductor = units["forge-line-conductor-local.service"]
    assert "--mode OBSERVE" in conductor and "--line local" in conductor
    assert "Restart=always" in conductor and "RestartPreventExitStatus=77" in conductor
    assert "StartLimitIntervalSec=600" in conductor and "StartLimitBurst=10" in conductor
    assert "forge_factory.afo.host preflight" in conductor
    assert "ExecCondition=" not in conductor  # skipped/inactive would prevent the existing failed-unit recovery.
    assert "CPUWeight=1000" in conductor and "IOWeight=1000" in conductor and "MemoryLow=256M" in conductor
    assert "FORGE_CONDUCTOR_UNIT=forge-line-conductor-local.service" in conductor
    assert "FORGE_OPERATIONS_INTENT=" + str(deployment["intent"]) in conductor
    assert "FORGE_STATE_DIR=" + str(deployment["launch_dir"] / "lrtx/state") in conductor
    watchdog = units["forge-line-watchdog-local.service"]
    assert "--intent " + str(deployment["intent"]) in watchdog
    assert "RequiresMountsFor=" not in watchdog and "OnBootSec=5min" in units["forge-line-watchdog-local.timer"]
    assert not any("@" in line for text in units.values() for line in text.splitlines() if not line.startswith("#"))


def test_line_act_render_does_not_invent_authorization(deployment):
    text = services.render_line(mode="ACT", **deployment)["forge-line-conductor-local.service"]
    assert "--mode ACT" in text
    assert "FORGE_OWNER_DEVELOPMENT" not in text and "AUTH_OK" not in text


@pytest.mark.parametrize("field,value", [("intent", Path("relative")), ("watchdog_code", Path("/tmp/a\nExecStart=/bin/true")),
                                        ("launch_dir", Path("/tmp/%u")), ("mode", "OWNER_SUPERVISED_DEVELOPMENT")])
def test_line_renderer_rejects_ambiguous_or_injected_configuration(deployment, field, value):
    with pytest.raises(ValueError):
        services.render_line(**(deployment | {field: value}))


@pytest.mark.parametrize("mode", ["STOPPED", "UNKNOWN"])
def test_public_line_startup_fences_before_fabro_state_or_model_access(tmp_path, monkeypatch, mode):
    path = tmp_path / "private/intent.json"
    path.parent.mkdir(mode=0o700)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(path))
    if mode != "UNKNOWN":
        operations.Intent(path).set(mode, actor="CONTROL", reason="CONTROL", initialize=True)
    monkeypatch.setattr(line_conductor.FabroView, "from_env", lambda *_: pytest.fail("fenced before any Fabro lookup"))
    assert line_conductor.main(["--mode", "OBSERVE", "--once"]) == 77
    assert not (tmp_path / "state").exists()


def test_unknown_after_running_is_fenced_at_the_next_start(tmp_path, monkeypatch):
    path = tmp_path / "private/intent.json"
    path.parent.mkdir(mode=0o700)
    intent = operations.Intent(path)
    intent.set("RUNNING", actor="CONTROL", reason="CONTROL", initialize=True)
    path.write_text("{corrupt")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(path))
    monkeypatch.setattr(line_conductor.FabroView, "from_env", lambda *_: pytest.fail("unknown cannot start"))
    assert line_conductor.main(["--mode", "ACT", "--once"]) == 77


def test_legacy_observe_without_configured_intent_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({}))
    monkeypatch.setattr(line_conductor, "install_guard", lambda *_: None)
    monkeypatch.setattr(line_conductor, "run", lambda *_: 0)
    assert line_conductor.main(["--mode", "OBSERVE", "--fabro-snapshot", str(snapshot)]) == 0


@pytest.mark.parametrize("mode", ["RUNNING", "PAUSED", "DRAINING"])
def test_authenticated_nonstopped_intent_can_start_model_free_observer(tmp_path, monkeypatch, mode):
    path = tmp_path / "private/intent.json"
    path.parent.mkdir(mode=0o700)
    operations.Intent(path).set(mode, actor="CONTROL", reason="CONTROL", initialize=True)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(path))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("{}")
    monkeypatch.setattr(line_conductor, "install_guard", lambda *_: None)
    monkeypatch.setattr(line_conductor, "run", lambda *_: 0)
    before = path.read_bytes()
    assert line_conductor.main(["--mode", "OBSERVE", "--fabro-snapshot", str(snapshot)]) == 0
    assert path.read_bytes() == before  # boot does not initialize/rewrite Intent, resume, or grant any work.


def test_relative_configured_intent_refuses_before_lookup(monkeypatch):
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", "relative.json")
    monkeypatch.setattr(line_conductor.FabroView, "from_env", lambda *_: pytest.fail("relative Intent"))
    assert line_conductor.main(["--once"]) == 77


@pytest.mark.parametrize("field", ["intent", "watchdog_code", "watchdog_dependencies", "watchdog_python"])
def test_watchdog_and_control_must_survive_application_volume_loss(deployment, monkeypatch, field):
    root = deployment["launch_dir"].parent / "data"
    monkeypatch.setenv("FORGE_DATA_ROOT", str(root))
    with pytest.raises(ValueError, match="LINE_HOST_PATH_ON_APPLICATION_VOLUME"):
        services.render_line(**(deployment | {field: root / field}))


def test_symlink_alias_into_application_volume_is_not_host_survivable(deployment, tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setenv("FORGE_DATA_ROOT", str(root))
    with pytest.raises(ValueError, match="LINE_HOST_PATH_ON_APPLICATION_VOLUME"):
        services.render_line(**(deployment | {"watchdog_code": alias / "archive.zip"}))


@pytest.mark.parametrize("url", ["http://127.0.0.1:65536", "http://127.0.0.1:0", "http://localhost:80\nExecStart=true"])
def test_renderer_refuses_invalid_endpoint_or_directive_injection(deployment, url):
    with pytest.raises(ValueError, match="LINE_DEPLOYMENT_FABRO_URL_INVALID"):
        services.render_line(**deployment, fabro_url=url)


def test_line_cli_renders_only_never_installs_or_starts(deployment, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(services.subprocess, "run", lambda *_a, **_k: pytest.fail("render must have zero service effects"))
    out = tmp_path / "units"
    argv = ["render-line", "--out", str(out)]
    for key, value in deployment.items():
        argv.extend(["--" + key.replace("_", "-"), str(value)])
    assert services.main(argv) == 0
    assert set(json.loads(capsys.readouterr().out)) == set(services.render_line(**deployment))
    assert {p.name: p.read_text() for p in out.iterdir()} == services.render_line(**deployment)


def test_line_cli_cannot_use_generic_installer_or_enable(deployment):
    argv = ["render-line", "--enable", "forge-line-conductor-local.service"]
    for key, value in deployment.items():
        argv.extend(["--" + key.replace("_", "-"), str(value)])
    with pytest.raises(SystemExit) as error:
        services.main(argv)
    assert error.value.code == 2


def test_line_render_keeps_generic_unit_set_and_legacy_render_unchanged(deployment, monkeypatch):
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    generic = services.render()
    services.render_line(**deployment)
    assert services.render() == generic
    assert set(generic) == set(services.UNITS)


def test_line_render_is_accepted_by_real_systemd_analyzer(deployment, monkeypatch):
    import sys

    monkeypatch.setenv("FORGE_VENV", str(Path(sys.executable).parent.parent))
    result = services.verify(services.render_line(**deployment))
    assert result["ok"], result["messages"]
