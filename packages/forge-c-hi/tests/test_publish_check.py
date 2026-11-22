"""T069: the publish check detects every violation class. Samples are assembled at run time so that this file itself
stays clean when the package is checked."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from conftest import PKG

CHECK = PKG / "tools" / "publish_check.py"


def run(root, *args):
    r = subprocess.run([sys.executable, str(CHECK), str(root), "--no-audit", *args], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


def clean(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# Package\n\nThe driver shall start the counter. Contact: a@example.com\n")
    return tmp_path / "pkg"


def test_clean_package_passes(tmp_path):
    code, out = run(clean(tmp_path), "--denylist", str(tmp_path / "none.txt"))
    assert code == 0 and out["status"] == "PASS", out


@pytest.mark.parametrize("name,content,cls", [
    ("manual.pdf", b"%PDF-1.4 binary", "BINARY-DOC"),
    ("blob.bin", b"abc\0def", "BINARY-DOC"),
    ("notes.md", ("see /ho" + "me/alice/work/file").encode(), "PRIVATE"),
    ("notes2.md", ("data on /med" + "ia/alice/disk").encode(), "PRIVATE"),
    ("hosts.md", ("ssh to 192." + "168.1.20 or 100." + "87.10.79").encode(), "PRIVATE"),
    ("mail.md", ("write to alice" + "@" + "corp-mail.com").encode(), "EMAIL"),
    ("zw.md", ("hidden" + chr(0x200B) + "text").encode(), "HIDDEN-UNICODE"),
    ("bidi.md", ("x" + chr(0x202E) + "y").encode(), "HIDDEN-UNICODE"),
])
def test_each_class_detected(tmp_path, name, content, cls):
    root = clean(tmp_path)
    (root / name).write_bytes(content)
    code, out = run(root, "--denylist", str(tmp_path / "none.txt"))
    assert code == 1 and cls in out["by_class"], out


def test_quoted_standard_text_detected_but_own_requirements_are_not(tmp_path):
    root = clean(tmp_path)
    words = " ".join(["the", "item"] * 14)
    quoted = f'Per ISO 26262-6 clause 7: "{words} shall be specified and verified by the supplier for each element."\n'
    (root / "q.md").write_text(quoted)
    code, out = run(root, "--denylist", str(tmp_path / "none.txt"))
    assert code == 1 and "QUOTED-TEXT" in out["by_class"]
    (root / "q.md").write_text("> " + words + " shall be specified for each element in RM0486.\n")
    assert run(root, "--denylist", str(tmp_path / "none.txt"))[1]["by_class"].get("QUOTED-TEXT") == 1
    (root / "q.md").write_text(f'Our requirement: "{words} shall start the counter within 5 ms of the call."\n')
    assert run(root, "--denylist", str(tmp_path / "none.txt"))[0] == 0


def test_local_denylist_literals(tmp_path):
    root = clean(tmp_path)
    (root / "x.md").write_text("benchmark PRIVATEBENCH-9 results\n")
    deny = tmp_path / "deny.txt"
    deny.write_text("# private names\nprivatebench-9\n")
    code, out = run(root, "--denylist", str(deny))
    assert code == 1 and out["by_class"]["PRIVATE"] == 1 and "privatebench" not in json.dumps(out).lower()


def test_denylist_inside_package_is_refused(tmp_path):
    root = clean(tmp_path)
    (root / "deny.txt").write_text("x\n")
    code, out = run(root, "--denylist", str(root / "deny.txt"))
    assert code == 2


def test_this_package_is_clean():
    code, out = run(PKG)
    assert code == 0, out
