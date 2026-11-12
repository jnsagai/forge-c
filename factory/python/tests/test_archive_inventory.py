"""Independent package inventory faults must fail even when surviving bytes match."""
import hashlib
import zipfile

import pytest
from forge_factory.release.finalize import verify_archive


def archive(tmp_path, fault=None):
    files = {"manifest.json": b'{"package_status":"BLOCKED"}\n',
             "evidence/verification.txt": b"Recorded verification evidence\n"}
    checksums = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n"
                        for name, data in files.items()).encode()
    if fault == "missing-member":
        del files["evidence/verification.txt"]
    elif fault == "unlisted-member":
        files["evidence/unlisted.txt"] = b"Unbound evidence\n"
    elif fault == "duplicate-checksum":
        checksums += checksums.splitlines(keepends=True)[0]
    elif fault == "malformed-checksum":
        checksums = b"not-a-checksum\n"
    elif fault == "invalid-encoding":
        checksums = b"\xff\n"
    elif fault == "empty-index":
        files.clear()
        checksums = b""
    path = tmp_path / "review.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr("SHA256SUMS.txt", checksums)
        if fault == "duplicate-member":
            with pytest.warns(UserWarning, match="Duplicate name"):
                z.writestr("manifest.json", files["manifest.json"])
    return path


def test_valid_inventory_with_and_without_external_checksum(tmp_path):
    path = archive(tmp_path)
    assert verify_archive(path)["integrity"] == "PASS"
    path.with_name(path.name + ".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "  review.zip\n")
    assert verify_archive(path)["integrity"] == "PASS"


@pytest.mark.parametrize("fault", ["missing-member", "unlisted-member", "duplicate-member", "duplicate-checksum",
                                  "malformed-checksum", "invalid-encoding", "empty-index"])
def test_incomplete_ambiguous_or_malformed_inventory_is_rejected(tmp_path, fault):
    result = verify_archive(archive(tmp_path, fault))
    assert result["integrity"] == "FAIL", result
    assert result["issues"]


@pytest.mark.parametrize("checksum", ["", "not-a-checksum\n", "0" * 64 + "  review.zip\n"])
def test_invalid_external_checksum_is_a_failed_verification(tmp_path, checksum):
    path = archive(tmp_path)
    path.with_name(path.name + ".sha256").write_text(checksum)
    result = verify_archive(path)
    assert result["integrity"] == "FAIL" and result["issues"]
