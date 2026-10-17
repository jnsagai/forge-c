# Feature 006 (EASA) operations guide

Feature 006 adds independent engineering checks to SWE.1–SWE.6. It is bounded engineering evidence for offline human
review. It is not an ISO 26262 or Automotive SPICE conformance statement, not an ASIL approval and not a safety
sign-off. It adds no SUP/MAN workflow.

## 1. What runs, and where

| Where | What | Can it change an outcome? |
|---|---|---|
| SWE inspection gate (`inspection/gate.py step_inspect`) | `assurance/observe.py`: the assurance gate for the phase. It uses recorded MCP tool results plus the independent verifiers in `assurance/verifiers.py`, and appends to `.forge-run/assurance/gate-log.jsonl` with reports under `.forge-run/assurance/reports/` | No. It is observe-only and the 002 decision stands. |
| SWE.2–SWE.6 author gate, trace-profile work orders only | `inspection/swtrace.py` checks the phase's trace relation and writes its matrix into `workproducts/SWE.n/traceability/` | Yes, as the existing presence gate: missing links block the freeze. This is the owner addendum of 2026-10-17. |
| SWE.3 chain, trace profile only | `inspection/unit_scaffold.py` (node `swe3_units`) generates the unit-spec skeleton, the as-built PlantUML designs and the MISRA deviation statement from facts | No. It generates; the author must replace the markers. |
| Finalizer (`release/finalize.py`) | `assurance/package.py` adds `assurance/` (gate log, independence, applicability, fidelity, claims, hashes) and `configuration/model-profile.json` | Only in ENFORCING mode, through the existing `open_findings` rule of the unchanged v0.5 release policy |
| Dashboard | `/api/v1/assurance/*` and the Assurance section of the existing page | No (read-only) |

Work orders prepared from now on carry `"trace_profile": "owner-2026-10-17"` in `.forge-run/manifest.json`. Older work
orders and test fixtures keep their original rules.

## 2. Commands

```sh
. scripts/forge-env.sh
python -m forge_factory.assurance.baseline --out <file>         # capability matrix, tools, locked references (T001)
python -m forge_factory.assurance.regress --full --out <file>   # regression + negative controls (T004)
python -m forge_factory.assurance.compat --out <file>           # migration on a DB copy, frozen files (T007)
python -m forge_factory.assurance.audit <zip> --out <file>      # read-only frozen baseline manifest (T003)
python -m forge_factory.assurance.matrix                        # FR -> task -> AT -> evidence status (T071)
python - <<'EOF'                                                # copy-based shadow audit of a sealed package (T064)
from forge_factory.assurance import shadow; print(shadow.run(ZIP, RM_INPUTS_DIR))
EOF
```

Task status comes only from `evidence/v0.4/runs/EASA-T*/latest.json`; see `docs/assurance/EASA-STATUS.md`. The
authored `tasks.md` keeps its boxes unchecked by design, because `validate_spec.py` counts them.

## 3. Rollout: OBSERVE_ONLY → PILOT → ENFORCING

- **Today:** `config/factory/assurance-policy.yaml` is absent, so the built-in example policy applies: OBSERVE_ONLY,
  profile ENHANCED.
- **To change the mode:**
  1. Write the policy file.
  2. Have a human approve its sha (`policy.approve`).
  3. Request the mode with `policy.request_mode`.
  - PILOT needs a human authorization block.
  - ENFORCING also needs a PASS pilot record with a measured false-positive and false-negative rate and an independent
    human review.
- An agent can do none of this.
- A policy that isn't approved, or doesn't parse, is never loaded; the previous one stays active.

## 4. Oracle independence

- A test oracle counts as independent only if it is derived from the frozen requirements and the baselined reference
  manual (`assurance/oracle_gen.py`, literal RM constants) and never sees the implementation.
- An oracle that uses symbols defined by the code under test, copies a value from it, or was written by an author role
  is `CONTAMINATED` (`assurance/oracle.py`). The sealed r101/r102 unit tests are this case: their expected values are
  the generated macros (audit finding F-01).
- The same model for author and inspector is recorded as common cause (`independence.py`): PARTIAL, not SUPPORTED.
- Holdout expectations live in a vault owned by the verifier sub-UID (rootless Podman). Author processes are refused by
  the policy check and by the kernel.

## 5. Normative status

- The ISO 26262-6:2018 method list is a 47-entry provisional secondary working index.
- No licensed copy is registered, so normative verification is BLOCKED.
- The procedure to change this is in `docs/assurance/normative-reconciliation-plan.md`.

## 6. Decisions that only the owner can take

1. **Product safety scope of the RCC work orders (QM or ASIL) as an approved record (`.forge-run/safety_scope.json`).**
   - Without it, the two safety documents stay required and every package stays BLOCKED.
   - With an approved QM scope (human approver, written rationale), the package states the documents as not applicable.
     The unchanged release policy can then give READY_FOR_OFFLINE_REVIEW. This was measured on a copy of sealed r102.
2. **Registering a licensed ISO 26262-6:2018 copy, and a competent reviewer's per-table reconciliation.**
3. **PILOT authorization for EASA**, after reviewing the dry-run and corpus measurements in `evidence/easa/measurements/`.
4. **Recording a different model or provider per role**, if author/inspector independence beyond PARTIAL is wanted.
