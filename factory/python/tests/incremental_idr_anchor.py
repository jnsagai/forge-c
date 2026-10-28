"""Deterministic provider-artifact fixture, real policy/tools/phase gates. Never live Qwen evidence."""
from __future__ import annotations

import json
from pathlib import Path

from forge_factory.brownfield import trace
from forge_factory.common import pretty_json
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx.visit import write_scoped
from forge_factory.mcp import sdk
from forge_factory.policy.authz import Authorizer, Binding
from forge_factory.registry.mcp_registry import fabro_tool_name

HOST = r'''#define FORGE_HOST_DEVICE_IMPLEMENTATION
#include "forge_host_device.h"
#include "stm32n6xx_ll_crc.h"
#include <stdio.h>
static int failures;
/** @test UT-001 @verifies USPEC-LL-01-01 USPEC-LL-01-03 */
static void ut_write(void) {
 const uint32_t values[] = {0U,0xffffffffU,0xaaaaaaaaU,0x55555555U,0x80000001U};
 for(unsigned int i=0;i<5U;i++) {
  CRC->DR=0x87654321U;
  LL_CRC_Write_IDR(CRC,values[i]);
  if(CRC->IDR!=values[i] || CRC->DR!=0x87654321U) failures++;
 }
 printf("UT-001 %s\n",failures ? "FAIL" : "PASS");
}
/** @test UT-002 @verifies USPEC-LL-01-02 USPEC-LL-01-03 */
static void ut_read(void) {
 const uint32_t values[] = {0U,0xffffffffU,0xaaaaaaaaU,0x55555555U,0x80000001U};
 for(unsigned int i=0;i<5U;i++) {
  CRC->IDR=values[i];
  if(LL_CRC_Read_IDR(CRC)!=values[i] || CRC->IDR!=values[i]) failures++;
 }
 printf("UT-002 %s\n",failures ? "FAIL" : "PASS");
}
/** @test UT-003 @verifies USPEC-LL-01-03 */
static void ut_no_status_dependency(void) {
 CRC->DR=0x87654321U;CRC->CR=0xffffffffU;
 LL_CRC_Write_IDR(CRC,0x12345678U);
 if(LL_CRC_Read_IDR(CRC)!=0x12345678U || CRC->DR!=0x87654321U || CRC->CR!=0xffffffffU) failures++;
 printf("UT-003 %s\n",failures ? "FAIL" : "PASS");
}
int main(void) {ut_write();ut_read();ut_no_status_dependency();return failures ? 1 : 0;}
'''
INTEGRATION = r'''#define FORGE_HOST_DEVICE_IMPLEMENTATION
#include "forge_host_device.h"
#include "stm32n6xx_ll_crc.h"
#include <stdio.h>
/** @test IT-001 @verifies SWC_LL IF-01 IF-02 */
int main(void) {
 const uint32_t values[] = {0U,0xffffffffU,0xaaaaaaaaU,0x55555555U,0x80000001U};
 for(unsigned int i=0;i<5U;i++) {
  LL_CRC_Write_IDR(CRC,values[i]);
  if(LL_CRC_Read_IDR(CRC)!=values[i]) {puts("IT-001 FAIL");return 1;}
 }
 puts("IT-001 PASS");return 0;
}
'''
TARGET = r'''/** @file test_crc_idr.c @verifies SWC_LL IF-01 IF-02 */
#include "stm32n6xx_ll_crc.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void) {
 const uint32_t values[] = {0U,0xffffffffU,0xaaaaaaaaU,0x55555555U,0x80000001U};
 uint32_t before_dr, before_cr;
 FORGE_TEST_BEGIN();
 TCHECK(1, CRC->IDR==0U);
 before_dr=CRC->DR;before_cr=CRC->CR;
 for(unsigned int i=0;i<5U;i++) {
  LL_CRC_Write_IDR(CRC,values[i]);
  TCHECK(2, CRC->IDR==values[i]);
  TCHECK(3, LL_CRC_Read_IDR(CRC)==values[i]);
  CRC->IDR=~values[i];
  TCHECK(4, LL_CRC_Read_IDR(CRC)==~values[i]);
 }
 TCHECK(5, CRC->DR==before_dr && CRC->CR==before_cr);
 FORGE_TEST_END();return 0;
}
'''


class Anchor:
    def __init__(self, ws, monkeypatch):
        self.ws = Path(ws)
        self.store = Store(ws)
        self.results = []
        nodes = {f"swe{i}_{kind}": {"role": f"swe{i}-{kind}", "phase": f"SWE.{i}"}
                 for i in range(1, 7) for kind in ("author", "inspector")}
        self.binding = Binding("idr-six-phase-fixture", str(ws), nodes)
        self.binding.dump(self.ws / ".forge-run/binding.json")
        monkeypatch.setenv("FORGE_BINDING_ID", self.binding.binding_id)
        monkeypatch.delenv("FORGE_MCP_TRUST", raising=False)

    def write(self, phase, files):
        write_scoped(self.ws, files, f"swe{phase[-1]}_author")

    def tool(self, module, server, op, phase, args=None, inspector=False):
        args = args or {}
        kind = "inspector" if inspector else "author"
        node, role = f"swe{phase[-1]}_{kind}", f"swe{phase[-1]}-{kind}"
        name = fabro_tool_name(server + "." + op)
        decision = Authorizer(self.binding).decide(node, name, args)
        assert decision.allow, decision
        ticket = sdk.issue_ticket(self.binding.binding_id, name, args, role, node, phase, str(self.ws))
        result = sdk.invoke(server, next(o for o in module.OPERATIONS if o.name == op), args)
        assert not ticket.exists()
        self.results.append({"phase": phase, "server": server, "op": op, "result": result})
        assert result["status"] == "PASS", result
        return result

    def finish(self, phase):
        reply = {"status": "PASS", "artifacts": [], "issues": [], "next_action": "inspect"}
        assert gate.step_author(self.store, phase, json.dumps(reply)) == 0, (
            self.ws / ".forge-run/gates/gate-log.jsonl").read_text()[-6000:]
        baseline = self.store.latest_baseline(phase)
        # The only verdict substitution: deterministic checks below still execute in the real engine.
        verdicts = {c["id"]: {"verdict": "PASS", "evidence_refs": list(baseline["files"])[:2]}
                    for c in self.store.applicable(self.store.checklist(phase))["checks"]}
        result = self.store.record_inspection(phase, f"swe{phase[-1]}-inspector", baseline["baseline_id"], verdicts)
        assert result["verdict"] == "PASS", result["findings"]
        assert self.store.gate(phase)["decision"] == "PASS"

    def architecture(self):
        reqs = sorted(json.loads((self.ws / ".forge-run/lrtx/SWE.1/assembly.json").read_text())["swr"])
        rows = [f"| {r} | SWC_LL | " + (
            "LL_CRC_Write_IDR" if r == "SWR-001" else "LL_CRC_Read_IDR" if r == "SWR-002"
            else "shared component constraint") + " |" for r in reqs]
        md = """# CRC IDR software architecture
## Components
SWC_LL is the header-only stm32n6xx_ll_crc component; the caller supplies a valid accessible CRC instance.
No HAL, DMA, calculation, polynomial, reversal or generated driver implementation is in this objective.
## Interfaces
| ID | Signature | Responsibility |
| --- | --- | --- |
| IF-01 | void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData) | Write all 32 IDR bits. |
| IF-02 | uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx) | Return the current 32-bit IDR value. |
## Requirement allocation
| SWR | SWC | Function or constraint |
| --- | --- | --- |
""" + "\n".join(rows) + """
## Register table
| Register | Offset | Access |
| --- | --- | --- |
| CRC_IDR | 0x04 | 32-bit read/write temporary storage; RM0486 section26.4.2 p.1172 |
## Timing, concurrency and caller responsibility
Calls perform one direct volatile register access without polling. Caller owns clock, power,
security/access setup and coordination of concurrent writers. No invalid-pointer behavior or
error-return contract is invented. The component has no autonomous startup activity or private
static storage. Whole-component budgets are flash4096, static RAM64 and stack128 bytes.
## Limits
Safety assurance NOT_ASSESSED. Host RAM mapping and behavioral target simulation do not verify
physical clock gating, security attribution or board timing.
"""
        allocated = ", ".join(reqs)
        static = f"""@startuml
component "stm32n6xx_ll_crc" <<SWC>> as SWC_LL
component Caller
component CRC
note right of SWC_LL
 Allocated: {allocated}
end note
Caller --> SWC_LL : IF-01 IDR write/read
SWC_LL --> CRC : IF-02 32-bit CRC_IDR access
@enduml
"""
        dynamic = """@startuml
participant Caller
participant stm32n6xx_ll_crc
participant CRC
Caller -> stm32n6xx_ll_crc : LL_CRC_Write_IDR(CRC, value)
stm32n6xx_ll_crc -> CRC : write CRC_IDR.IDR
Caller -> stm32n6xx_ll_crc : LL_CRC_Read_IDR(CRC)
stm32n6xx_ll_crc -> CRC : read CRC_IDR.IDR
stm32n6xx_ll_crc --> Caller : stored 32-bit value
@enduml
"""
        calls = {"schema": "forge-c/api-calls/1", "calls": {
            "WRITE_IDR": {"function": "LL_CRC_Write_IDR", "args": ["CRC", "0x12345678U"]},
            "READ_IDR": {"function": "LL_CRC_Read_IDR", "args": ["CRC"]}}}
        self.write("SWE.2", {"workproducts/SWE.2/software_architecture.md": md,
                            "workproducts/SWE.2/architecture_static.puml": static,
                            "workproducts/SWE.2/architecture_dynamic.puml": dynamic,
                            "workproducts/SWE.2/api_calls.json": pretty_json(calls)})
        self.finish("SWE.2")

    def implementation(self):
        from forge_factory.inspection.unit_scaffold import misra_statement
        from forge_factory.mcp.servers import analysis, build

        units = """# CRC IDR software units
## SWU-LL-01: independent data register access
- SWC: SWC_LL
- Functions: LL_CRC_Write_IDR, LL_CRC_Read_IDR
- Design: workproducts/SWE.3/detailed_design/SWU-LL-01.puml
- **USPEC-LL-01-01** Store the supplied 32-bit value in IDR without changing other registers. Traces: SWR-001
- **USPEC-LL-01-02** Return the independently preset 32-bit IDR value without changing a register. Traces: SWR-002
- **USPEC-LL-01-03** Perform no status polling for a valid accessible instance. Traces: SWR-004
"""
        design = """@startuml
title SWU-LL-01 CRC IDR
legend top left
USPEC-LL-01-01, USPEC-LL-01-02, USPEC-LL-01-03
endlegend
start
:Caller supplies an accessible CRC instance;
if (API) then (write)
:LL_CRC_Write_IDR stores InData in IDR;
else (read)
:LL_CRC_Read_IDR returns IDR;
endif
stop
@enduml
"""
        trace.seed(self.ws)
        mapped = json.loads((self.ws / trace.SEED).read_text())
        for row in mapped["rows"]:
            row["unit"] = "SWU-LL-01"
            row["uspecs"] = ["USPEC-LL-01-01" if row["function"] == "LL_CRC_Write_IDR"
                             else "USPEC-LL-01-02", "USPEC-LL-01-03"]
        self.write("SWE.3", {"workproducts/SWE.3/unit_specifications.md": units,
                            "workproducts/SWE.3/detailed_design/SWU-LL-01.puml": design,
                            trace.MAP: pretty_json(mapped),
                            "workproducts/SWE.3/detailed_design.md": """# CRC IDR detailed design
The two original frozen ST inline functions implement IF-01/IF-02. SWU-LL-01 and its three
specification items trace to the independent input requirements. The implementation uses the
original CMSIS instance pointer and direct volatile access to IDR; no generated register-array
driver or new implementation is claimed. Caller-owned setup and writer coordination remain
preconditions. The IDR functions do not poll status. Other driver functions are outside scope.
Actual compiler, analyzer, target size and stack records are retained in evidence/tool-results.jsonl.
The measured build unit contains wrappers only and is explicitly not delivered driver logic.
"""})
        for profile in ("host-clang", "target-cm55-gcc"):
            self.tool(build, "forge-build-mcp", "configure", "SWE.3", {"profile": profile})
            self.tool(build, "forge-build-mcp", "compile", "SWE.3", {"profile": profile})
        self.tool(analysis, "forge-analysis-mcp", "cppcheck", "SWE.3")
        self.tool(analysis, "forge-analysis-mcp", "clang_analyze", "SWE.3")
        self.tool(build, "forge-build-mcp", "measure_elf", "SWE.3", {"profile": "target-cm55-gcc"})
        self.tool(build, "forge-build-mcp", "stack_usage", "SWE.3", {"profile": "target-cm55-gcc"})
        misra_statement(self.ws)
        assert gate.step_verify(self.store, "SWE.3", "delivery") == 0
        self.finish("SWE.3")

    def unit(self):
        from forge_factory.mcp.servers import tests

        self.write("SWE.4", {"software/tests/unit/test_crc.c": HOST,
                            "workproducts/SWE.4/unit_verification_report.md": """# IDR unit verification
UT-001 verifies all32 write bits at zero, all ones, alternating and high/low-bit values, with
an unrelated register sentinel. UT-002 presets IDR independently of the write API and verifies
read value and nonmutation. USPEC-LL-01-01/02/03 and SWR-001/002/004 are covered.
The actual host compiler, execution, coverage and exit statuses are retained in tool evidence.
Startup and resource constraints are observed/measured separately, not by a tautological host test.
"""})
        self.tool(tests, "forge-tests-mcp", "run_unit", "SWE.4")
        self.tool(tests, "forge-tests-mcp", "llvm_coverage", "SWE.4", {"level": "unit"})
        self.finish("SWE.4")

    def integration(self):
        from forge_factory.mcp.servers import sim, tests

        self.write("SWE.5", {"software/tests/integration/test_crc.c": INTEGRATION,
                            "software/tests/target/test_crc_idr.c": TARGET,
                            "workproducts/SWE.5/integration_verification_report.md": """# IDR integration verification
IT-001 covers the IF-01 write→IF-02 read interaction of SWC_LL with boundary and alternating
32-bit values. Real host execution and an actual Cortex-M55 Renode target image are required.
The target checks an initial IDR observation, independent read presets, write/read round trips
and unchanged DR/CR observations. The behavioral model assumes an accessible interface; it does
not qualify physical clocks, security attribution, bus timing or a silicon board.
Compiler/tool identities, exit codes and size/stack limits are in the recorded tool results.
"""})
        self.tool(tests, "forge-tests-mcp", "run_integration", "SWE.5")
        self.tool(sim, "forge-sim-mcp", "run_renode", "SWE.5")
        self.finish("SWE.5")

    def validation(self):
        from forge_factory.mcp.servers import tests
        from forge_factory.workflow import robot_scaffold

        robot_scaffold.scaffold(self.ws)
        path = self.ws / robot_scaffold.suite(self.ws)
        text = path.read_text()
        marker = "    " + robot_scaffold.PLACEHOLDER + ": "
        parts = text.split(marker)
        # The seven requirements are fixed by the independently supplied fixture.
        actions = [
            "Run Target Scenario    scn_idr.c\n    Target Check Should Pass    2",
            "Run Target Scenario    scn_idr.c\n    Target Check Should Pass    4",
            "Run Target Scenario    scn_idr.c\n    Target Check Should Pass    1",
            "Run Target Scenario    scn_idr.c\n    All Target Checks Should Pass",
            "Driver Flash Size Should Be At Most    4096",
            "Driver Static RAM Should Be At Most    64",
            "Driver Stack Should Be At Most    128"]
        assert len(parts) == len(actions) + 1, "fixture requirements changed; update and requalify the oracle"
        output = parts[0]
        for action, tail in zip(actions, parts[1:], strict=True):
            _, rest = tail.split("\n", 1)
            output += "    " + action + "\n" + rest
        self.write("SWE.6", {robot_scaffold.suite(self.ws): output,
                            "software/tests/software/scn_idr.c": TARGET,
                            "workproducts/SWE.6/software_verification_report.md": """# IDR software verification
The Robot suite independently observes the two IDR behaviors and startup precondition on the
Cortex-M55 behavioral model and measures the declared4096/64/128-byte resource constraints.
No mocked compiler, simulator, measurement or tool PASS is permitted. Results, coverage, raw
evidence hashes and normal phase trace matrices are retained. This is a deterministic provider-
artifact fixture, not Qwen quality, a legitimate human review or an actual M1 accepted delivery.
"""})
        self.tool(tests, "forge-tests-mcp", "run_robot", "SWE.6")
        self.finish("SWE.6")
