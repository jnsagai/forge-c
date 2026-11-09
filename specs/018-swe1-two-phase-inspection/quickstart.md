# Quickstart: validating the two-phase SWE.1 inspection

Prerequisites: Omniverse2 clone of `feat/018-swe1-two-phase-inspection`, `uv` on PATH, the private RM0486 inputs.

1. Unit and replay tests (no model):
   `cd factory/python && uv run --frozen pytest -q -p no:cacheprovider tests/test_f018_*.py`
   Expected: per-requirement verdict checkpointing, splice invariant (other requirements byte-identical),
   rounds/no-progress stops, carried findings, graph insertion, SQ reply rule, report.
2. Graph check: `uv run pytest -q tests/test_builder_structured_refactor_golden.py` after re-recording, and inspect
   the SWE.1 nodes: `swe1_author -> swe1_iq_inspect_serve -> swe1_iq_inspect -> ... -> swe1_author_gate`.
3. Design check: `python3 tests/spec/validate_design.py`.
4. Native acceptance (owner lane, after deploy): the WWDG SWE.1 order
   `WO-F014-SWE1-WWDGL-20261109-L44` produces `.forge-run/lrtx/SWE.1/phase1/summary.json` (every requirement
   judged, swaps <= 2 per round), `inspection/SWE.1/quality-report.md`, and the SWE1-01..08 inspection with SQ items.
