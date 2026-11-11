"""Feature 016 OB-T020 (FR-020, SC-002): onboarding re-derives the hand-written facts of every existing ST delivery
example. Every difference must be a reviewed exception with its explanation."""
import os
import shutil

import pytest

from forge_factory.common import REPO_ROOT
from forge_factory.onboarding import oracle as O


def _have_inputs():
    return shutil.which("arm-none-eabi-gcc") and os.path.isdir(os.path.expandvars("$FORGE_DATA_ROOT/inputs/st"))


@pytest.mark.parametrize("example", O.ORACLE_EXAMPLES)
def test_derivation_reproduces_the_hand_written_facts(example, tmp_path, monkeypatch):
    if not _have_inputs():
        pytest.skip("ST inputs or the Arm GNU toolchain not on this host")
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    exc = O.exceptions()
    for d in O.compare(REPO_ROOT / "examples" / example):
        e = exc.get((example, d["fact"]))
        assert e is not None, f"unreviewed difference {example}:{d}"
        if d["fact"] != "instance":
            assert sorted(map(str, e["hand_value"] or [])) == sorted(
                str(x[0]) if isinstance(x, (list, tuple)) else str(x) for x in (d["hand_value"] or [])) or \
                e["hand_value"] == d["hand_value"], f"exception no longer matches {example}:{d}"


def test_every_exception_is_explained_and_still_needed():
    exc = O.exceptions()
    assert all(e["explanation"].strip() and e["reviewed_by"] for e in exc.values())
    assert {ex for ex, _ in exc} <= set(O.ORACLE_EXAMPLES)
