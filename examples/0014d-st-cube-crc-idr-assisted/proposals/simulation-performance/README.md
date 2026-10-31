# Reviewed simulation-only development input

Owner Jefferson Nascimento approved the complete nine-requirement payload on
2026-10-29. The exact payload hash is
`af48340bdc64510347f2aa236114b601f86ad24a0fbd062e82f07e4eed770463`.
The [review record](../../../../../evidence/014-durable-local-autonomy/m1-owner-review-simulation-20261029.json)
binds the actual approval and reviewed preview.

The preview is retained exactly as shown for review, including its historical
PENDING banner. Current review status is in provided-requirements.json and that
record. Seven original requirements are retained; two owner-selected allocations
add 64 executed target instructions and 100 microseconds of Renode virtual time
per call at 100 MIPS, with no injected interrupts/bus stalls. This claims no
physical WCET or safety assurance. The original example and historical baseline
are unchanged.

Prepare through the normal workorder intake, assisted import and independent
SWE.1 inspection. The preparation tool in factory/qualification/014 can import,
freeze and measure the six inspector requests without inference. It deliberately
leaves delivery unavailable until real inspection passes. The source measurement
path is generic to declared delivery functions; this example is an IDR fixture.

Approval of requirements does not renew execution authority, amend a mission,
prove a role, or accept a product. Preserve the existing M1 mission, history and
conservative charge. New execution needs a current source-bound grant and the
existing role admission checks.
