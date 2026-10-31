# Complete literal owner section coverage

Candidate `090b5f0e7bdf8604045e20b5a142014312bd583c` fixes the observed mismatch
between RCC owner scope and the four-section peripheral seed catalog. The profile
opt-in unions seed sections with literal references/ranges/lists bound to the
selected manual; explicit exclusions and other manuals remain separate. Unsupported
or oversized ranges refuse explicitly. Missing referenced inputs block before
inference. No model decides administrative scope or invents hardware facts.

The actual RCC scope selects25sections,248fields and61bounded obligations; ownership
is unique and complete. Legacy profiles retain their original catalog behavior.
The experimental profile uses the existing visit mechanism with a pinned256-call
SWE.1 allowance: the previous35calls cannot cover61initial obligations. Individual
context/inference limits and cumulative mission/job accounting are unchanged.
This checks literal section coverage, not arbitrary natural-language completeness.

Exact-source local76PASS [JUnit](local76-junit.xml), native380PASS/0failures/errors/skips
[provenance/JUnit/log](native380/). Native sandbox4CPUs/8GiB/no swap/no network/GPU/
model/owner/SSH, bounded CPU-only verification while the existing product ran.
No source activation or operator pause by qualification. A prior exploratory
local108-case sweep passed while the candidate was evolving; it is not exact-revision
qualification and is not summed with these checks.

The subsequent mixed-role source7fbefc40 includes this correction and passed443native
checks. Its [actual native preflight](../role-reasoning-20261030/records/initial-request-preflight.json)
measures all61initial requests after gateway transformation against262144capacity,
with no model/grant/mission effect. The new full-scope product attempt must still
prove correct outputs and all six gates. No requirement, expected output, oracle or
quality gate was relaxed. No task newly closed; full LL/HAL remains unproven.
