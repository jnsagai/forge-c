"""Normal signed TEST bundle must refuse unrelated drift; real preflight and pytest.

The CRE metadata is a synthetic control, never independent source qualification.
No owner keys, model calls, network access, live installs or authority are used.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile

from forge_factory.offline import patch as P

SIG = "offline signed patch carries unrelated deployed source drift into the reviewed target"


def main():
    with tempfile.TemporaryDirectory(prefix="rpr173-") as directory:
        root = Path(directory)
        repo = root / "dev"
        (repo / "factory/python/pkg").mkdir(parents=True)
        (repo / "tests").mkdir()
        (repo / "config/factory").mkdir(parents=True)

        def git(*args):
            return subprocess.check_output(["git", *args], cwd=repo)

        git("init", "-q")
        git("config", "user.name", "TEST fixture")
        git("config", "user.email", "fixture@invalid")
        (repo / "config/factory/reliability-policy.yaml").write_text(
            "security:\n  protected_path_globs:\n    - config/factory/reliability-policy.yaml\n    - evidence/**\n")
        (repo / "factory/python/pkg/__init__.py").write_text("")
        (repo / "factory/python/pkg/unchanged.py").write_text("LIMIT = 10\n")
        (repo / "factory/python/pkg/rule.py").write_text("def answer():\n    return 41\n")
        (repo / "tests/test_rule.py").write_text(
            "from pkg.rule import answer\n\ndef test_answer():\n    assert answer() == 42\n")
        git("add", "-A")
        git("commit", "-qm", "fixture base")
        base = git("rev-parse", "HEAD").decode().strip()
        (repo / "factory/python/pkg/rule.py").write_text("def answer():\n    return 42\n")
        git("commit", "-qam", "fixture target")
        target = git("rev-parse", "HEAD").decode().strip()
        dec = root / "CONTROL-synthetic-cre.json"
        dec.write_text(json.dumps(dict(decision_id="CONTROL-SYNTHETIC-NOT-QUALIFICATION", decision=P.ELIGIBLE,
            baseline_revision=base, candidate_revision=target,
            baseline_sha256=hashlib.sha256(git("ls-tree", "-r", base)).hexdigest(),
            candidate_sha256=hashlib.sha256(git("ls-tree", "-r", target)).hexdigest())))
        key = root / "TEST-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        signers = root / "TEST-signers"
        signers.write_text(f'FixtureOwner namespaces="{P.NAMESPACE}" {key.with_suffix(".pub").read_text()}')
        bundle = root / "patch.zip"
        P.build(repo, base, target, ["tests/test_rule.py"], dec, "FixtureOwner", bundle)
        P.sign(bundle, key)
        outcomes = {}
        for case in ("clean", "drift"):
            install = root / case
            release = install / "releases" / base
            release.mkdir(parents=True)
            with tarfile.open(fileobj=io.BytesIO(git("archive", base))) as archive:
                archive.extractall(release, filter="data")
            if case == "drift":
                (release / "factory/python/pkg/unchanged.py").write_text("LIMIT = 999\n")
            P._switch(install, base)
            # Syntax compilation in memory, plus the normal importer runs the declared pytest.
            expression = "from pathlib import Path; [compile(p.read_bytes(),str(p),'exec') for p in Path('factory/python').rglob('*.py')]"
            result = P.import_patch(bundle, install_root=install, allowed_signers=signers,
                preflight_cmd=shlex.join([sys.executable, "-c", expression]))
            outcomes[case] = result
            if case == "clean":
                assert result["code"] == "PATCH_OK", result
                assert all(check["exit_code"] == 0 for check in result["checks"])
                assert (install / "current/factory/python/pkg/unchanged.py").read_bytes() == git(
                    "show", f"{target}:factory/python/pkg/unchanged.py")
                assert P.rollback(install)["current"] == base
            elif result["code"] == "PATCH_OK":
                assert (install / "current/factory/python/pkg/unchanged.py").read_bytes() != git(
                    "show", f"{target}:factory/python/pkg/unchanged.py")
                print(json.dumps(outcomes, sort_keys=True))
                print("SYMPTOM_PRESENT:" + SIG)
                return 1
            else:
                assert result["code"] == "PATCH_BASE_DRIFT", result
                assert result["current"] == base and "checks" not in result
                assert not (install / "releases" / target).exists()
        print(json.dumps(outcomes, sort_keys=True))
        print("SYMPTOM_ABSENT")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
