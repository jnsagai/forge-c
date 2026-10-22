"""Feature 011 M0 (F011-T005, F011-AT-005): static checks of the authored package and the public/private boundary."""
from __future__ import annotations

import json
import subprocess

import pytest
from forge_factory.safec_bridge import provenance as P
from forge_factory.safec_bridge import static_check as SC

PRIVATE_LINE = "pub fn derive_register_mask(field: &FieldDef, logical: u64) -> Result<u64, SemanticError> {"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path):
    """A private checkout with one tracked source line and a public repository with a base commit."""
    priv, pub = tmp_path / "private", tmp_path / "public"
    for r in (priv, pub):
        r.mkdir()
        _git(r, "init", "-q")
        _git(r, "config", "user.email", "t@example.invalid")
        _git(r, "config", "user.name", "t")
    (priv / "lib.rs").write_text(PRIVATE_LINE + "\n    todo!()\n}\n")
    _git(priv, "add", ".")
    _git(priv, "commit", "-qm", "p")
    (pub / "README.md").write_text("public\n")
    _git(pub, "add", ".")
    _git(pub, "commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=pub, capture_output=True, text=True).stdout.strip()
    return priv, pub, base


def test_feature_documents_resolve_and_examples_behave_as_frozen():
    res = SC.check()
    assert res["status"] == "PASS", [r for r in res["references"] if r["status"] == "MISSING"]
    assert {e["id"] for e in res["schemas"]["examples"] if e["expected_valid"]} == {
        "request-valid-validate-intents", "result-valid-unsupported"}
    assert all(e["as_expected"] for e in res["schemas"]["examples"])


def test_an_unplanned_missing_reference_fails(tmp_path, monkeypatch):
    planned = SC.proposed(SC.REPO_ROOT)
    assert SC.resolve(SC.REPO_ROOT, "factory/python/forge_factory/safec_bridge/nothing_like_this.py",
                      planned)["status"] == "MISSING"
    assert SC.resolve(SC.REPO_ROOT, "config/factory/profiles/local-rtx-v1.yaml", planned)["status"] == "RESOLVED"
    assert SC.resolve(SC.REPO_ROOT, "feat/011-safec-semantic-first", planned)["status"] == "RESOLVED"


def test_a_clean_change_passes_the_boundary_scan(repos):
    priv, pub, base = repos
    (pub / "bridge.py").write_text("def client():\n    return 'public adapter code with nothing private in it'\n")
    res = P.scan_public_tree(pub, base, priv)
    assert res["status"] == "PASS" and res["private_checkout_compared"] and res["files_scanned"] == 1


def test_a_copied_private_line_is_found_without_storing_it(repos):
    priv, pub, base = repos
    (pub / "notes.md").write_text("context\n    " + PRIVATE_LINE + "\n")
    res = P.scan_public_tree(pub, base, priv)
    assert res["status"] == "FAIL"
    assert res["findings"] == [{"path": "notes.md", "line": 2, "kind": "PRIVATE_SOURCE_LINE"}]
    assert "derive_register_mask" not in repr(res)


def test_credentials_are_found_in_tracked_and_untracked_changes(repos):
    priv, pub, base = repos
    (pub / "README.md").write_text("public\ntoken = ghp_" + "k7Qz9" + "Wm2Xv4Rt8Ln3" + "Yp6Bs1Hd5Jf0" + "\n")
    (pub / "new.txt").write_text("-----BEGIN " + "OPENSSH PRIVATE KEY-----\n")  # assembled: not a key in this file
    kinds = {(f["path"], f["kind"]) for f in P.scan_public_tree(pub, base)["findings"]}
    assert ("README.md", "CREDENTIAL:GITHUB_TOKEN") in kinds and ("new.txt", "CREDENTIAL:PRIVATE_KEY") in kinds


def test_a_line_public_forge_c_already_had_is_not_a_private_copy(repos):
    priv, pub, base = repos
    (pub / "old.py").write_text(PRIVATE_LINE + "\n")
    _git(pub, "add", ".")
    _git(pub, "commit", "-qm", "public before")
    base2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=pub, capture_output=True, text=True).stdout.strip()
    (pub / "new.py").write_text(PRIVATE_LINE + "\n")
    assert P.scan_public_tree(pub, base2, priv)["status"] == "PASS"
    assert P.scan_public_tree(pub, base, priv)["status"] == "FAIL"


def test_placeholders_are_not_credentials():
    assert P.credentials("Authorization: Bearer " + "x" * 30) == []
    assert P.credentials("api_key = " + "<redacted-value>" * 2) == []
    assert P.credentials("token = " + "k7Qz9Wm2" + "Xv4Rt8Ln") == ["ASSIGNED_SECRET"]


def test_a_single_shared_idiom_is_not_a_copy_but_a_block_is(repos):
    priv, pub, base = repos
    idiom = "        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))"
    second = "        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))"
    (priv / "runner.py").write_text(idiom + "\n" + second + "\n")
    _git(priv, "add", ".")
    _git(priv, "commit", "-qm", "idiom")
    (pub / "a.py").write_text("x = 1\n" + idiom + "\ny = 2\n")
    assert P.scan_public_tree(pub, base, priv)["status"] == "PASS"
    (pub / "b.py").write_text(idiom + "\n" + second + "\n")
    res = P.scan_public_tree(pub, base, priv)
    assert [(f["path"], f["line"]) for f in res["findings"]] == [("b.py", 1), ("b.py", 2)]


def test_shared_public_contracts_are_not_private_content(repos):
    priv, pub, base = repos
    d = pub / "specs/011-safec-semantic-first/contracts"
    d.mkdir(parents=True)
    (d / "x.schema.json").write_text(PRIVATE_LINE + "\n")
    assert P.scan_public_tree(pub, base, priv)["status"] == "PASS"


@pytest.mark.parametrize("value, issue", [
    ("see " + "/PRIV/crates/safec-core/src/lib.rs", "PRIVATE_PATH:note"),
    ("Authorization: Bearer " + "eyJhbGci" + "OiJIUzI1NiJ9" + "q8Wn3Kz", "CREDENTIAL:note:BEARER"),
    (PRIVATE_LINE, "PRIVATE_SOURCE_LINE:note"),
    ("line one\nline two", "VALUE_TOO_LARGE_OR_MULTILINE:note"),
], ids=["private-path", "bearer", "private-line", "multiline"])
def test_public_summary_refuses_private_excerpts_and_secrets(tmp_path, value, issue, monkeypatch):
    """F011-AT-005: the collector refuses (never truncates or masks) and returns nothing to persist."""
    priv = tmp_path / "PRIV"
    priv.mkdir()
    fps = {P._digest(PRIVATE_LINE)}
    rec = {"status": "PASS", "note": value.replace("/PRIV", str(priv))}
    with pytest.raises(P.LeakRefused) as exc:
        P.public_summary(rec, ("status", "note"), private_root=priv, fingerprints=fps)
    assert issue in exc.value.issues


def test_public_summary_keeps_only_allowed_scalars(tmp_path):
    rec = {"status": "FAIL", "tests_passed": 263, "raw_log": "secret-ish", "linux": True, "tools": ["cbmc 6.11.0"]}
    assert P.public_summary(rec, ("status", "tests_passed", "linux", "tools")) == {
        "status": "FAIL", "tests_passed": 263, "linux": True, "tools": ["cbmc 6.11.0"]}
    with pytest.raises(P.LeakRefused, match="NOT_A_SCALAR:nested"):
        P.public_summary({"nested": {"a": 1}}, ("nested",))


def test_linux_probe_reports_counts_and_keeps_raw_logs_private(tmp_path, monkeypatch):
    """F011-T004: the probe parses cargo's own result lines, never passes on a failed test and writes only the
    public summary outside the private directory."""
    from forge_factory.safec_bridge import probe

    bindir = tmp_path / "bin"
    bindir.mkdir()
    cargo = bindir / "cargo"
    cargo.write_text("#!/bin/sh\nif [ \"$1\" = --version ]; then echo 'cargo 9.9.9 (stub)'; exit 0; fi\n"
                     "echo 'test result: ok. 5 passed; 0 failed; 1 ignored; 0 measured'\n"
                     "echo 'test result: FAILED. 2 passed; 1 failed; 0 ignored; 0 measured'\nexit 101\n")
    cargo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:/usr/bin:/bin")
    monkeypatch.setattr(probe, "FORMAL_BIN", tmp_path / "no-formal")
    monkeypatch.setattr(probe, "TOOLS", ("kind2-not-installed",))
    checkout = tmp_path / "safec"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    out = tmp_path / "private-out" / "run"
    s = probe.probe(checkout, out, tmp_path / "cargo-home")
    assert (s["tests_passed"], s["tests_failed"], s["tests_ignored"], s["test_binaries"]) == (7, 1, 1, 2)
    assert s["status"] == "FAIL" and s["cargo_exit"] == 101 and s["tools_missing"] == ["kind2-not-installed"]
    assert (out / "cargo-test.log").is_file() and str(checkout) not in json.dumps(s)
