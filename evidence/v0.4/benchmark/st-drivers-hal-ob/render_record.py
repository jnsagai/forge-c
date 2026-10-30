"""Render a frozen onboarding acceptance snapshot; refuse to overwrite output."""

import json
import sys
from pathlib import Path

from forge_factory.benchmark.record import markdown

record = Path(sys.argv[1])
out = Path(sys.argv[2])
r = json.loads(record.read_text())
lines = [
    "# ST HAL onboarding acceptance record",
    "",
    f"Recorded {r['recorded_at']}. The JSON snapshot retains every attempt, all named gaps and raw token counters.",
    "",
    "| Peripheral | Current package SHA-256 | Signed approval |",
    "|---|---|---|",
]
for name, p in r["packages"].items():
    lines.append(f"| {name.upper()} | `{p['sha256']}` | {p['approval']['approval_id']} ({p['approval_code']}) |")
lines += [
    "",
    "The initial GPIO package was superseded after omitted RM fields were found. Its failed attempt and original archive "
    "remain in this record; OA-2026-10-27-05 approves the corrected package. The first SPI attempt also remains visible "
    "with its factory probe defect. Terminal package status is not safety acceptance.",
    "Phase ACP token counters are retained per model and role, including separate cache counters. Recovery budget "
    "tokens remain the native UNKNOWN; they are not reported as zero or estimated from budget ceilings.",
    "",
]
entries = []
for o in r["orders"]:
    for a in o["attempts"]:
        entries.append({"route": "AFO", "request_id": o["request_id"], "order_id": o["order_id"], "order_state": o["state"], **a})
lines += [markdown({"queue": "st-hal-onboarding", "schema": r["schema"], "recorded_at": r["recorded_at"], "entries": entries})]
for o in r["orders"]:
    lines += [f"## {o['request_id']}", "", f"Order `{o['order_id']}`: **{o['state']}**.", ""]
    operations = o.get("operational") or {}
    if operations.get("terminal_reason"):
        lines += [f"Terminal reason: `{operations['terminal_reason']}`.", ""]
    review = o.get("cause_review")
    if review:
        lines += [f"Cited cause review: {len(review['onboarding_fact_causes_identified'])} onboarding-fact causes "
                  f"identified among {review['gap_count']} named gaps. {review['assessment']}", ""]
        if review.get("interpretation_limit"):
            lines += ["Review limitation: " + review["interpretation_limit"], ""]
    for a in o["attempts"]:
        b = a.get("onboarding") or {}
        p = a.get("package_record") or {}
        lines += [
            f"- Attempt `{a['attempt_id']}`, Fabro `{a.get('fabro_run_id')}`.",
            f"- Factory `{a.get('factory_revision')}`; approved package `{b.get('sha256')}` ({b.get('approval_id')}).",
            f"- Archive `{p.get('archive')}`.",
            f"- Archive SHA-256 `{p.get('archive_sha256')}`; {p.get('gap_count')} named gaps "
            "(full list in JSON and sealed archive).",
            "",
        ]
        timing = (operations.get("attempt_timing") or {}).get(a["attempt_id"])
        if timing:
            lines += [f"Full attempt duration: {timing['full_attempt_duration_s']} s "
                      f"({timing['started_at']} to {timing['finished_at']}).", ""]
    for plan in operations.get("recovery_plans") or []:
        lines += [f"Recovery `{plan['plan_id']}`: {plan['source']} / {plan['strategy']} / {plan['status']}. "
                  f"Token budget observation: {plan['budget_snapshot'].get('tokens', 'UNKNOWN')}.", ""]
lines += [
    "## Review status",
    "",
    "All packages are for offline review. Cited cause reviews are retained in the JSON snapshot; their coverage and "
    "bindings are checked separately from terminal outcomes. Owner dispositions remain pending. "
    "Held-out model authoring remains NOT_RUN while the approved Claude inspector is out of quota. "
    "No merge or safety approval is implied.",
    "",
]
with out.open("x") as f:
    f.write("\n".join(lines))
