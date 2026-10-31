# Keep speed, final formatting and functional correctness separate

These are observations on three standalone prompts and three seeds. They are
not a representative accuracy benchmark or a complete factory workflow.

| Setting | Semantic/functional correct / 9 | Full task contract / 9 | Format-only failures | Completion-cap truncations |
|---|---:|---:|---:|---:|
| Off | 1 | 1 | 0 | 0 |
| 512 thinking tokens | 0 | 0 | 0 | 0 |
| 2048 thinking tokens | 3 | 2 | 1 | 0 |
| Default thinking | 4 | 4 | 0 | 1 |

- `review_c-r2-budget2048` identifies exactly F1/F3/F5 but wraps the JSON in a
  markdown fence. Its recorded strict failure is a format defect, not a missed
  semantic defect. All three 2048-token reviews have correct defect sets;
  default thinking also has three correct reviews, with valid JSON in each.
- `author_c-r1-default_on` sets `low = 0xFFFFFFFFu` for width 32 instead of using
  the supplied replacement. It compiles but fails 21 independent assertions.
  The seeded full-width negative control produces the same failure count.
- `author_c-r3-default_on` fails to shift the replacement by lsb before masking;
  it compiles but fails 4705 assertions. `author_c-r3-off` passes all 31878
  assertions. More thinking did not improve every individual author result.
- `numeric-r1-budget2048` gets CRT x=487050 and extracted=92 right, but returns
  updated=2774853381 instead of 2774293157. Its JSON format is valid.
- `numeric-r3-default_on` exhausts the 8192-token common completion cap in
  thinking, with no final answer. It is an incomplete, censored observation,
  not an independently demonstrated incorrect numerical answer.

There were no repair prompts or test-feedback retries. All generated answers,
failures and the truncated case remain in their original denominators. The
positive/negative oracle controls ran after timed inference, and confirm that
the C harness can accept correct code and detect the selected seeded faults.

About 150 decoded tokens/s is supported for these small requests. Factory
throughput at long prompts, tool-assisted repair competence, deployment
reliability and a quality advantage over Qwen require separate measurements.
