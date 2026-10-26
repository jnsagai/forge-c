"""DA-T058 / DA-AT-058: a signed patch bundle activates only after every check and its local preflight and
regression pass; tampered, unsigned, wrong-base, drifted, protected-path and CRE-less bundles are refused with their
exact reason; rollback restores the previous release; nothing opens a network connection."""
import json
import socket
import subprocess
import zipfile

import pytest
from forge_factory.offline import patch as P

POLICY = "security:\n  protected_path_globs:\n    - config/factory/reliability-policy.yaml\n    - evidence/**\n"


def _git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def env(tmp_path):
    repo = tmp_path / "dev"
    (repo / "factory/python/pkg").mkdir(parents=True)
    (repo / "config/factory").mkdir(parents=True)
    (repo / "tests").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "config/factory/reliability-policy.yaml").write_text(POLICY)
    (repo / "factory/python/pkg/__init__.py").write_text("")
    (repo / "factory/python/pkg/rule.py").write_text("def answer():\n    return 41\n")
    (repo / "factory/python/pkg/old.py").write_text("X = 1\n")
    (repo / "tests/test_rule.py").write_text("from pkg.rule import answer\n\n\ndef test_answer():\n"
                                              "    assert answer() == 42\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "factory/python/pkg/rule.py").write_text("def answer():\n    return 42\n")
    (repo / "factory/python/pkg/new.py").write_text("Y = 2\n")
    (repo / "factory/python/pkg/old.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "target")
    target = _git(repo, "rev-parse", "HEAD")
    root = tmp_path / "install"
    (root / "releases").mkdir(parents=True)
    subprocess.run(f"git -C {repo} archive {base} | tar -x -C {root / 'releases'} --one-top-level={base}",
                   shell=True, check=True)
    P._switch(root, base)
    key = tmp_path / "owner"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    signers = tmp_path / "allowed-signers"
    signers.write_text(f'Jefferson namespaces="{P.NAMESPACE}" {(tmp_path / "owner.pub").read_text()}')
    dec = tmp_path / "pd-test.json"
    dec.write_text(json.dumps({"decision_id": "pd-test", "decision": P.ELIGIBLE, "candidate_revision": target,
                               "baseline_revision": base, "allowed_auto_deployment": False}))
    return {"repo": repo, "base": base, "target": target, "root": root, "key": key, "signers": signers, "dec": dec,
            "tmp": tmp_path}


def _bundle(env, name="p.zip", sign=True, **kw):
    out = env["tmp"] / name
    args = {"repo": env["repo"], "base": env["base"], "target": env["target"], "regression": ["tests/test_rule.py"],
            "cre_decision": env["dec"], "approver": "Jefferson", "out": out} | kw
    P.build(**args)
    if sign:
        P.sign(out, env["key"])
    return out


def _preflight_ok(staged, regression):
    return [{"check": "preflight", "exit_code": 0}] + P._checks_default(staged, regression, "true")[1:]


def _import(env, bundle, checks=_preflight_ok, **kw):
    return P.import_patch(bundle, install_root=env["root"], allowed_signers=env["signers"], checks=checks, **kw)


def test_a_valid_patch_activates_after_its_local_checks_and_rolls_back(env, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network use")

    monkeypatch.setattr(socket, "create_connection", refuse)
    b = _bundle(env)
    r = _import(env, b)
    assert r["decision"] == "ACTIVATED" and r["current"] == env["target"] and r["previous"] == env["base"]
    assert [c["check"] for c in r["checks"]] == ["preflight", "regression"]
    assert all(c["exit_code"] == 0 for c in r["checks"])  # the declared regression passed in the staged release
    new = env["root"] / "current"
    assert (new / "factory/python/pkg/rule.py").read_text().endswith("return 42\n")
    assert (new / "factory/python/pkg/new.py").is_file() and not (new / "factory/python/pkg/old.py").exists()
    assert (env["root"] / "releases" / env["base"] / "factory/python/pkg/old.py").is_file()  # previous kept
    assert P.rollback(env["root"])["current"] == env["base"]
    assert (env["root"] / "current/factory/python/pkg/rule.py").read_text().endswith("return 41\n")
    assert P.rollback(env["root"])["code"] == "NO_ACTIVATION_TO_UNDO"
    log = [json.loads(x) for x in (env["root"] / "imports/log.jsonl").read_text().splitlines()]
    assert [x["decision"] for x in log] == ["ACTIVATED", "ROLLED_BACK", "ROLLBACK_REFUSED"]


def _tamper(bundle, name, data):
    files = {n: zipfile.ZipFile(bundle).read(n) for n in zipfile.ZipFile(bundle).namelist()}
    with zipfile.ZipFile(bundle, "w") as zf:
        for n, d in {**files, name: data}.items():
            zf.writestr(n, d)


def test_tampered_unsigned_and_foreign_signatures_are_refused(env, tmp_path):
    b = _bundle(env)
    _tamper(b, "files/factory/python/pkg/rule.py", b"def answer():\n    return 0\n")
    assert _import(env, b)["code"] == "PATCH_HASH_MISMATCH"
    b = _bundle(env, "smuggle.zip")
    _tamper(b, "files/factory/python/pkg/extra.py", b"import os\n")
    assert _import(env, b)["code"] == "PATCH_INVENTORY"
    assert _import(env, _bundle(env, "unsigned.zip", sign=False))["code"] == "PATCH_SIGNATURE_INVALID"
    other = tmp_path / "intruder"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)], check=True)
    b = _bundle(env, "foreign.zip", sign=False)
    P.sign(b, other)
    assert _import(env, b)["code"] == "PATCH_SIGNATURE_INVALID"
    b = _bundle(env, "edited.zip")  # PATCH.json edited after signing (regression scope narrowed)
    m = json.loads(zipfile.ZipFile(b).read("PATCH.json"))
    _tamper(b, "PATCH.json", json.dumps({**m, "regression": ["tests/nothing.py"]}).encode())
    assert _import(env, b)["code"] == "PATCH_SIGNATURE_INVALID"
    assert (env["root"] / "current").resolve().name == env["base"]  # nothing activated


def test_wrong_base_local_drift_protected_paths_and_missing_cre_decisions_are_refused(env):
    rel = env["root"] / "releases" / env["base"]
    (rel / "factory/python/pkg/rule.py").write_text("def answer():\n    return 40\n")  # local edit since base
    assert _import(env, _bundle(env))["code"] == "PATCH_BASE_DRIFT"
    subprocess.run(["git", "-C", str(env["repo"]), "show", f"{env['base']}:factory/python/pkg/rule.py"],
                   stdout=(rel / "factory/python/pkg/rule.py").open("w"), check=True)
    rejected = env["tmp"] / "pd-rejected.json"
    rejected.write_text(json.dumps({"decision_id": "pd-r", "decision": "REJECTED", "candidate_revision": env["target"],
                                    "baseline_revision": env["base"]}))
    assert _import(env, _bundle(env, "rej.zip", cre_decision=rejected))["code"] == "PATCH_CRE_DECISION"
    other = env["tmp"] / "pd-other.json"
    other.write_text(json.dumps({"decision_id": "pd-o", "decision": P.ELIGIBLE, "candidate_revision": "f" * 40,
                                 "baseline_revision": env["base"]}))
    assert _import(env, _bundle(env, "other.zip", cre_decision=other))["code"] == "PATCH_CRE_DECISION"
    repo = env["repo"]
    (repo / "config/factory/reliability-policy.yaml").write_text(POLICY.replace("evidence/**", "nothing/**"))
    _git(repo, "commit", "-qam", "weaken policy")
    weak = _git(repo, "rev-parse", "HEAD")
    dec = env["tmp"] / "pd-weak.json"
    dec.write_text(json.dumps({"decision_id": "pd-w", "decision": P.ELIGIBLE, "candidate_revision": weak,
                               "baseline_revision": env["base"]}))
    r = _import(env, _bundle(env, "weak.zip", target=weak, cre_decision=dec))
    assert r["code"] == "PATCH_PROTECTED_PATH" and "reliability-policy.yaml" in r["reason"]
    P._switch(env["root"], "f" * 40)  # the deployment is on another release
    assert _import(env, _bundle(env, "base.zip"))["code"] == "PATCH_BASE_MISMATCH"


def test_failing_preflight_or_regression_keeps_the_current_release(env):
    b = _bundle(env)
    r = _import(env, b, checks=lambda s, reg: [{"check": "preflight", "exit_code": 2}])
    assert r["code"] == "PATCH_CHECKS_FAILED" and r["current"] == env["base"]
    assert not any(p.name.startswith(".staging") for p in (env["root"] / "releases").iterdir())
    r = _import(env, b, checks=lambda s, reg: P._checks_default(s, ["tests/test_rule.py"], "false"))
    assert r["code"] == "PATCH_CHECKS_FAILED" and "preflight" in r["reason"]
    r = P.import_patch(b, install_root=env["root"], allowed_signers=env["signers"])  # no preflight configured
    assert r["code"] == "PATCH_NO_PREFLIGHT" and (env["root"] / "current").resolve().name == env["base"]
