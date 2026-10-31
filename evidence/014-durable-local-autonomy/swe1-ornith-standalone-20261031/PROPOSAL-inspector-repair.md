# Proposal (owner decision needed): inspector repair can drop findings

**Observed.** In the standalone run (FINDINGS.md item 2), Qwen's first answer to SWE1-01 and SWE1-03 was
`verdict: PASS` with findings attached. `lrtx/review.validate_verdict` rejects that combination
(`review.py:203-204`, "a PASS verdict carries no findings (use FAIL when a finding exists)"). The localized repair then
returned `PASS` with **no** findings: the model resolved the inconsistency by dropping the findings, not by switching
the verdict to FAIL.
- The rejected answer's findings are not stored, because a checkpoint attempt keeps `errors`, `usage` and `input_hash`
  but not the rejected `doc`. Nobody can audit them now.
- The inspection gate then passed on the repaired answers.

**Why it matters.** The inspector is the factory's only semantic check before the oracle exists. A repair path that
lets the model silently drop findings turns "the model saw a problem but formatted it wrong" into a clean PASS.

**Options. All three keep the rejected answer's findings in the checkpoint attempt, so they can be audited.**

| Option | Mechanism | Trade-off |
|---|---|---|
| A. Record only | Store the rejected `doc` in the attempt. The inspection record lists "findings withdrawn in repair" per item. The gate is unchanged. | No behaviour change. A human sees what was dropped, but a PASS stays a PASS. |
| B. Withdrawal needs a reason | The repair message asks, for each earlier finding, to either keep it (verdict FAIL) or withdraw it with a one-line reason tied to evidence. A repaired PASS that drops findings without reasons is invalid again (bounded by the existing repair budget). | Keeps the model in charge of judgement but makes dropping explicit. Costs one more structured field. If the repair budget runs out, the item is NOT_INSPECTED rather than PASS. |
| C. PASS with findings counts as FAIL | The inconsistent answer is read as FAIL with those findings, and no repair is asked. | Deterministic and conservative, but it may raise false rejections where the model listed harmless notes as "findings". Calibration shows false rejections are already the inspector's main weakness (5/9 and 2/2). |

Any of these is a factory change and goes through CRE: a reproducer built from a scripted inspector answer, a
CAPA, then the promotion gate. Nothing has been implemented yet.
