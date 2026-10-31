# Findings from the standalone SWE.1 run (2026-10-31)

Reviewer notes on the subagent's run report (README.md). These are observations for the CRE register, not claims of
qualification.

1. **Workspace-copy isolation defect: CAPA-075 / RPR-074.** A copied `.forge-run/binding.json` made scoped writes
   in the copy update the source's development-phase state. The source's bytes were unchanged, but one mtime
   changed. Fix: `visit.write_scoped` re-roots the binding at the written workspace (CRE candidate on
   `feat/014-process-lab`). The copy's `durable-binding.json` also still binds the copy to the source's AFO job.
   The inspect step removed it from the scratch copy only (accepted: the run is standalone by design, D13). Copy
   tooling should drop or re-root it explicitly. That is a follow-up, not fixed here.
2. **The inspector's repair can turn findings into a clean PASS.** For SWE1-01 and SWE1-03, Qwen's first answer
   was "PASS with findings", which the validator rejects as inconsistent. The repaired answer was "PASS with no
   findings", so the findings were dropped instead of the verdict changing to FAIL. Their text was not kept. This
   is an inspection-integrity risk: the localized repair asks for consistency, and the model chose the
   lower-effort way to become consistent. Proposed follow-up: a CAPA candidate that keeps the rejected first
   answer's findings in the inspection record, plus a repair instruction or rule that a dropped finding needs a
   stated reason (or that "PASS with findings" re-asks as FAIL-or-withdraw per finding). Not acted on yet.
3. **The trial-06 profile inspects at medium effort.** The delivery-first profile has no `swe1-inspector`
   role effort, so the inspector ran at the profile's default `medium`, not the `xhigh` used by the ASPICE
   profiles. A process-lab comparison has to pin the inspector effort explicitly (design rev 4 §12 does).
4. **`modelcmp` is not a work order.** It skips the profile's model allow-list, lesson retrieval and per-task call
   allowances (Ornith was accepted under a Qwen profile). Its results show that the code path works. They do not
   measure work-order behaviour.
5. **The scope is very small.** One register (CRC_IDR), two model tasks. The 8–11 requirements include 5 budget
   rows the factory builds without a model call. This shows the factory runs end to end. It says nothing about
   capability on larger drivers.
