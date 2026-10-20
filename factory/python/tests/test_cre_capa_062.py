"""CAPA-062 (b008): the package of a header-only delivery shows the generated build-only unit in software/src, marked as
generated (not delivered code); a stage that already has a C source is left unchanged."""
import subprocess
import sys

from forge_factory.common import REPO_ROOT
from forge_factory.release import finalize as F


def test_capa062_header_only_delivery_gets_the_generated_unit():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr066_header_only_delivery_no_c_source.py")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr


def test_capa062_existing_c_source_is_kept(tmp_path):
    (tmp_path / "stage/software/src").mkdir(parents=True)
    (tmp_path / "stage/software/src/drv.c").write_text("int x;\n")
    assert F.stage_delivered_unit(tmp_path / "ws", tmp_path / "stage") is False
    assert sorted(p.name for p in (tmp_path / "stage/software/src").iterdir()) == ["drv.c"]
