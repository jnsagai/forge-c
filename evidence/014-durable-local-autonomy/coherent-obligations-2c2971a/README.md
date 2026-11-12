# Coherent obligations — candidate2c2971a, NOT DEPLOYED

Owner requires small coherent obligations, global coverage and a factory that
works across drivers. The current register splitter balances fields by position.
On the actual CRC inventory it puts RTYPE_IN in CRC_CR_1 and REV_IN in CRC_CR_2,
although the owner scope explicitly defines their joint input-reversal operation.
The author is told to act only on its packet fields. Locally VALID separate
packets therefore do not establish a coherent operation or conformance.

This is a deterministic decomposition defect. Its contribution to the actual
model's reasoning time and eventual product outcome is UNMEASURED. It is not a
claim that the model has failed the product or that this fix proves success.

Candidate2c2971a7e3d04bf892180c3b6bef1c96dfd2b52b:
- Prospectively opts ASPICE profilev2 into literal field dependencies from
  parenthesized positive owner-scope clauses. Excluded scope is ignored.
- Generic connected components keep coupled fields together, balancing bounded
  packets with unique ownership and complete inventory coverage.
- No peripheral/field names are hard-coded in implementation. An unrelated
  device and transitive dependencies are exercised.
- Oversized, unknown-field and cross-register obligations are explicitly
  capability-limited before any inference. They are not silently split or dropped.
- Legacy inventories/profiles keep their exact previous balanced partition.
  Frozen inspector source, gates, oracles and hardware semantics are unchanged.

Baseline2/2FAIL reproduces split dependency and missing oversize refusal.
Candidate56PASS, exact9PASS, zero skips. These are local deterministic/scripted
tests; zero Qwen calls and no native qualification. Ruff/diff checksPASS.
Commands:
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=<checkout>/factory/python FORGE_DATA_ROOT=<loop10-root> TMPDIR=<loop10-audit>
<loop10-venv>/bin/python -m pytest -q
factory/python/tests/test_lrtx_coherent_obligations.py
factory/python/tests/test_lrtx_swe1.py
factory/python/tests/test_aspice_development.py
factory/python/tests/test_da014_required_scope_coverage.py
--junitxml=<loop10-audit>/coherent-final-tests.xml

Runtime remains fcb15cb. At15:06:50Z four actual Qwen packets are locally VALID,
including both CR partitions; no phase baseline or inspection exists. Native
qualification is NOT_RUN while the owner-dedicated remote mission is live.
Do not mutate its profile/source/checkpoints, refill the mission or infer success.
Promote only after native checks and exact provider quiescence, with new pinned
role/source/profile authority and the unchanged remaining mission/deadline.
Feature014 stays30/58, no task tick. No proven learning, benchmark or availability.
