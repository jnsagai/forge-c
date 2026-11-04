"""A real fresh interpreter can report missing application volume from committed host code alone."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from forge_factory.afo.line_watchdog_package import build
from forge_factory.common import REPO_ROOT


def test_archive_is_repeatable_and_contains_no_policy_state_or_credentials(tmp_path):
    data = tmp_path / "application-volume"
    p = tmp_path / "host/watchdog.zip"
    result = build(p, application_data=data)
    assert build(p, application_data=data) == result
    with zipfile.ZipFile(p) as archive:
        names = archive.namelist()
        assert all(name.startswith("forge_factory/") and name.endswith(".py") or name == "watchdog-code-manifest.json"
                   for name in names)
        manifest = json.loads(archive.read("watchdog-code-manifest.json"))
        assert result["source_revision"] == manifest["source_revision"]
        assert result["source_files"] == len(manifest["files"])
    with pytest.raises(ValueError, match="OUTSIDE_APPLICATION_VOLUME"):
        build(data / "watchdog.zip", application_data=data)


def test_real_host_check_executes_without_application_repo_volume_or_venv(tmp_path):
    data = tmp_path / "application-volume-is-missing"
    archive = tmp_path / "host/watchdog.zip"
    build(archive, application_data=data)
    control = tmp_path / "private-control"
    control.mkdir(mode=0o700)
    intent = control / "operations.json"
    intent.write_text(json.dumps({"mode": "RUNNING", "epoch": 1}))
    intent.chmod(0o600)
    env = {**os.environ, "PYTHONPATH": str(archive), "FORGE_REPO_ROOT": str(data / "repo"),
           "FORGE_DATA_ROOT": str(data), "FORGE_STATE_DIR": str(data / "state")}
    result = subprocess.run([sys.executable, "-S", "-m", "forge_factory.afo.line_watchdog", "recover",
                             "--intent", str(intent)], cwd=control, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stderr  # unhealthy is reported as failure, never a success heartbeat
    report = json.loads(result.stdout)
    assert report["recovery"]["action"] == "WAITING_FOR_AUTHORITATIVE_VOLUME"
    assert not data.exists()
    assert json.loads(intent.read_text()) == {"mode": "RUNNING", "epoch": 1}


def test_external_service_template_does_not_depend_on_application_mount():
    template = (REPO_ROOT / "deploy/systemd/afo/forge-line-watchdog-local.service.in").read_text()
    assert "\nRequiresMountsFor=" not in template
    assert "ExecStart=@WATCHDOG_PYTHON@" in template
    assert "Environment=PYTHONPATH=@WATCHDOG_CODE@" in template
