# CR-T044: live validation (feature 007)

Recorded 2026-10-19 on port 8766, against the real state directory. The owner's 8765 dashboard was untouched.

## Live work order: LL r168

- **Configuration:** Codex Sol 6.1 authors and, for the first time, Claude Opus 5.5 inspectors and Release
  Manager. Launched from a frozen worktree at c9f836a with a HEAD guard; Fabro run `01M5AA11S73CDV5Q9AQ9SVWM6T`.
- **Live board:** the Control Room showed r168 as soon as it started (factory status PRODUCING, unit at SWE.1
  RUNNING, current node `swe1_author`, author and inspector models shown). The unit then moved through the
  stations, reached Shipping and was listed under "shipped in the last 24 h" with its cause.
- **Outcome:**
  - All six first inspections PASS, every one by Claude Opus 5.5. First-pass result per station: PASS ×6.
  - 3 rework cycles at the author gate (SWE.1, SWE.2 and SWE.4); lead time 34 min.
  - Package BLOCKED with exactly 2 gaps: `safety/software_safety_analysis.md` and
    `safety/tool_assurance_assessment.md`, the safety documents the owner postponed. No engineering-phase gap.
- **Usage, all reported (0 stages not reported):**

  | Model and role | Stages | New tokens | Cache reads |
  |---|---|---|---|
  | Codex Sol 6.1, author | 13 | 15.6 k | 455 k |
  | Claude Opus 5.5, inspector | 6 | 11.6 k | 1.27 M |
  | Claude Opus 5.5, release | 1 | 0.4 k | |
  | DeepSeek flash, author (`swe4_test_author`, not in the ACP author set) | 1 | 60.6 k | |

  This is the first run whose Codex author usage is measured, through the proxy recording added by feature 007.
- **Screenshot:** `control-room-after-r168.png` (all panels, 1440 px).

## SSE latency (SC-001)

`latency100.py` appended 100 recorded station changes and measured the time until the stream showed each one,
over a real loopback server with fixture data. Result: 100 of 100 within 5 s; p50 1.005 s, p95 1.008 s,
max 1.027 s. Raw data: `sse-latency-100.json`.
