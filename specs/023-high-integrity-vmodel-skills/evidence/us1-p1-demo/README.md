# T041: P1 demo, Safety Supervisor, system and software requirements

Reference configuration: generic profile, HI-2, Claude Sonnet author through Claude Code (`claude -p --model sonnet`,
owner account) and GPT-6.1 Terra inspector through Codex CLI (`codex exec -s read-only -m gpt-6.1-terra`, ChatGPT
login). Runs 1 and 2 used the account defaults (Claude Opus 5.5, GPT-6.2-Sol), before the owner chose Sonnet/Terra.

**Result of record: run 5** (`run5-pass4-accepted/`): a clean consumer project, one package version (`2e21d7bf`) for
all its passes, final state **both stages ACCEPTED** (85 system requirements, 89 software requirements, every gate
PASS, no open finding, no blocking open point), sealed `READY_FOR_OFFLINE_REVIEW` and verified (`../us5-seal/run5/`).

| Run | Models | Passes | Outcome | What it showed |
|---|---|---|---|---|
| 1 (`run1-blocked/`) | Opus / Sol | 1 (stopped) | BLOCKED | needs alone leave values open; inspector rightly marks them unverifiable; rework cannot answer them → `blocked_by` |
| 2 (`run2-blocked/`) | Opus / Sol | 1 | BLOCKED | with demo decisions: 42 of 47 open points blocking; two conductor defects (TR-SUSPECT after set rework, duplicated findings) |
| 3 (`run3-error/`, `run3-blocked/`) | Sonnet / Terra | 1 (+1 error) | BLOCKED | invalid JSON from the author crashed the conductor (fixed); 14 min instead of 2.5 h; author/inspector disagreed on open-point classification |
| 4 (`run4-*`) | Sonnet / Terra | 9 | ACCEPTED both | open-point classification rule; decision rounds 2–8; package fixes between passes (ported RE rules, set-finding identity); sealed `../us5-seal/run4/` |
| 5 (`run5-*`) | Sonnet / Terra | 4 (+1 attempt) | **ACCEPTED both** | clean start on a fixed package; decision rounds 9–11 answered contradictions and gaps the fresh run found |

Run 5 in numbers: 4 passes, 97 model calls (66 author, 31 inspector), 19 min author and 13 min inspector time.
Between passes only the product-decision input changed (rounds 9, 10 and 11: `CON-SUP-137..141`); the conductor
re-authored and re-judged only what those changes affected.

**About the product decisions.** All `CON-SUP-1xx` decisions are fictional demo-product decisions written by Claude,
labelled as such in `examples/safety-supervisor/needs/product-decisions.md` and recorded in `../owner-decisions.md`.
Each round answered only what the package had raised as a blocking open point or a blocking finding. The package
never filled such a gap itself.

Not certification, approval or release under any standard: the sealed package is engineering input for offline human
review.
