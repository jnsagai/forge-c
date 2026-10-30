# Ten-hour AFO delivery qualification — 30–31 October 2026

**Real AFO-admitted Qwen candidate passed the complete declared functional slice
in-loop. The six-phase terminal package and DF-M1 remain pending.**

Owner request at21:57:59UTC: continue the goal overnight for ten hours.
The fixed inference deadline is **2026-10-31T07:57:59Z**. No grant or mission
deadline is automatically renewed. Production stays **PAUSED111**. This is an
isolated development instance of the existing AFO/Conductor/Fabro stack, not a
production deployment, another scheduler or an EGM implementation.

## Actual execution

- Runtime root: `/mnt/data/forge-c/delivery-first-afo-014-20261030-v1`.
- Clean source: **a34fdd859af47d1ca6cba2633b3ccb672c7cb690**.
- AFO order **afo-5faf7b5e42e6d55f**, product job
  **afo-product-221ded78874865909a532471**.
- Native **01M67ETTPXS1Q73QPMQ98DNJX0**, launched22:28:06UTC.
- Profile `local-rtx-v2-omniverse2-q38-delivery-first` v3, SHA256
  `823942772335b7ef500f9f11926732405ac12dbff0dcc7f0ab39e345db3358e7`.
- Qwen3.8-27B Q8, f16 KV, MTP3, medium reasoning, one262144-token slot.
  This is an experimental role grant, **not** measured role qualification.
- Actual namespace preflight: **DENIED_VERIFIED**, loopback interface only;
  model manifest/precision matched the pinned profile. Actual gateway worker
  environment was checked after replacement, including its policy path.
- Existing scheduler/outbox admitted the order and adopted the native nonce.
  The request ledger recorded SENT then QUIESCENT requests while the execution
  retained its inference lease. This is actual admission/accounting, not a
  standalone trial masquerading as AFO.

Qwen wrote a new2044-byte header, from an initially absent candidate. Its hash
differs from the earlier standalone candidate:
`855f53a6b3f90d83e60e03aacba50e953e9e3a2827c3730d6ae6746fff46b173`.
At **22:31:19UTC**, the native deterministic verifier recorded attempt0 **PASS**:
both compilers,630independent host assertions,351target assertions, simulation
performance and declared object/frame budgets. Object flash16B, static RAM0B,
maximum frame0B. There is no linked-firmware, call-graph stack or physical WCET
claim. **Zero implementation corrections.** The target oracle was frozen in
the work order before launch; this result is not external post-hoc verification.

Read [the exact first-pass receipt and native authorship evidence](runtime-checkpoint/control/first-in-loop-functional-pass-v3-native-ns.json)
and [the actual candidate](runtime-checkpoint/qwen-first-candidate.h).
The host observer initially called the workspace's namespace-local API from the
wrong namespace and obtained UNVERIFIED metadata. Re-observation inside the
correct native namespace confirmed the exact successful write event. This
observer correction did not alter the job, candidate, input or verifier.

At this checkpoint the run had advanced to SWE.1. Remaining phases, final-byte
recheck, package integrity and full milestone conditions must still be observed.
No post-launch source, candidate or model steering was supplied to this job.
Dashboard retargeting and outcome collection are disclosed observation activities,
not engineering repairs or evidence of autonomous self-healing.

Read-only update at22:52UTC: SWE.1 author completed; its deterministic contract
gate found four unsupported field names (`CRC_CR.CR`, `CRC_INIT.INIT`) in
preservation cases. Those findings are retained; the demonstration graph
continued to SWE.1 inspection. The EARS tool separately reported10requirements,
zero major findings, PASS. Neither observation changes the independent driver
verdict or establishes process acceptance. See the [live checkpoint](runtime-checkpoint/progress-20261030-2252.json).

The [actual profile preflight receipt](runtime-checkpoint/control/profile-preflight-v3.json)
is now included for offline model-digest/network verification. Its separate
remote/local hash comparison is recorded in the transfer addendum; the original
23-file transfer manifest remains unchanged.

Read-only [register-contract diagnosis](runtime-checkpoint/swe1-contract-diagnosis-20261030.json)
confirmed the index contains the actual manual fields: the generated aliases
`CR` and `INIT` are absent. This is generated contract content rejected by the
existing gate; no shared-engine parser defect was identified.

The three follow-up [cohort and launch records](repeatability-prepared/cohort.json)
are prepared before their first run. They have fresh request/order identities,
identical launch configuration and no candidate reuse. Status remains
**PREPARED_NOT_SUBMITTED**: no follow-up is admitted before an independently
audited DF-M1 terminal PASS. These records establish no repeatability result.

## Specific fixes and reproduced failures

**5440c474d0a64ccd69be97518cb987d98d390119**: history import previously preserved
token charges but discarded supplied request/tool/correction counts. A valid
snapshot imported(3,4,1) as(0,0,0), and a spent historical request allowance still
admitted a new request. Both regressions failed before the change. Optional,
evidence-bound imported counts now survive idempotent replay, reject rebinding
and deduplicate later observations in the same execution. Negative/unbound counts
are rejected. Legacy snapshots remain compatible; no synthetic request rows are
created. Exact accounting/mission/native-integration cohort: **134PASS**, no
skip/failure/error.

**a34fdd85**: the fast author's prompt did not match the existing request-role
parser before its first tool call. The new regression returned None rather than
swe3-author. The prompt now uses the established `skill_name swe3-author`
instruction, with the existing tool binding unchanged. Exact delivery/strict/
demonstration/policy/role-trial cohort: **104PASS, one disabled live Fabro skip**,
zero failures/errors. Cohorts overlap; do not sum them.

Commands (pinned loop10 Python/toolchain environment):

```text
python -m pytest factory/python/tests/test_da014_historical_counts.py factory/python/tests/test_da014_protocol.py factory/python/tests/test_da014_integration.py factory/python/tests/test_da014_settled_usage.py factory/python/tests/test_da014_product_outcomes.py factory/python/tests/test_mission_capacity.py factory/python/tests/test_mission_deadline.py -q
python -m pytest factory/python/tests/test_delivery_first.py factory/python/tests/test_simulation_declared_headers.py factory/python/tests/test_simulation_performance_authored.py factory/python/tests/test_pipeline_demonstration.py factory/python/tests/test_demonstration_repair.py factory/python/tests/test_t007_policy.py factory/python/tests/test_da014_product_role_trial.py -q
```

Pre-inference setup also exposed an incorrect Fabro binary path and omitted
required cache environment variables. Their exact configurations/errors were
preserved and corrected before the first admitted inference.

The first AFO native **01M67E5YEMFM4F5GR62AM0F9EM** completed nativeSUCCEEDED,
product **BLOCKED56**, with **zero admitted requests / zero reported inference
tokens**. All57recorded refusals occurred before upstream dispatch. The setup
restart had ended a namespace-entry wrapper while its old gateway worker remained
listening; a replacement failed to bind, and the worker used the earlier policy.
Typed AUTH_POLICY_MISMATCH, actual effective/expected policy hashes and failure
history are retained in
[the sanitized record](runtime-checkpoint/failed-admission-v2-sanitized.json).

This was an external setup mistake, not a failed Qwen diagnosis or autonomous
repair. The correction used the existing managed provider namespace retirement,
proved the namespace init ended, stopped the old Conductor through its durable
intent, and started a replacement. It then verified the **actual** worker's
policy before admission. No authority check was waived.

## Conserved history, authority and window

The earlier standalone job, the failed AFO admission and this new run share
one cumulative mission. Earlier failed jobs/packages remain unchanged. Historical
request count is a conservative reservation, not a claimed physical-generation
measurement. Token **charges/reservations** are distinct from actual reported
usage: the first standalone import reserves246×262144=64487424tokens with
explicit uncertainty, and the failed AFO attempt retains its67108864-token
reservation despite reported zero usage. These are not generated-token claims.
The mission registration and original limits were not reset on either new grant.

Signed qualification records were made through the existing SSH agent under the
owner's standing delegation and ten-hour request. No private key, safety document,
review disposition or patch bundle was signed/read. V3 pins source, model,
context and eight remaining predeclared CRC orders; only the first is initially
queued. Fresh three-run qualification waits for actual DF-M1. All records retain
the same07:57:59deadline. The policy preserves one work order/inference, strict
release gates, operator intent and finite cumulative job/request/token limits.

The external window guard is an executable qualification tool, not a work
scheduler. At the deadline it calls existing shutdown, cancellation and managed
provider reconciliation. A newer operator epoch fences its stop. It uses the
qualification API bridge explicitly and cannot stop unrelated systemd units.
The guard process and script hash are recorded; its future stop outcome is not
yet qualified or claimed complete.

Dashboard: **http://100.118.28.92:8786**, now backed by this runtime/API32404.
The existing access policy is unchanged. Complete terminal archives are copied,
SHA256-checked, integrity-verified and safely extracted privately on loop10 at:

```text
B/inspection/feature014/2026-10-30-qwen/overnight-afo-delivery/
```

The corrected read-only collector is live; it already copied the BLOCKED56
archive. Its first observer query used the wrong SQLite column and was corrected
without any runtime side effect. Observation grace ends08:12:59UTC for final
copies; this does not extend inference authority.

Formal Feature014 progress remains30/58. No autonomous DF-M1,3/3repeatability,
HAL dependency, full RCC/LL/HAL, ASPICE compliance, production, general-target,
learning-benefit or24/7 result is claimed at this checkpoint.
