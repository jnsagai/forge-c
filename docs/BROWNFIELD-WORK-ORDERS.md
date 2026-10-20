# Brownfield work orders (feature 008)

A brownfield work order starts from code that already exists: a vendor driver, a supplier delivery or legacy code.
You bring three things:
- the reference documents (datasheet / reference manual sections);
- the existing C code;
- a scope.

The factory produces the remaining ASPICE SWE.1–SWE.6 and ISO 26262 software work products around that code, and
judges the code against requirements it derives **independently** from the reference documents.

Spec Kit: `specs/008-brownfield-work-orders/`. Examples: `examples/0008a-rcc-ll-delivered`,
`examples/0008b-rcc-hal-delivered`, `examples/0008c-st-cube-rcc`.

## Bringing a delivery

Add a `delivery` block to the example's `workorder.json`. The contract is
`specs/008-brownfield-work-orders/contracts/brownfield-workorder.schema.json`.

| Field | Meaning |
|---|---|
| `code_mode` | `FROZEN` (never changed) or `FIX_ALLOWED` (changed only to fix a CODE defect) |
| `origin`, `licence`, `licence_allows_modification` | Where the code comes from and what its licence allows. Missing values, or FIX_ALLOWED under a licence that forbids modification, are refused at intake. |
| `source` | Directory or `.tar.gz`. It may use `$FORGE_DATA_ROOT`. Vendor downloads live under `$FORGE_DATA_ROOT/inputs/` with a `provenance.json`. |
| `files` | Delivered file → workspace path (`software/ll|hal|src/...`) |
| `scope.functions` | The functions or macros the work order covers. Every other function is listed as excluded. |
| `dependencies` | Vendor headers the code needs (e.g. CMSIS), copied read-only to `inputs/vendor/include/` |
| `build` | `style` (`forge` = factory register-array style, `cmsis` = vendor CMSIS style), `defines`, `secure` |

Intake only (no agents):

```bash
python -m forge_factory.workorder --example examples/0008a-rcc-ll-delivered --wo WO-X --intake-only
```

## What happens in a run

1. **Intake** (before any agent):
   - the delivery is checked against the contract;
   - every file is fingerprinted and stored read-only **outside** the workspace (`state/workorders/<wo>/delivered/`);
   - the scope is resolved to real functions;
   - the code is build-checked (host clang for `forge` style, `arm-none-eabi-gcc` for `cmsis` style).

   Any failure stops the work order with a named `DELIVERY_*` issue.
2. **SWE.1 without the code:**
   - The requirements are written from the reference documents and the scope while the workspace holds no
     delivered code.
   - Requirement authors are also denied read access to the delivered paths.
   - The node `delivery_inject` writes the code into the workspace only after the SWE.1 inspection passes. It records
     the frozen SWE.1 baseline in `.forge-run/delivery/injection.json`.
3. **SWE.2 / SWE.3 describe the delivered code as it is:**
   - The architecture, the detailed design and the unit specifications are recovered from the code.
   - The code carries no trace tags, so `workproducts/SWE.3/code_trace_map.json` maps each scope function to its
     unit and unit specification items. The factory seeds it and checks it.
   - No code generator or code author runs.
4. **Conformance** (`.forge-run/delivery/conformance.json`) compares, for every requirement case, the register effect
   the requirement states with the effect the delivered function actually has. Set/clear alias registers are mapped
   to their base register bits. Findings:
   - `NO_CODE`: no delivered function implements a requirement case;
   - `NO_REQUIREMENT`: a scope function implements nothing that is required;
   - `CONTRADICTION`: wrong register, wrong bit, wrong operation, extra writes, or overwriting a shared register.
5. **SWE.4–SWE.6:** tests are written from the requirements and unit specifications. A failing test on delivered code
   is a CODE defect:
   - **FROZEN:** escalated to the owner, with no rework loop;
   - **FIX_ALLOWED:** the fix author may change the delivered file **only** while that CODE defect is in fix, only
     inside scope functions, and never by adding a file.
6. **Packaging:**
   - `configuration/delivery.json` and `delivery/` (intake, scope, injection, conformance, verification, change
     report) go into the package;
   - the fingerprints are re-checked;
   - every open conformance finding, fingerprint mismatch, escalated defect and (FROZEN) delivered-code check
     finding is an unresolved finding, so the package is BLOCKED until the owner disposes of it;
   - safety drafts are generated in `safety/drafts/` (unsigned, never at the signed paths).

## Limits (current)

- **CMSIS-style deliveries (the ST pilot):**
  - intake, the build check, scope resolution and conformance work;
  - the SWE.3 checklist items that assume the factory's own code style (Cube2 guideline, `LL_RCC_*` register
    defines, LL implementation rules) fail on vendor code. The adapted checklist version is a protected change and
    needs an owner decision;
  - host and simulator test harnesses for CMSIS register access (host device shim, Renode set/clear registers) are
    not built yet.
- **Resume:** a brownfield work order cannot be resumed from another work order (the code must enter after a SWE.1
  frozen in the same work order).
- **Owner decisions by example name:** the safety scope and the owner dispositions apply per example name. The new
  examples are not covered until the owner extends them.
