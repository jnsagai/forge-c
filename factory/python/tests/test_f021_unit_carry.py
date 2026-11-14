"""Feature 021 T013 (FR-005, SWE.3 per unit) on top of T009: a SWE.3 author task is one unit (`code:<SWU>`) whose
packet holds only that unit's own dependency set - its requirements and register cases and the generated defines of
the registers it accesses. A changed requirement therefore changes the semantic key of exactly the units it is
allocated to, so a rerun inherits every other unit (visit.inherited_task) and authors only the changed ones."""
from __future__ import annotations

import re
import shutil

from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe3
from test_lrtx_swe3 import ws2  # noqa: F401 - SWE.2-complete LL workspace (owner inputs)
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401
from test_lrtx_swe2 import ws1  # noqa: F401


def test_a_changed_requirement_changes_only_the_keys_of_its_units(ws2, tmp_path):  # noqa: F811
    us = swe3.units(ws2)
    before = {u["id"]: S.semantic_key(swe3.code_packet(ws2, u, "m")) for u in us}
    target = next(u for u in us if len(u["swrs"]) == 1)
    swr = target["swrs"][0]
    other = tmp_path / "rerun"
    shutil.copytree(ws2, other, symlinks=True)
    md = other / "workproducts/SWE.1/software_requirements.md"
    text = md.read_text()
    new = re.sub(rf"({re.escape(swr)}\b[^\n]*?)(\.)(\s*\n)", r"\1, as revised in the rerun\2\3", text, count=1)
    assert new != text
    md.write_text(new)
    after = {u["id"]: S.semantic_key(swe3.code_packet(other, u, "m")) for u in swe3.units(other)}
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {u["id"] for u in us if swr in u["swrs"]}
    assert target["id"] in changed and len(changed) < len(us)
