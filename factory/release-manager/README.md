# Forge-C v0.3 — Fully autonomous dark factory, offline human review

**Status:** editable process design + a working Python reference packager. **Not** an implemented Fabro workflow; no claim of automotive process compliance, qualified tools, or approved ASIL B software.

The project focuses on ultra-low-memory-footprint C HAL and low-level drivers. Fabro orchestrates local/open-source tools and model agents. Separate review agents inspect each SWE.1–SWE.6 workproduct and generate checklist-based findings. Defects are routed to the responsible author. When a retry budget is exhausted, the run terminates safely and automatically sends its evidence to the Release Manager.

## One continuous unattended execution

1. **Intake** receives immutable target/HSI, requirements, safety allocation, acceptance criteria and resource budgets. Missing authoritative inputs are never invented.
2. **SWE.1–SWE.6** author agents produce requirements, software architecture, design/code, unit verification, software component and integration verification, and software verification artifacts.
3. **Inspect each SWE phase:** an agent with a separate context reviews the frozen workproduct against a versioned checklist. A deterministic gate requires evidence, no unresolved blocking findings, current hashes and complete traceability.
4. **Autonomous loops:** findings return to the originating agent; upstream changes reopen affected descendants. Retry exhaustion, unresolvable ambiguity or unverifiable safety conditions create a terminal `BLOCKED` state, not an interactive human checkpoint.
5. **Release Manager** gathers all C/H, build outputs, ASPICE workproducts, evidence, safety inputs/analyses, inspection records, defects/changes, metrics, traceability, toolchain provenance and limitations.
6. **Deterministic packager** snapshots files, validates configured completeness, computes SHA-256, writes a manifest/gap report/checksums and makes a single ZIP archive.
7. **Offline human review** happens after production of the package; it is **outside the Fabro workflow**. Review, quality assurance independence, safety assessment, deviation acceptance and production-release authorization remain human responsibilities.

Machine output status is one of:

- `READY_FOR_OFFLINE_REVIEW`: configured mechanical checks passed. **Not** safety approved, process certified or production released.
- `BLOCKED`: incomplete/failing evidence, open findings or exhausted retries. **Still generates** a reviewable package with findings and gaps (assuming the artifact storage/packaging environment remains functional).

## Editable diagrams

Open `Forge-C_Fabro_DarkFactory_v0.3.drawio` in <https://app.diagrams.net/>. All seven tabs contain native editable draw.io nodes and connectors:

1. Dark factory architecture — macro workflow, final Release Manager, external offline review.
2. SWE autonomous inspections — six author/inspector/checklist correction loops.
3. Release Manager workflow — collecting, final checks, status branches, package output.
4. OSS bootstrap (implemented demo) — preserved from v0.1.
5. Inspection protocol — independent review, rework and bounded failures.
6. SWE checklist catalogue — 36 v0.2 checklist items.
7. Package inventory + offline review — deliverables and safety boundary.

The package also contains a proposed release policy and a reference `scripts/build_review_package.py` packager with tests. The packager is **not yet wired to Fabro**. The existing v0.1 C demo and build script are not modified.

## Example packager usage

```bash
python3 scripts/build_review_package.py \
  --workspace /path/to/forge-c/run-output \
  --out-dir /path/to/review-archives \
  --run-id example-001 \
  --policy policies/release-package-policy.json
```

On a clean/empty workspace this deliberately generates a `BLOCKED` review ZIP, documenting missing inputs. It does not fabricate evidence.

Run the reference tests using:

```bash
python3 -m unittest discover -s tests -v
```

## Safety and process boundary

This process can generate candidate workproducts and inspection evidence aligned with **Automotive SPICE SWE.1–SWE.6** and supporting SUP.1/SUP.8/SUP.9/SUP.10 processes, and it can gather evidence pertinent to **ISO 26262-6 ASIL B**. Specific information items depend on the agreed process, product scope, safety plan and tailoring. The factory must not claim ASPICE assessment results, organizational independence, tool qualification or ISO 26262 release authorization solely from its agent outputs. ISO 26262 engineering review and release disposition belong to an independent human assessment outside the run.

Reference: [VDA QMC Automotive SPICE PAM 4.0](https://vda-qmc.de/wp-content/uploads/2023/12/Automotive-SPICE-PAM-v40.pdf) and [ISO 26262-6:2018](https://www.iso.org/standard/68388.html).
