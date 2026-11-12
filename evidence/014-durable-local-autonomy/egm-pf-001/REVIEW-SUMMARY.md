# PF-EGM-001 — EGM review summary

Date 2026-10-31. Target `docs/designs/forge-c-process-first-ornith-qwen.md` (832 lines, drafted with egm-draft
section gates; owner decisions D1–D5). Plugin egm 0.1.0 @403d888, Claude Code 2.1.316 ([PREFLIGHT.md](PREFLIGHT.md)).

| Stage | Reviewers (fresh native subagents) | Result | Report |
|---|---|---|---|
| 5 Initial Zoom Out | egm-zoom-out | 2 B / 12 M / 6 N | [zoom_out_report.md](zoom_out_report.md) |
| 6 Comprehension | egm-comprehension | 0 B / 11 M / 10 N | [comprehension_report.md](comprehension_report.md) |
| 7 Critic | egm-design, egm-structural, egm-style | 4 B / 17 M (deduplicated) | [critic_report.md](critic_report.md) |
| 8 Intermediate Zoom Out | egm-zoom-out | 1 B / 4 M / 2 N | [intermediate_zoom_out_report.md](intermediate_zoom_out_report.md) |
| 9 Implementation Readiness | egm-implementation-readiness, egm-codebase-details, egm-style | 10 B (deduplicated) | [implementation_readiness_report.md](implementation_readiness_report.md) |

Mode: interactive, all rubrics, one round per stage. The owner chose "proceed" at stages 5–8 and "Conclude review and
finalize document" at Stage 9. **egm-resolve was NOT run** and no finding was fixed or contested. The design text is
unchanged from the reviewed revision apart from its status line.

## EGM design gate (plan §8.2): BLOCKED

Open Blockers in the gate's own categories (Elephant code checks in the stage reports):
- **Incorrect state machine / non-runnable swap:** C7-B3, R9-B3 (`stack.start` fenced to RUNNING; managed profile
  pinned in units).
- **Role batching / attempt carry-over impossible under D1:** S5-B1/B2, C7-B1/B2, R9-B1/B2/B6.
- **Fake acceptance risk:** C7-M4, R9-B8 (scorer matching undefined).
- **Hidden oracle / reference leakage:** R9-B10 (0014g inputs carry reviewed requirements and oracle C), C7-M6 (lesson retrieval).
- **Unadmittable configuration:** R9-B4 (no Ornith role-capability path), R9-B5 (QM purpose refuses the stepwise inspector).
- Standard compliance: C7-B4 (no Risks & Mitigations).

The reviewers' main recommendation (Z8-B1) is to reopen D1: one order per (driver, role), one stack session per role
batch, and the swap done by the existing operator profile activation (`mtp-speed-20261030/activate.py`, a one-off
script to promote into a tested tool). Phase 1 would be Qwen-only; Ornith comes in phase 2 after a feasibility check
(Z8-M3). Fixes that stay valid under any shape: G3 identity hash via `role_capability.IDENTITY` + profile sha (global,
with G7 amended), `evaluation_holdout` on lab orders, a single `OLLAMA_CONTEXT_LENGTH`, and `criteria_result` only in
the score report.

Status: **EGM_REVIEW_RUN, resolution NOT_RUN, design NOT approved.** No code implemented, no model run, no deployment.

## Update 2026-10-31 — resolution and targeted re-review

- **Resolution.** The owner ran egm-resolve and chose auto accept. Owner decisions: D1′ (one order per (driver,
  role)), D6 (both arms now), D7 (QM purpose plus a lab-scoped exception), D8 (cut the corpus layer, keep the
  oracle-hash guard), D9 (global G3). Revision 2 was written, and revision 1 is kept as `design-r1-as-reviewed.md`.
  See [goldfish_review_report.md](goldfish_review_report.md).
- **Targeted re-review.** Three fresh reviewers. RC-9 resolved; RC-4–RC-6 down to Majors; 7 deduplicated Blockers
  open in RC-1, RC-2, RC-3, RC-7 and RC-8. See [targeted_rereview_report.md](targeted_rereview_report.md).
- **Cap.** Plan §8.2.4 allows one cycle plus a targeted re-review, and that cap is reached. The owner chose
  **accept and proceed**: revision 2 is frozen with its open Blockers recorded, and only unaffected increments may be
  implemented, starting with G3.

Status: **EGM_REVIEW_RUN, RESOLVED_ONCE, TARGETED_REREVIEW_RUN; design gate still BLOCKED for lab intake, activation,
admission, scoring and leakage; G3 increment cleared to start.**
