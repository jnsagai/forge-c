# Owner review: four ST HAL onboarding handovers

All four current packages are sealed **BLOCKED** handovers. They are ready for offline review, not accepted driver
releases. [record.md](record.md) and [record.json](record.json) retain all six attempts, signatures, revisions,
archive hashes, every named gap, phase verdicts, timing and available token counters. Recovery tokens remain UNKNOWN
where the native record supplies no measurement.

| Current request | Gaps | Last completed inspection | Stop |
|---|---:|---|---|
| BENCH-GPIO-ST-HAL-OB-R1 | 709 | SWE.3 PASS | SWE.4 runtime unit failures and uncovered USPECs |
| BENCH-SPI-ST-HAL-OB-R1 | 310 | SWE.3 PASS | SWE.4 runtime unit failures and uncovered USPECs |
| BENCH-USART-ST-HAL-OB | 711 | SWE.3 PASS | SWE.4 runtime unit failures and uncovered USPECs |
| BENCH-TIM-ST-HAL-OB | 230 | SWE.3 PASS | SWE.4 runtime unit failures and uncovered USPECs; coverage export unavailable |

The archive and current owner-approval bindings pass `OB-T058`. Cited reviews of the latest packages identify no
wrong or missing onboarding fact as a cause of these blockers (`OB-SC005-LATEST`). This is a source-cited assessment,
not an automatic proof that every generated requirement or CODE diagnosis is correct. The historical SC-005 check
still FAILS on the original GPIO RM-field omission; the initial GPIO and SPI failures remain visible.

Review the generated requirements before accepting the reported CODE diagnoses. In particular:

- GPIO: the BSRR requirement and the delivered BRR reset operation may need requirement adjudication despite their
  related hardware effects; analog pull behavior, invalid arguments and before-init behavior also have findings.
- SPI: reports concern invalid configurations, NSS/SSI, receive completion and timeouts. The original factory DMA
  probe include-context defect was fixed through CRE; R1 passed SWE.3 on that fix.
- USART: reports concern NULL handles, invalid configurations, timeout boundaries and BRR configuration. The generated
  representable-nonzero BRR premise and exact timeout deadline need review against RM/API constraints. The owner-signed
  clock assumption remains 64 MHz; no new clock approval is requested.
- TIM: reports concern NULL handles, invalid configurations/events and temporary CR1.URS writes. The driver restores
  CR1 after generating an update. Final RAM tests cannot establish intermediate-write behavior or silicon timing.

TIM additionally retains FACTORY DEF-008: pinned LLVM 19.1.7 rejects its coverage mapping as truncated. The read-only
replay in `OB-TIM-COVERAGE-REPRO` reproduces the symptom. Its root cause and repair remain unverified; coverage metrics
are unavailable. A repair needs its own controlled reproducer, CRE decision and fresh acceptance request. No delivered
ST file, failing expectation, raw archive or gate verdict was changed to clear a finding.

Strict literal SC-001 history remains FAIL because an unused legacy GPIO model-description string changed. The
active-input/text generation audit passes and reads no hand profile. This scope exception needs owner adjudication;
it has not been silently relabeled or removed from history.

The missing-model authoring graph is implemented and has deterministic tests. Its held-out CRC authoring/inspection
result (SC-007 / OB-T043) is **NOT_RUN** because the owner reported Claude token exhaustion. No inspector was
substituted. Candidate `129d786c06818db1d475c8a8b123b5571f0a752d` has CRE decision
`pd-993fb0e765714c0494a8` eligible for offline review; it has not been deployed. Production remains on `9dd5b71`.

The owner must decide the disposition of each BLOCKED handover and the strict SC-001 exception. Accepting an offline
handover does not resolve its defects or constitute safety approval. No owner release-disposition record has been
created, and no merge is authorized. This review is required by OB-T060 and handoff §4.5–§4.6; prior onboarding
signatures approve the input packages, not these later release outcomes.
