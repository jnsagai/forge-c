# Missing MCP tool root: actual SWE.3 failure and undeployed correction

Current production **9b4c390e1605d11c4865bdeea382df74a0078692** is still running
the owner-selected full-pipeline QM demonstration. The two-function FROZEN IDR
scope and all previous accounting/quality findings remain intact.
Candidate **9f9a93f174f46aa0add59c16a423be7d56988614** fixes the diagnosed root
propagation defect and includes the previously local-qualified admission diagnostics;
it is **not deployed**. No current service, grant or run was restarted/replaced.

## Later complete SWE.4 phase and simulation result — 15:47UTC

Actual SWE.4 inspection/current frozen baseline/deterministic gate PASS;17private
local files hash/size verified. Renode subsequently reports27checks passed/0failed
across two images on its behavioural CRC model after a performance-test build failure.
SWE.5 author is active; phase inspection/full product pending. See
[swe4-frozen evidence](swe4-frozen/README.md). The environment-fix native qualification
is [staged but NOT_RUN](native-prepared/README.md); only bootstrap-v2.py is current.
Current mission remains uninterrupted and original failures are preserved.

## Later SWE.4 host-unit result — 15:19UTC

Actual host-unit results FAIL twice for duplicate test IDs, then PASS at15:18:27UTC,
exit0. Scoped two-function LLVM function/region coverage100%; whole-file line6.76%/
function8.33%, target evidencefalse. This is ordinary authoring feedback, not M3,
measured learning or factory-self-healing qualification. SWE.4 test author remains
active at15:19:19UTC with104requests; phase inspection/full product pending.
See swe4-host/ for actual failed/passing tool records, coverage and live observation.

## Actual SWE.3 outcome and diagnosis

Qwen produced detailed_design.md (5811bytes), unit_specifications.md (3315bytes),
two unit diagrams and a code-trace map. The current frozen baseline is
97f4c1c95f841e179d72846ff63e49ac5d777761e8474a87a80403e14a1133f5.
Both real inspections **INS-SWE.3-001/002 FAIL**,14:55:32/14:56:30UTC, retain
major SWE3-10 findings: both unit diagrams returned PLANTUML_NOT_AVAILABLE.
The demonstration proceeded to SWE.4 as requested; the failures remain failures.

A read-only audit of **nine actual MCP processes** confirms FORGE_DATA_ROOT absent,
FORGE_STATE_DIR pointing at the production state, Java available and the installed
PlantUML JAR present under the state parent's toolchains directory. SWE.2 views have
a state-parent fallback; SWE.3 swtrace uses common.data_root(), which falls back to
a developer-machine path when the explicit root is absent. Installed tools alone
therefore did not make them available to the isolated MCP child. This is a runtime
context defect, not evidence that Qwen failed to author valid diagram syntax.
No successful actual SWE.3 render is claimed for the current run.

The generated Fabro TOML now explicitly supplies the selected data root to MCP
servers and policy hooks, alongside the existing state/Python/binding/PATH context.
Per-server and hook overrides retain precedence without duplicate TOML keys.
Hook values/executable/binding paths are shell-quoted, including paths with spaces.
Only the declared environment is forwarded; ambient credentials are not copied.
No new scheduler/store/authority or relaxed quality gate was introduced.

## Qualification and next deployment prerequisite

At exact source9f9a93f the local cohort is **13PASS,0failures/errors/skips,9.959s**:
actual isolated child processes resolve both diagram-check paths to the same explicit
tool root; hook contexts with spaces work; explicit overrides remain; inherited
native qualification context and actual MCP protocol handshakes pass. The focused
two-case test was run first against unchanged49add27 and **both cases fail**.
Location tests use a clearly labeled dummy JAR and never execute it as PlantUML;
they prove context resolution, not rendering or Qwen capability. Raw source-pinned
JUnit/logs are included; published failure transcripts trim trailing whitespace only.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 FORGE_FABRO_LIVE=0 \
PYTHONPATH=factory/python FORGE_DATA_ROOT="$FC014_DATA" TMPDIR="$FC014_TMP" \
python -m pytest -q factory/python/tests/test_fabro_runconfig_context.py \
  factory/python/tests/test_da014_qualification_state.py \
  factory/python/tests/test_m2_mcp.py::test_t018_preflight_live_handshake_and_run_config_has_no_shell \
  --junitxml="$FC014_OUTPUT/pytest.xml"
```

Use the qualified LLVM/PlantUML/Renode/system PATH as in prior local qualification.
**Native qualification NOT_RUN** while this Qwen mission has remote priority.
After actual quiescence, qualify the exact combined candidate on Omniverse, capture
complete role requests, bind source/profile/model identities and verify actual MCP
children receive the correct root before a signed/fenced continuation. Preserve
the existing18:05:39UTC window, mission charges and newer operator intent.
Do not patch the active checkout or reinterpret its historical failed inspections.
The correction is externally implemented by Codex; this is not Qwen self-healing proof.

## Actual compilation and independent static binary evidence

Actual SWE.3 tool records retain the initial NO_OBJECTS/NO_STACK_USAGE blocks,
then configure/target compile PASS, followed by size/stack PASS; Clang and Cppcheck
report PASS. The deterministic delivery verification records UNCHANGED FROZEN code,
zero conformance findings and three recorded guideline findings. These recorded
findings are not waived. Cppcheck does not establish complete MISRA compliance.

The copied target **relocatable driver ELF** hasSHA
730855b86d4618bf10103ef086b846b9298daa5f0ff829c7e3741a5eb9849b0d.
Object-level text8bytes, static RAM0bytes; two measured wrapper frames0bytes.
Independent local LLVM19.1.7 disassembly finds both measurement wrappers, each
two instructions: a32-bit store/read at offset0x04 and return. This is static
code evidence only. Runtime timing, target execution and physical WCET are not
established by disassembly or these object/frame measurements.

All**36**frozen phase/build/tool-log/inspection files are copied privately to local
loop10 with every member's hash/size verified. Transfer archiveSHA
988b51d28add5440590434af3baf2ba1d505c60e29d06ce6a6c767879fecdd7c.
The private folder includes the original failed inspections, target ELF/map, source,
unit contracts, diagrams and raw tool logs. Git contains bounded metadata/audit
scripts only, not vendor headers or complete raw logs.

At15:07:03UTC actual native01M63ZTJ5QM1R96484Y2KN97H6 remains **RUNNING**,
SWE.4 test author active,84requests in this run; SWE.4 inspection has not run.
The existing recorder and local final-outcome collector continue. Strict M1/IE-T008
remains unaccepted; IE-T001–007 and formal30/58 are unchanged. IE-T009/M2–M5, broad
capability, learning benefit and long-duration qualification remain unrun/unproven.
