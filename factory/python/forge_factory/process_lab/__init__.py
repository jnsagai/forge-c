"""Process-first lab (docs/designs/forge-c-process-first-ornith-qwen.md, revision 4).

SWE.1-only, single-role work products scored against a frozen oracle. Phase 1 (owner decision D13, 2026-10-31) runs
standalone on the real structured SWE.1 code; AFO integration follows later. Nothing here deploys, admits or sends a
model request on its own.
"""
from __future__ import annotations

MODE = "QM_PROCESS_LAB"
