"""CAPA-067 (rc3 IWDG HAL): every '@test' in one Doxygen block is traced with the '@verifies' that follows it; blocks
with a single @test and file-level blocks keep their previous reading."""
import subprocess
import sys

from forge_factory.common import REPO_ROOT
from forge_factory.inspection.swtrace import tagged_tests


def _tags(tmp_path, text):
    f = tmp_path / "software/tests/unit/test_x.c"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)
    return [(t["test"], t["verifies"], t["file_level"]) for t in tagged_tests([f], tmp_path)]


def test_capa067_reproducer_absent():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr071_multi_test_doc_block.py")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr


def test_each_test_in_one_block_gets_its_own_verifies(tmp_path):
    assert _tags(tmp_path, "/**\n * @test UT-001 @verifies USPEC-LL-01-01\n * @test UT-002\n"
                           " * @verifies USPEC-LL-01-02 USPEC-LL-01-03\n * @test UT-003\n */\n") == [
        ("UT-001", ["USPEC-LL-01-01"], False), ("UT-002", ["USPEC-LL-01-02", "USPEC-LL-01-03"], False),
        ("UT-003", [], False)]


def test_single_test_block_reading_unchanged(tmp_path):
    # @verifies before @test, as earlier runs wrote it, still belongs to that test
    assert _tags(tmp_path, "/** @verifies USPEC-LL-01-01\n * @test UT-001 */\n/** @test UT-002 @verifies USPEC-LL-01-02 */\n") == [
        ("UT-001", ["USPEC-LL-01-01"], False), ("UT-002", ["USPEC-LL-01-02"], False)]


def test_file_level_block_unchanged(tmp_path):
    assert _tags(tmp_path, "/** @file test_x.c\n * @verifies USPEC-LL-01-01 */\n") == [
        ("FILE:test_x.c", ["USPEC-LL-01-01"], True)]
