# Target-test prompt follows the declared API

Source `d0090099c2961c71aa28623b53eda03e790e3ea2` fixes one observed prompt
contradiction. It is **NOT_ACTIVATED** on Omniverse. Current native05 and the
prepared repeatability cohort retain producer0e342eef/profile3/auditor30371da5.
No active workspace, model, candidate or steering input was changed.

## Actual native observation

Native `01M67R1HNE9TKPWCYJ2SVKEPJS` first ran its SWE.5 tests at02:41:17UTC:
two images failed compilation because `ll_crc_regs` and `LL_CRC_*_OFFSET`
declarations were absent. No executable assertions ran in that failed attempt.
At02:43:15UTC Qwen's revised tests passed33simulated checks across two images.
The driver remained9aa11db1... throughout. This is a job-local test adaptation,
not an implementation repair or autonomous factory-source healing.

The accepted tests add local offset definitions and a typed access wrapper around
the simulator linker symbol. They do not wholly switch to the declared device
API. Original failed/passed protected test sources and hashes are included here,
alongside exact selected tool outputs and their protected-history records. The
files were read/copied/hashed locally; Qwen C was not executed locally. Simulation
is not physical silicon or hardware WCET. Independent preregistered630host/
351target checks remain separate; counts are not added to the33authored checks.

## Small framework fix and verification

The generated target-author prompt still explicitly requested the legacy array
and offset-macro interface. A new regression reproduced that contradiction
before the change (1FAIL). The opt-in Delivery-First graph now reads the frozen
contract, actual candidate headers and device inputs, and uses their exact
prototypes, valid instance arguments and declared simulator fidelity. It keeps
the mailbox/TCHECK protocol, actual `run_renode` invocation, failure correction,
trace and defect reporting. No target-specific API is added to shared policy.
The original strict target prompts and graphs remain unchanged.

Focused checks2PASS. Exact combined framework/finalizer/provenance/strict-release
cohort **95PASS,0failures/errors/skips**, tested atd0090099. These cohorts overlap
earlier88tests and must not be added. Tests use supplied synthetic fixtures,
not Qwen products. All five actual strict graph hashes match before/after;
the inherited Feature009 golden mismatch is preserved, not rewritten or waived.
Final scoped Ruff PASS. Specification/contracts PASS is static documentation
validation, not runtime qualification or a measured prompt-benefit result.

`source-qualification.json` records commands/revision/results.
`receipt-representations.json` distinguishes original JUnit bytes (deterministic
gzip) from readable views with trailing whitespace stripped and a final newline.
No historical receipt, sealed archive or run verdict was rewritten.

This supports DF-T007 implementation. DF-M1 terminal audit and DF-T010 execution
remain pending; original DA ledger30/58 is unchanged. No full LL/HAL, production,
assessed ASPICE, generic-driver, learning-benefit or24/7 qualification is claimed.
