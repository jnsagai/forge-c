"""LAB-T00 (process-first design rev 4, increment 1): moving the `swap`/`pipe`/`continuation` closures of
`builder.structured_authors` to module level must leave every generated graph byte-identical.

The golden hashes were recorded from the unrefactored builder (feat/014-process-lab 3f0cc667 = 31231e0c source).
Regenerate only for a deliberate graph change: FORGE_GOLDEN_WRITE=1 pytest this file.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from forge_factory.workflow import builder

GOLDEN = Path(__file__).parent / "fixtures" / "process_lab" / "structured_authors_golden.json"
ALL = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
BASE = {"model": "golden-model:q8", "timeout_s": 3600, "visit_time_s": 1200}
CASES = {
    "plain-ll": dict(layer="LL", trace=True),
    "plain-legacy": dict(),
    "structured-all": dict(layer="LL", trace=True, structured={**BASE, "phases": ALL, "inspect_phases": ALL}),
    "structured-reinspect": dict(layer="LL", trace=True,
                                 structured={**BASE, "phases": ALL, "inspect_phases": ALL, "reinspect": True}),
    "structured-advisory": dict(layer="LL", trace=True, structured={**BASE, "phases": ALL, "inspect_phases": ALL,
                                                                     "reinspect": True, "advisory": True}),
    "structured-swe1-only": dict(layer="LL", trace=True,
                                 structured={**BASE, "phases": ["SWE.1"], "inspect_phases": ["SWE.1"]}),
    "structured-demonstration": dict(layer="LL", trace=True, structured={**BASE, "phases": ALL, "inspect_phases": ALL,
                                                                          "demonstration": True}),
    "structured-hal": dict(layer="HAL", trace=True, isolation=True,
                           structured={**BASE, "phases": ALL, "inspect_phases": ALL, "reinspect": True}),
}


def _hash(kw: dict) -> str:
    """The normalized graph's sha256, or the exact refusal: a refusal is behaviour the refactor must keep too."""
    try:
        g, _ = builder.build("WO-GOLD", chunk_lines=150, **kw)
    except ValueError as exc:
        return f"ValueError:{exc}"
    g = g.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")
    return hashlib.sha256(g.encode()).hexdigest()


def test_record_or_compare_golden():
    got = {name: _hash(kw) for name, kw in CASES.items()}
    if os.environ.get("FORGE_GOLDEN_WRITE") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(got, indent=1, sort_keys=True) + "\n")
        pytest.skip("golden recorded")
    assert got == json.loads(GOLDEN.read_text())
