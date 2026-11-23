# forge-c-hi: measured impact (T073)

Protocol: `../evaluation/PROTOCOL.md`, committed at 2026-11-22T17:46Z, before the first evaluation run (17:48Z). The
targets below were written there and have not moved. All runs are recorded in `eval/*.json`. Every number comes from
the package's own deterministic code, applied the same way to every arm. Nothing here is a certification or a safety
claim about any product.

## Reading guide

- **Reference models:** author Claude Sonnet through Claude Code (`claude -p --model sonnet`); inspector GPT-6.1 Terra
  through the Codex CLI (`codex exec -m gpt-6.1-terra`). No API keys were used. The exception is runs 1–2 and
  baselines 1–2, which used the account-default models and are labelled so.
- **Inputs:** the fictional Safety Supervisor example: 15 stakeholder needs, 7 constraints, and product decisions.
  The product decisions are **fictional and were written by Claude**. They were added in rounds, each answering the
  open points a run stopped on (rounds 1–12, CON-SUP-101..144). Each run's input hashes are in its record.

## 1. Requirement quality (SC-006): MET

Metric: deterministic quality-rule violations per 100 requirements (`hi quality sys-req`), the same rules for both arms.

| Arm | Models | Inputs | Items | Violations / 100 | Trace coverage |
|---|---|---|---|---|---|
| baseline 1, plain prompt | Claude Code default | needs, constraints | 46 | 39.1 | 100 % |
| baseline 2, plain prompt | Claude Code default | + decisions | 46 | 47.8 | 100 % |
| **baseline 3, plain prompt** | **Sonnet** | **+ decisions** | 55 | **38.2** | 100 % |
| with package, run 2 | Claude / GPT default | + decisions | 90 | 1.1 | 100 % |
| with package, run 4 | Sonnet / Terra | + decisions | 58 | 0.0 | 100 % |
| **with package, run 5** (result of record) | **Sonnet / Terra** | **+ decisions** | 85 | **0.0** | 100 % |

- **Target:** with the package, at most 50 % of the baseline. **Result:** 0.0 against 38.2 on the same model.
- **Baseline 3's violations:**
  - 17 requirements with more than one "shall";
  - 3 numbers without a unit;
  - 1 heuristic multiple-obligation.
- **Run 2's 1.1:** one violation of the open-point rule, which was added after run 2 and applied to it afterwards.

What the baselines do that the rules cannot see:
- None of them raised a single open point, so every gap in the needs was filled with a value.
- The package runs stopped on those gaps instead, as **blocking open points**, and asked for a decision. The first
  clean run (run 2) stopped on 42 of them.

That is the intended behaviour ("no invention"), and it is the main reason the package runs needed decision rounds
and more than one pass.

## 2. Seeded-defect detection (SC-005): MISSED on the pre-registered metric

**Corpus** (`../evaluation/seeded/`, built by `build_corpus.py` from run 5's accepted system requirements):
- 23 defects in 15 classes;
- 6 of them are visible to a deterministic gate, 17 need judgement;
- the answer key is never placed in the inspector's working folder.

**Arms:**
- **Package:** the package inspector, one item phase over all 84 items and one set phase, plus the gates. No rework.
- **Plain:** the same inspector model with a plain prompt: "review these requirements and list every defect".

| Run | Pre-registered metric: item and class match | Item named (audited in sample 2) | Findings | Calls | Wall time |
|---|---|---|---|---|---|
| package, sample 1 | 13 / 23 = **56.5 %** | 22 / 23 (95.7 %), not audited | 70 | 2 | 176 s |
| package, sample 2 | 14 / 23 = **60.9 %** | 20 / 23 (87.0 %) | 60 | 2 | 147 s |
| plain, sample 1 | not scorable | 22 / 23 (95.7 %), not audited | 27 | 1 | 34 s |
| plain, sample 2 | not scorable | 17 / 23 (73.9 %) | 25 | 1 | 43 s |

- **Target:** at least 80 % of the seeded defects, on the protocol's metric. A defect counts when a finding names
  its item, or for a set defect cites its ids, **with a checklist class from the same family**. The package reached
  56.5 % and 60.9 %: **target missed**.
- **Where the class labels disagreed (sample 2),** the finding still described the seeded defect; the inspector
  filed it under another valid class:

  | Defect | Answer key | Inspector's class |
  |---|---|---|
  | "a small share" of the cycle | IQ-03 ambiguous | IQ-06 unverifiable |
  | "never lost under any circumstances" | IQ-06 unverifiable | IQ-09 contradicts the power-on clear |
  | a wrong value against the decisions | IQ-07 or IQ-09 | IQ-02 incorrect |
  | missing fault reaction or missing scenario | SQ-02 | SQ-01 coverage |

  The protocol's class rule is stricter than the answer key's single class per defect can support. The number of
  record stays as measured.
- **Item named:** a finding names the defect's item, or cites the ids of a set-level defect. Every sample 2 hit,
  in both arms, was read against the defect and describes it; there were no false matches. Sample 1 kept only
  counts, so it is not audited.
  - **Both samples:** package 42 / 46 (91.3 %), plain 39 / 46 (84.8 %).
  - **Found only by the package in sample 2:** both design-detail defects (a `uint8_t` array, a ring buffer with
    head and tail pointers) and the uncovered need (trace gate).
  - **Found by neither arm in sample 2:**
    - the status signal dropped from the start-up hold;
    - a 49 ms timing requirement set to be verified by inspection;
    - a source swapped for an unrelated need.

    The last two sit in fields, not in the text.
- **The plain arm cannot be scored on the class metric.** Its prompt asks for no checklist class. This is a flaw in
  the protocol, not in either arm.

**What this shows:**
- On the same model, the package's inspection found somewhat more seeded defects than a plain review: 91.3 % against
  84.8 % over two samples, with the gap from sample 2.
- That is a small difference on a small sample.
- The package's inspection costs about four times the wall time and produces two to three times as many findings.
  Findings on items without a seeded defect were not scored, because the base set is not known to be defect-free.
  So their precision is unknown, and they add to the reviewer's load.

## 3. Traceability (SC-004): MET

Every package run has 100 % trace coverage (needs to system requirements, system to software requirements). The
review packages of runs 4 and 5 were sealed READY with no trace gap. The seal re-runs the trace gate, so a suspect
or dangling link would have blocked them.

## 4. Cost of a run with the package

| Run | Passes | Model calls | Model time | Result |
|---|---|---|---|---|
| run 4 | 9 | 84 (system requirements) | 38 min (system requirements) | ACCEPTED, system and software requirements |
| run 5 | 4 | 74 (system requirements; 97 in total) | 23 min (system requirements) | ACCEPTED |
| baseline 3 | 1 | 1 | 50 s | not inspected |

- Most passes were waiting on product decisions, not on rework.
- The package does not reduce cost. What it buys is gated, inspected, traced requirements with every unknown made
  explicit, in a sealed review package.

## 5. Limits

- One fictional product, few runs per arm, harness default sampling. Model behaviour varies between runs; sample 1
  and sample 2 differ by up to 5 defects in the plain arm.
- The deterministic rules measure form, not engineering correctness, and the inspector's judgement is not ground
  truth.
- **Claude wrote** the seeded corpus, the answer key and the sample 2 audit, and **Claude also wrote** the product
  decisions. Nothing here was assessed blind by an independent person.
- The baseline prompt is deliberately plain. A carefully engineered prompt without the package would narrow the
  quality gap.
- Tokens are not reported: the harnesses do not expose them for account use.

## 6. Run 6 (governance step, T087)

Run 6 repeats the demo on a clean project with the governance step added (FR-030).
- **Governance package:** written in 24 s, with 6 actors and 12 use cases covering all 15 needs. No coverage issue on
  the first check.
- **Pass 1 (system requirements):**
  - item findings fell 17 → 5 → 3 → 0 over four rounds;
  - every gate passed;
  - the stage was BLOCKED only by three findings that wait on three new product questions.
- **Decision round 12** answers those questions (CON-SUP-142..144).
- **Pass 2** runs on the current package, which adds the coverage matrix (T089).
