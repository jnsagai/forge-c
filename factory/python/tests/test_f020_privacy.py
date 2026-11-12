"""Feature 020 T033 (FR-025, SC-008): no benchmark name is in the repository.

The forbidden tokens (programme, peripheral and people names of the private benchmark) are held only as salted SHA-256
hashes in fixtures/f020/forbidden-token-hashes.json; the scan lower-cases and word-splits every tracked file and
reports hits by file and hash, never by token."""
from __future__ import annotations

import json
import re
from pathlib import Path

from forge_factory.benchmark import privacy as P

REPO = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures/f020/forbidden-token-hashes.json"


def test_the_fixture_holds_hashes_only():
    doc = json.loads(FIXTURE.read_text())
    assert doc["schema"] == P.SCHEMA and doc["salt"] and doc["hashes"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in doc["hashes"])
    assert set(doc) == {"schema", "salt", "normalise", "hashes"}


def test_no_tracked_file_holds_a_forbidden_token():
    hits = P.scan_repo(REPO, P.load(FIXTURE))
    assert hits == [], f"forbidden benchmark tokens in tracked files: {hits[:10]}"


def test_a_planted_token_is_found(tmp_path):
    salt = "test-salt"
    hashes = {"salt": salt, "hashes": {P.digest(salt, "zorblax")}}
    clean, planted = tmp_path / "clean.md", tmp_path / "planted.md"
    clean.write_text("A register-level requirement of the module.\n")
    planted.write_text("Notes of the ZORBLAX-81 programme.\n")  # case and punctuation do not hide it
    assert P.scan_paths([clean], hashes) == []
    hits = P.scan_paths([clean, planted], hashes)
    assert hits == [{"file": str(planted), "hash": P.digest(salt, "zorblax")}]


def test_hashing_tool_writes_no_clear_token(tmp_path):
    src = tmp_path / "tokens.txt"
    src.write_text("Zorblax\nquux\n")
    out = tmp_path / "hashes.json"
    assert P.main(["hash", "--tokens", str(src), "--salt", "s1", "--out", str(out)]) == 0
    text = out.read_text()
    assert "zorblax" not in text.lower() and "quux" not in text
    assert json.loads(text)["hashes"] == sorted({P.digest("s1", "zorblax"), P.digest("s1", "quux")})
