"""RPR-169: a host watchdog archive cannot execute normal recovery without application-site dependencies.

The committed fixture contains byte-identical evaluated Python sources. A private Git mirror makes the
existing public archive builder usable inside the verifier without exposing the owner's Git object store.
This exercises dependency completeness, not a physical-volume fault or permission to restart a service.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SIG = "standalone host watchdog recovery cannot load its normal policy dependencies"

PROBE = r'''
import json,sys
from pathlib import Path
from forge_factory.afo.line_watchdog import recover
root=Path(sys.argv[1]);root.mkdir(mode=0o700)
intent=root/'intent.json';intent.write_text(json.dumps({'mode':'RUNNING','epoch':1}));intent.chmod(0o600)
before=intent.read_bytes()
def runner(argv):
    (root/'unexpected-effect.json').write_text(json.dumps(argv))
    raise AssertionError('UNEXPECTED_SERVICE_EFFECT')
result=recover(intent,ready=lambda:{'ok':True},probe=lambda:{'ActiveState':'active','MainPID':'4242','UnitFileState':'enabled','Result':'success'},runner=runner)
assert result['action'] in ('WAITING_FOR_PREAUTHORIZED_OPERATIONAL_RECIPE','NO_APPROVED_RECOVERY'),result
assert intent.read_bytes()==before
assert not (root/'unexpected-effect.json').exists()
print(json.dumps({'action':result['action'],'intent_unchanged':True,'service_effects':[]}))
'''


def git(repo: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-11-04T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-11-04T00:00:00Z", "GIT_TERMINAL_PROMPT": "0"}
    subprocess.run(["git", "-c", "user.name=RPR169", "-c", "user.email=rpr169@invalid",
                    "-c", "commit.gpgsign=false", *args], cwd=repo, env=env,
                   check=True, capture_output=True, timeout=60)


def main() -> int:
    from forge_factory.afo.line_watchdog_package import build
    from forge_factory.common import REPO_ROOT

    with tempfile.TemporaryDirectory(prefix="rpr169-") as temporary:
        root = Path(temporary)
        mirror = root / "source"
        mirror.mkdir()
        source = REPO_ROOT / "factory/python/forge_factory"
        count = 0
        for path in sorted(source.rglob("*.py")):
            assert path.is_file() and not path.is_symlink()
            target = mirror / path.relative_to(REPO_ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
            count += 1
        assert count > 20
        for name in ("pyproject.toml", "uv.lock", "requirements.lock", "requirements/forge-factory.lock"):
            original = REPO_ROOT / name
            if original.is_file():
                target = mirror / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
        git(mirror, "init", "--quiet")
        git(mirror, "add", ".")
        git(mirror, "commit", "--quiet", "-m", "Byte-identical evaluated source fixture")
        artifact = build(root / "host/watchdog.zip", repo=mirror,
                         application_data=root / "application-volume")
        probe = root / "probe.py"
        probe.write_text(PROBE)
        control = root / "private-control"
        env = {**os.environ, "PYTHONPATH": artifact.get("pythonpath", artifact["archive"]),
               "FORGE_REPO_ROOT": str(REPO_ROOT),
               "FORGE_CRE_POLICY": str(REPO_ROOT / "config/factory/reliability-policy.yaml"),
               "FORGE_STATE_DIR": str(root / "application-state"),
               "FORGE_EVENTS_DIR": str(root / "application-state/events")}
        result = subprocess.run([sys.executable, "-S", str(probe), str(control)], cwd=root,
                                env=env, capture_output=True, text=True, timeout=90)
        if (control / "unexpected-effect.json").exists():
            raise AssertionError("RUNNER_WAS_CALLED")
        if result.returncode:
            dependencies = ("yaml", "jsonschema", "attr", "attrs", "referencing", "rpds",
                            "jsonschema_specifications", "typing_extensions")
            if "ModuleNotFoundError" in result.stderr and any(
                    "No module named '" + name in result.stderr for name in dependencies):
                print("SYMPTOM_PRESENT:" + SIG)
                return 1
            raise RuntimeError("NORMAL_RECOVERY_ERROR:" + result.stderr[-600:])
        data = json.loads(result.stdout.strip().splitlines()[-1])
        assert data["intent_unchanged"] is True and data["service_effects"] == []
        print("SYMPTOM_ABSENT")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:500])
        raise SystemExit(2)
