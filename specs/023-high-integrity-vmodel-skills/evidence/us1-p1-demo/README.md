# T041: P1 demo, Safety Supervisor, system and software requirements

Reference configuration: generic profile, HI-2, Claude Sonnet author through Claude Code (`claude -p --model sonnet`,
owner account) and GPT-6.1 Terra inspector through Codex CLI (`codex exec -s read-only -m gpt-6.1-terra`, ChatGPT
login). Runs 1 and 2 used the account defaults (Claude Opus 5.5, GPT-6.2-Sol), before the owner chose Sonnet/Terra.

**Results of record:**

- **Run 5** (`run5-pass4-accepted/`). A clean consumer project with one package version (`2e21d7bf`) for all its
  passes. Both stages were **ACCEPTED**: 85 system requirements, 89 software requirements, every gate PASS, no open
  finding and no blocking open point. Sealed `READY_FOR_OFFLINE_REVIEW` and verified (`../us5-seal/run5/`).
- **Run 6** (`run6-pass5-accepted/`, T087). A clean project with the **governance step**: 6 actors and 12 use cases
  covering all 15 needs, written before any requirement. It also adds the set coverage matrix and the open-point id
  check. Both stages were **ACCEPTED**: 93 system requirements, 104 software requirements, every gate PASS including
  `governance`, no open finding. Sealed READY with 81 files and verified (`../us5-seal/run6/`).

  Unlike run 5, the package changed between run 6's passes. Each pass found something, and it was fixed with a test
  before the next pass: a finding waiting on a governance open point, coverage rows already tracked by a finding, and
  open-point id reuse. The package version of each pass is in the demo project's git log and in its pass folder.

| Run | Models | Passes | Outcome | What it showed |
|---|---|---|---|---|
| 1 (`run1-blocked/`) | Opus / Sol | 1 (stopped) | BLOCKED | needs alone leave values open; inspector rightly marks them unverifiable; rework cannot answer them → `blocked_by` |
| 2 (`run2-blocked/`) | Opus / Sol | 1 | BLOCKED | with demo decisions: 42 of 47 open points blocking; two conductor defects (TR-SUSPECT after set rework, duplicated findings) |
| 3 (`run3-error/`, `run3-blocked/`) | Sonnet / Terra | 1 (+1 error) | BLOCKED | invalid JSON from the author crashed the conductor (fixed); 14 min instead of 2.5 h; author/inspector disagreed on open-point classification |
| 4 (`run4-*`) | Sonnet / Terra | 9 | ACCEPTED both | open-point classification rule; decision rounds 2–8; package fixes between passes (ported RE rules, set-finding identity); sealed `../us5-seal/run4/` |
| 5 (`run5-*`) | Sonnet / Terra | 4 (+1 attempt) | **ACCEPTED both** | clean start on a fixed package; decision rounds 9–11 answered contradictions and gaps the fresh run found |
| 6 (`run6-*`) | Sonnet / Terra | 5 | **ACCEPTED both** | governance step first time right; coverage matrix in real use; decision rounds 12–15 (CRC layout and range ends, a fault report during an answer, the start-up message deadline, equality with a timing limit); three conductor defects found and fixed |

Run 6 in numbers: 5 passes, 109 model calls, 27 min author and 33 min inspector time (system requirements alone: 91
calls, 49 min). Run 5 in numbers: 4 passes, 97 model calls (66 author, 31 inspector), 19 min author and 13 min inspector time.
Between passes only the product-decision input changed (rounds 9, 10 and 11: `CON-SUP-137..141`); the conductor
re-authored and re-judged only what those changes affected.

**About the product decisions.** All `CON-SUP-1xx` decisions are fictional demo-product decisions written by Claude,
labelled as such in `examples/safety-supervisor/needs/product-decisions.md` and recorded in `../owner-decisions.md`.
Each round answered only what the package had raised as a blocking open point or a blocking finding. The package
never filled such a gap itself.

Not certification, approval or release under any standard: the sealed package is engineering input for offline human
review.
