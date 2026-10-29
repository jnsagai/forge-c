# SWE.6 declared performance-test contract

Exact source **b1536d78bbfa23677c562a2e2e82aef4d27f423a**, undeployed. The
interrupted real Qwen suite called scn_performance.c for SWR008/009, while the
existing simulator instruments only the declared target test. The gate correctly
refused a complete passing measurement. This change exposes that contract and
distinguishes wrong source, missing/failed observation and changed budget. It does
not accept copied measurements or change any budget, instrumentation or verdict.
The opt-in scaffold names the exact test; MCP returns the input contract as compact
JSON metadata, explicitly not a measurement. Legacy non-performance suites retain
their existing scaffold and result shape.

[Exact qualification](qualification.json): **37PASS,0failures/errors/skips**,112.827s,
local CPU tools only. [XML](local-pytest.xml), [log](local-pytest.log) and
[actual Robot tool results](actual-local-robot-results.json) include an actual
compiler/Robot/Renode PASS for the declared test and FAIL for a separate scenario.
Other controls reject a transplanted observation, stale budget, missing/failed
measurement and target check failure. The full scoped six-phase fixture uses
explicitly scripted semantic artifacts; it is not Qwen authorship or acceptance.
Inherited Robot policy/coverage and MCP/hook root checks pass in the same cohort.
Ruff E9/F/B and static specification/contracts validate; neither proves native
runtime or product qualification. The initial uncommitted patch had22PASS/2FAIL:
nested metrics were dropped by the MCP scalar envelope. Those original
[failures](initial-pytest.xml) are preserved; compact JSON-string metadata corrects
them before the37-pass exact-source qualification.

The remote remains **STOPPED epoch33**, provider gone, no compute processes,
execution QUIESCENT/lease RELEASED. **Native qualification NOT_RUN**. Earlier
epoch32 staged tooling is bound to9f9a93f and must refuse the owner's newer stop;
do not treat it as qualification of this combined descendant. No new inference,
grant renewal, source activation, budget reset, automatic18:00 restart or task
completion is claimed. Strict M1/M2–M5 remain unaccepted/unrun as applicable.

[Transfer proof](interrupted-transfer.json) and [full file inventory](interrupted-file-inventory.json)
record101files/4482319bytes copied privately to loop10. All hashes/sizes verified;
archiveSHA12dbfd978a1530bc66e419b4091226de86bd276e46bb99811032d443ba822682.
This is an interrupted point-in-time engineering snapshot, **not** a completed
release package. SWE.6 has test sources and actual Robot results, no finished
report or inspection. Raw vendor code, restricted references and engineering logs
remain private. No model reasoning or credentials are captured or published.
