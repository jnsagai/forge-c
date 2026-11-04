"""A real fresh interpreter can report missing application volume from committed host code alone."""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

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


@pytest.fixture
def packaged_recovery(tmp_path):
    """Real zip + native dependency tree; no installed site-packages or application Python."""
    import shutil

    data = tmp_path / "application"
    host = tmp_path / "host/watchdog.zip"
    artifact = build(host, application_data=data)
    # The authoritative policy/schema remain separate data, never code-archive contents.
    policy = tmp_path / "authoritative-policy"
    for relative in ("config/factory/reliability-policy.yaml", "config/factory/supervisor-policy.yaml",
                     "specs/004-continuous-reliability-engineering/contracts/reliability-policy.schema.json"):
        destination = policy / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, destination)
    control = tmp_path / "private-control"
    control.mkdir(mode=0o700)
    intent = control / "operations.json"
    intent.write_text(json.dumps({"mode": "RUNNING", "epoch": 1}))
    intent.chmod(0o600)
    effect = control / "unexpected-service-effect"
    script = control / "probe.py"
    script.write_text("""
import json, sys
from pathlib import Path
from forge_factory.afo.line_watchdog import recover, check
intent=Path(sys.argv[1]); effect=Path(sys.argv[2])
def runner(argv):
    effect.write_text(json.dumps(argv))
    raise AssertionError('SERVICE_EFFECT_NOT_ALLOWED')
state={'ActiveState':'active','MainPID':'12','UnitFileState':'enabled','Result':'success'}
if sys.argv[3]=='healthy':
    heartbeat=intent.with_name('heartbeat.json')
    heartbeat.write_text(json.dumps({'pid':12,'epoch':1000,'ok':True,'mode':'PILOT'}))
    health=check(now=1030, heartbeat=heartbeat, probe=lambda:state)
    assert health['code']=='HEALTHY'
# Default operational_authorized loads the real unweakened policy + JSON Schema.
report=recover(intent, ready=lambda:{'ok':sys.argv[3]!='no-volume'}, probe=lambda:state, runner=runner)
print(json.dumps(report))
""")
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": artifact["pythonpath"], "PYTHONDONTWRITEBYTECODE": "1",
           "FORGE_REPO_ROOT": str(policy), "FORGE_DATA_ROOT": str(data), "FORGE_STATE_DIR": str(data / "state")}

    def run(mode="normal"):
        return subprocess.run([sys.executable, "-S", str(script), str(intent), str(effect), mode],
                              cwd=control, env=env, capture_output=True, text=True, timeout=30)

    return artifact, intent, effect, run


def test_real_bare_interpreter_recovery_loads_default_policy_and_schema_without_effect(packaged_recovery):
    artifact, intent, effect, run = packaged_recovery
    original = intent.read_bytes()
    for mode in ("normal", "healthy", "normal"):
        report = run(mode)
        assert report.returncode == 0, report.stderr
        assert json.loads(report.stdout)["action"] == "WAITING_FOR_PREAUTHORIZED_OPERATIONAL_RECIPE"
    assert not effect.exists()
    assert intent.read_bytes() == original
    assert not list(Path(artifact["dependency_path"]).rglob("__pycache__"))


def test_bare_recovery_refuses_missing_volume_and_intent_even_without_dependency_tree(packaged_recovery):
    import shutil

    artifact, intent, effect, run = packaged_recovery
    shutil.rmtree(artifact["dependency_path"])
    report = run("no-volume")
    assert report.returncode == 0, report.stderr
    assert json.loads(report.stdout)["action"] == "WAITING_FOR_AUTHORITATIVE_VOLUME"
    intent.unlink()
    report = run()
    assert report.returncode == 0, report.stderr
    assert json.loads(report.stdout)["action"] == "WAITING_FOR_AUTHENTICATED_OPERATIONS_INTENT"
    assert not effect.exists()


@pytest.mark.parametrize("damage,expected", [
    ("missing", "INVENTORY_CHANGED"), ("changed", "FILE_CHANGED"),
    ("symlink", "SYMLINK"), ("manifest", "MANIFEST_CHANGED"), ("tree-symlink", "TREE_MISSING_OR_SYMLINK"),
])
def test_bare_recovery_refuses_damaged_dependencies_before_policy_or_effect(packaged_recovery, damage, expected):
    artifact, intent, effect, run = packaged_recovery
    root = Path(artifact["dependency_path"])
    file = root / "yaml/__init__.py"
    original = intent.read_bytes()
    if damage == "missing":
        file.unlink()
    elif damage == "changed":
        file.chmod(0o600)
        file.write_bytes(file.read_bytes() + b"\n# tampered\n")
    elif damage == "symlink":
        target = root.parent / "yaml-original.py"
        file.rename(target)
        file.symlink_to(target)
    elif damage == "manifest":
        manifest = root / "watchdog-dependencies-manifest.json"
        manifest.chmod(0o600)
        manifest.write_bytes(manifest.read_bytes() + b" ")
    else:
        target = root.with_name("relocated-dependencies")
        root.rename(target)
        root.symlink_to(target, target_is_directory=True)
    report = run()
    assert report.returncode != 0
    assert "WATCHDOG_DEPENDENCY_" + expected in report.stderr
    assert not effect.exists()
    assert intent.read_bytes() == original


def test_bare_recovery_rejects_integrity_bound_but_wrong_native_abi(packaged_recovery):
    import hashlib

    from forge_factory.common import canonical_json

    artifact, intent, effect, run = packaged_recovery
    manifest_path = Path(artifact["dependency_path"]) / "watchdog-dependencies-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["interpreter"]["soabi"] = "other-python-native-abi"
    raw = canonical_json(manifest) + b"\n"
    manifest_path.chmod(0o600)
    manifest_path.write_bytes(raw)
    archive = Path(artifact["archive"])
    with zipfile.ZipFile(archive) as original:
        files = {info.filename: (info, original.read(info)) for info in original.infolist()}
    info, code = files["watchdog-code-manifest.json"]
    code_manifest = json.loads(code)
    code_manifest["dependencies_manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    files[info.filename] = info, canonical_json(code_manifest) + b"\n"
    replacement = archive.with_name("wrong-abi.zip")
    with zipfile.ZipFile(replacement, "w") as result:
        for info, body in files.values():
            result.writestr(info, body)
    replacement.replace(archive)
    before = intent.read_bytes()
    report = run()
    assert report.returncode != 0
    assert "WATCHDOG_DEPENDENCY_INTERPRETER_ABI_MISMATCH" in report.stderr
    assert not effect.exists()
    assert intent.read_bytes() == before


def test_default_active_policy_still_cannot_start_healthy_unit(packaged_recovery):
    import yaml

    artifact, intent, effect, run = packaged_recovery
    # A private test policy passes the normal schema/invariant loader. No authorize callback is used.
    control = intent.parent
    policy_path = control.parent / "authoritative-policy/config/factory/reliability-policy.yaml"
    policy = yaml.safe_load(policy_path.read_text())
    policy["mode"] = "ACTIVE"
    policy["authorization"] = {"runbook_ref": "private-test-runbook", "approved_by": "test-owner",
                               "approved_on": "2026-11-04"}
    policy["promotion"]["allowed_automatic_operational_actions"] = ["restart_conductor"]
    policy_path.write_text(yaml.safe_dump(policy))
    report = run("healthy")
    assert report.returncode == 0, report.stderr
    assert json.loads(report.stdout)["action"] == "NO_APPROVED_RECOVERY"
    assert not effect.exists()
