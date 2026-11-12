"""Executed only inside the network-blocked verifier namespace by the integration test.

A small CPU project exercises real local execution, export/replay, TEST signatures,
the portable CLI, preflight/regression, activation, rejection receipts and rollback.
Synthetic CRE control metadata here is not source qualification or a native trial.
"""
from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

from forge_factory.common import REPO_ROOT


def main():
    root = Path.cwd()
    network_namespace = os.readlink("/proc/self/ns/net")
    assert network_namespace != os.environ["FIXTURE_PARENT_NETWORK_NAMESPACE"]
    try:
        with socket.create_connection(("198.51.100.1", 443), timeout=1):
            raise AssertionError("NETWORK_ACCESS_AVAILABLE")
    except OSError as exc:
        assert exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH), exc
        network_errno = exc.errno
    repo = root / "development"
    runtime = repo / "factory/python"
    runtime.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "factory/python/forge_factory", runtime / "forge_factory",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (repo / "scripts").mkdir()
    shutil.copy2(REPO_ROOT / "scripts/forge-offline-update.py", repo / "scripts/forge-offline-update.py")
    contracts = repo / "specs/014-durable-local-autonomy/contracts"
    contracts.mkdir(parents=True)
    for name in ("patch-bundle.schema.json", "offline-export-manifest.schema.json"):
        shutil.copy2(REPO_ROOT / "specs/014-durable-local-autonomy/contracts" / name, contracts / name)
    (repo / "config/factory").mkdir(parents=True)
    policy = "security:\n  protected_path_globs:\n    - config/factory/reliability-policy.yaml\n    - evidence/**\n"
    (repo / "config/factory/reliability-policy.yaml").write_text(policy)
    (runtime / "fixture_pkg").mkdir()
    (runtime / "fixture_pkg/__init__.py").write_text("")
    (runtime / "fixture_pkg/rule.py").write_text("def answer():\n    return 41\n")
    (runtime / "fixture_pkg/unchanged.py").write_text("LIMIT = 10\n")
    (repo / "tests").mkdir()
    (repo / "tests/test_rule.py").write_text(
        "from fixture_pkg.rule import answer\n\ndef test_answer():\n    assert answer() == 42\n")
    (repo / "tests/regression_negative.py").write_text("def test_negative_control():\n    assert False\n")

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.PIPE)

    def env(runtime_root):
        return {**os.environ, "FORGE_REPO_ROOT": str(runtime_root),
                "PYTHONPATH": str(runtime_root / "factory/python"), "PYTHONDONTWRITEBYTECODE": "1",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}

    def command(runtime_root, *args, expected=0):
        result = subprocess.run([sys.executable, *map(str, args)], cwd=root, env=env(runtime_root),
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == expected, (args, result.returncode, result.stdout[-1000:], result.stderr[-1000:])
        return json.loads(result.stdout)

    git("init", "-q")
    git("config", "user.name", "TEST fixture")
    git("config", "user.email", "fixture@invalid")
    git("add", "-A")
    git("commit", "-qm", "CPU fixture base")
    base = git("rev-parse", "HEAD").decode().strip()
    baseline_archive = git("archive", base)
    install = root / "omniverse-offline"
    live = install / "releases" / base
    live.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(baseline_archive)) as archive:
        archive.extractall(live, filter="data")
    (install / "current").symlink_to(Path("releases") / base)
    pytest_args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_rule.py"]
    started = time.monotonic()
    original = subprocess.run(pytest_args, cwd=live, env=env(live), capture_output=True, text=True, timeout=60)
    assert original.returncode == 1 and "assert 41 == 42" in original.stdout
    ws = root / "local-workorder/workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(dict(work_order="WO-OFFLINE-CPU-CONTROL",
        source_revision=base, local_profile=dict(id="CPU-CONTROL"), scope="NO_NATIVE_OR_MODEL_QUALIFICATION")))
    gate = dict(phase="CPU-CONTROL", status="FAIL", exit_code=original.returncode,
                duration_s=time.monotonic()-started, output=original.stdout, model_calls=0)
    (ws / ".forge-run/gates/result.json").write_text(json.dumps(gate))
    outgoing = root / "outgoing"
    exported = command(live, "-m", "forge_factory.offline.export", "--run", ws, "--out", outgoing / "report.zip")
    reviewed = root / "external-analysis"
    reviewed.mkdir()
    for suffix in ("report.zip", "report.zip.sha256", "report.md"):
        shutil.copy2(outgoing / suffix, reviewed / suffix)
    assert command(repo, "-m", "forge_factory.offline.export", "--verify", reviewed / "report.zip")["status"] == "INTACT"
    assert '"status": "FAIL"' in (reviewed / "report.md").read_text()
    replay = subprocess.run(pytest_args, cwd=live, env=env(live), capture_output=True, text=True, timeout=60)
    assert replay.returncode == gate["exit_code"] and "assert 41 == 42" in replay.stdout
    (runtime / "fixture_pkg/rule.py").write_text("def answer():\n    return 42\n")
    git("commit", "-qam", "CPU fixture correction")
    target = git("rev-parse", "HEAD").decode().strip()
    key = root / "TEST-owner"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True,
                   capture_output=True)
    signers = root / "TEST-allowed-signers"
    signers.write_text(f'FixtureOwner namespaces="forge-patch-bundle" {key.with_suffix(".pub").read_text()}')

    def make_bundle(name, revision=target, regression="tests/test_rule.py"):
        decision = root / f"{name}-CONTROL-cre.json"
        decision.write_text(json.dumps(dict(decision_id="CONTROL-NOT-REAL-CRE-QUALIFICATION",
            decision="ELIGIBLE_FOR_OFFLINE_REVIEW", baseline_revision=base, candidate_revision=revision,
            baseline_sha256=hashlib.sha256(git("ls-tree", "-r", base)).hexdigest(),
            candidate_sha256=hashlib.sha256(git("ls-tree", "-r", revision)).hexdigest())))
        bundle = reviewed / f"{name}.zip"
        result = command(repo, "-m", "forge_factory.offline.patch", "build", "--repo", repo, "--base", base,
            "--target", revision, "--regression", regression, "--cre-decision", decision,
            "--approver", "FixtureOwner", "--out", bundle, "--runner-out", reviewed / "apply-update.py")
        command(repo, "-m", "forge_factory.offline.patch", "sign", bundle, "--key", key)
        return bundle, result

    bundle, built = make_bundle("correction")
    incoming = root / "incoming"
    incoming.mkdir()
    for path in (bundle, bundle.with_name(bundle.name + ".sig"), reviewed / "apply-update.py"):
        shutil.copy2(path, incoming / path.name)
    bundle = incoming / bundle.name
    runner = incoming / "apply-update.py"
    assert hashlib.sha256(runner.read_bytes()).hexdigest() == built["runner_sha256"]
    preflight = shlex.join([sys.executable, "-c", "from pathlib import Path; p=Path('factory/python/fixture_pkg/rule.py'); compile(p.read_bytes(),str(p),'exec')"])

    def apply(path=bundle, preflight_cmd=preflight, expected=1):
        return command(live, runner, "apply", "--install-root", install, "--bundle", path,
                       "--allowed-signers", signers, "--preflight-cmd", preflight_cmd, expected=expected)

    rejected = {}
    unsigned = incoming / "unsigned.zip"
    shutil.copy2(bundle, unsigned)
    rejected["unsigned"] = apply(unsigned)["code"]
    assert rejected["unsigned"] == "PATCH_SIGNATURE_INVALID"
    tampered = incoming / "tampered.zip"
    with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(tampered, "w") as dest:
        for name in source.namelist():
            dest.writestr(name, b"def answer():\n    return 0\n" if name.endswith("/rule.py") else source.read(name))
    shutil.copy2(bundle.with_name(bundle.name + ".sig"), tampered.with_name(tampered.name + ".sig"))
    rejected["tampered"] = apply(tampered)["code"]
    assert rejected["tampered"] == "PATCH_HASH_MISMATCH"
    unchanged = live / "factory/python/fixture_pkg/unchanged.py"
    unchanged.write_text("LIMIT = 999\n")
    rejected["local_drift"] = apply()["code"]
    assert rejected["local_drift"] == "PATCH_BASE_DRIFT"
    unchanged.write_text("LIMIT = 10\n")
    rejected["preflight"] = apply(preflight_cmd=shlex.join([sys.executable, "-c", "raise SystemExit(7)"]))["code"]
    assert rejected["preflight"] == "PATCH_CHECKS_FAILED"
    failing, _ = make_bundle("failing-regression", regression="tests/regression_negative.py")
    rejected["regression"] = apply(failing)["code"]
    assert rejected["regression"] == "PATCH_CHECKS_FAILED"
    (repo / "config/factory/reliability-policy.yaml").write_text(policy.replace("evidence/**", "nothing/**"))
    git("commit", "-qam", "protected negative control")
    protected, _ = make_bundle("protected", revision=git("rev-parse", "HEAD").decode().strip())
    rejected["protected"] = apply(protected)["code"]
    assert rejected["protected"] == "PATCH_PROTECTED_PATH"
    accepted = apply(expected=0)
    assert accepted["decision"] == "ACTIVATED" and accepted["current"] == target
    assert all(check["exit_code"] == 0 for check in accepted["checks"])
    assert (install / "current/factory/python/fixture_pkg/unchanged.py").read_text() == "LIMIT = 10\n"
    rejected["wrong_base"] = apply()["code"]
    assert rejected["wrong_base"] == "PATCH_BASE_MISMATCH"
    rolled = command(install / "current", runner, "rollback", "--install-root", install)
    assert rolled["decision"] == "ROLLED_BACK" and rolled["current"] == base
    assert (install / "current/factory/python/fixture_pkg/rule.py").read_text().endswith("return 41\n")
    records = [json.loads(line) for line in (install / "imports/log.jsonl").read_text().splitlines()]
    assert len(records) == len(rejected) + 2
    assert not any(path.name.startswith(".staging") for path in (install / "releases").iterdir())
    print(json.dumps(dict(scope="CPU_CONTROL_NOT_NATIVE_FACTORY_ACCEPTANCE", network_namespace=network_namespace,
        network_errno=network_errno, model_calls=0, original_gate="FAIL", replay_gate="FAIL",
        exported_sha256=exported["sha256"], runner_sha256=built["runner_sha256"],
        rejected=rejected, activation=accepted["code"], rollback=rolled["code"], receipts=len(records))))


if __name__ == "__main__":
    main()
