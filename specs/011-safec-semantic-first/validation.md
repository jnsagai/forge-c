# Validation ledger — Feature 011

**Status as of 2026-10-22: SPECIFICATION_ONLY.** There is **no** completed implementation, local model trial, SafeC Linux run, safety qualification or live full regression evidence from Feature 011.

## Verified GitHub provenance (metadata, not host deployment)

| Item | Result |
|---|---|
| Forge-C source selected | Main `2f4b9cf44fd9cc56648fa26b6da6c2e29248338d`, merge commit of PR #34, recorded through connected GitHub |
| New branch | `feat/011-safec-semantic-first` created at that commit |
| Existing baseline | `baseline/codex-claude-2026-10-21` pinned to `86f1f40c030bc721e7e5125a572d69647c4ac041` in ADR-0013 |
| SafeC discovery ref | Private main `556dca8df4d2fccd9cb59fd8fb0432aafdd05835`; executable binary/runtime hash NOT_VERIFIED |
| T024 baseline | 13/30 run, 0 READY, 8.41 h / 640 calls / 204 Wh GPU-board only; NOT_PASS, not a 30-case result |
| T021 baseline | 1/7 on-target inspections, 2/2 false clean rejections; limited catalogue, not a qualification |

## Checklist of required engineering evidence

| Check | Status | Required evidence path/pointer when implementation occurs |
|---|---|---|
| New schemas/Spec Kit content readable in GitHub | SPEC_WRITTEN, NOT_RUN through local validator | `specs/011-safec-semantic-first/` |
| Existing ACP/default/Feature 010 compatibility | NOT_RUN | test command/digest/exit in isolated evidence |
| SafeC Linux build/probe and license inventory | NOT_RUN | Separate private SafeC trial + public-safe identity/result pointer |
| Python/Rust bridge conformance and adversarial tests | NOT_RUN | Per-task evidence for F011-AT-006..010 |
| Register-io authoritative semantic fixtures | NOT_RUN | F011-AT-011..016 |
| Local SWE.1 RCC/IWDG runs | NOT_RUN | F011-AT-017,025 |
| Independent inspector qualified on holdouts | NOT_RUN | F011-AT-019..023,030 |
| SWE.2 and SWE.3..SWE.6 integration | NOT_RUN | F011-AT-024,026..029 |
| Offline 30-case v2 campaign | NOT_RUN | F011-AT-032 |
| Actual machine isolation, archive verification and rollback | NOT_RUN | F011-AT-001..005,033 |
| Assurance/release/ASIL acceptance | NOT_GRANTED | External offline authority and mandatory evidence |

**Rule:** No checklist may be ticked based on proposal text, model narrative or unsupported simulation. Refresh this ledger with exact hashes, tests, failures and limitations after each implementation milestone.
