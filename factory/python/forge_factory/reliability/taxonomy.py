"""CRE-T007/T008 — deterministic failure classification and fingerprint v1 (ADR-CRE-002). Model-free.

classify(raw, component, operation) -> Classification(failure_class, category, error_code, route).
The class is decided by ordered rules over normalized issue codes; text that matches no rule is UNKNOWN (never a
guessed class). Root-cause hypotheses never enter the fingerprint.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..common import canonical_json

CLASSIFIER_VERSION = "cre-rules-1.2"  # bump on any rule change; superseded observations are retracted, not deleted
CLASSES = ("INFRASTRUCTURE", "TRANSIENT_DEPENDENCY", "PRODUCT_QUALITY", "POLICY_SECURITY", "UNKNOWN")
CATEGORIES = ("INFRASTRUCTURE", "WORKFLOW_ORCHESTRATION", "MCP_TOOL", "RESOURCE_BUDGET", "TRANSIENT_ENVIRONMENT",
              "PRODUCT_ENGINEERING", "REQUIREMENTS_SPEC", "AGENT_OUTPUT", "POLICY_SECURITY", "UNKNOWN")
CLASS_OF = {"INFRASTRUCTURE": "INFRASTRUCTURE", "WORKFLOW_ORCHESTRATION": "INFRASTRUCTURE", "MCP_TOOL": "INFRASTRUCTURE",
            "RESOURCE_BUDGET": "INFRASTRUCTURE", "TRANSIENT_ENVIRONMENT": "TRANSIENT_DEPENDENCY",
            "PRODUCT_ENGINEERING": "PRODUCT_QUALITY", "REQUIREMENTS_SPEC": "PRODUCT_QUALITY",
            "AGENT_OUTPUT": "PRODUCT_QUALITY", "POLICY_SECURITY": "POLICY_SECURITY", "UNKNOWN": "UNKNOWN"}
# AT-004: routes are fixed per class; PRODUCT_QUALITY is never sent to infrastructure repair.
ROUTE_OF = {"INFRASTRUCTURE": "REPAIR_ELIGIBLE", "TRANSIENT_DEPENDENCY": "RETRY_BOUNDED",
            "PRODUCT_QUALITY": "SWE_REWORK", "POLICY_SECURITY": "REQUIRES_OFFLINE_ATTENTION",
            "UNKNOWN": "REQUIRES_OFFLINE_ATTENTION"}
NOT_REPAIRABLE = {"RESOURCE_BUDGET"}  # budgets/caps are owner decisions: offline attention, never auto-repaired

# Ordered rules: (regex on the raw issue, category, error_code template). First match wins.
RULES: list[tuple[re.Pattern, str, str]] = [(re.compile(p, re.I), cat, code) for p, cat, code in [
    # policy / security (fail closed)
    (r"WRITE_SCOPE_DENIED|PATH_(?:ESCAPE|TRAVERSAL|INVALID)|ROBOT_POLICY:|FORGE_POLICY:(?!TURN_BUDGET)|"
     r"TOOL_NOT_GRANTED|ROLE_NOT_ALLOWED|PROTECTED_PATH|SECURITY_DENIAL", "POLICY_SECURITY", "POLICY_DENIAL"),
    # resource budgets set by the owner
    (r"TOKEN_BUDGET_EXHAUSTED", "RESOURCE_BUDGET", "TOKEN_BUDGET_EXHAUSTED"),
    (r"cost cap .* reached|COST_CAP", "RESOURCE_BUDGET", "COST_CAP_REACHED"),
    # transient dependencies
    (r"\b429\b|rate.?limit|timed? ?out|TIMEOUT(?!_VALUE)|temporar(?:il)?y unavailable|connection (?:reset|refused)|"
     r"dropped_output|upstream.*(?:empty|dropped)", "TRANSIENT_ENVIRONMENT", "TRANSIENT_UPSTREAM"),
    # orchestration / infrastructure
    (r"run_not_completed|deterministic failure cycle|stdin_source .* not found|max_visits|WORKFLOW_ERROR|"
     r"stage\.failed", "WORKFLOW_ORCHESTRATION", "RUN_NOT_COMPLETED"),
    (r"READINESS_FAILURE|STAGE_STALL|QUEUE_STALL|DASHBOARD_DOWN|CONFIG_INVALID", "INFRASTRUCTURE", "{supervisor}"),
    (r"STORE_NOT_WRITABLE|DB_NOT_WRITABLE|DISK_PRESSURE|RAM_PRESSURE|No space left", "INFRASTRUCTURE", "{supervisor}"),
    (r"MCP_HANDSHAKE_FAILURE|TOOL_MISSING|TOOL_UNAVAILABLE|MCP_UNAVAILABLE", "MCP_TOOL", "TOOL_UNAVAILABLE"),
    # agent output contract / behaviour (PRODUCT_QUALITY -> SWE rework)
    (r"AGENT_OUTPUT_(?:PROSE|SCHEMA|TOO_LARGE)|^(?:issues/\d+|next_action|status|artifacts|<root>):",
     "AGENT_OUTPUT", "AGENT_OUTPUT_CONTRACT"),
    (r"(?:turn|tool|tool-call|tool-turn)[ /-]*(?:turn )?budget|TURN_BUDGET|TOOL_BUDGET|budget hit \d+/\d+",
     "AGENT_OUTPUT", "TURN_BUDGET_EXHAUSTED"),
    (r"TEST_CHANGED_AFTER_FAIL|UNDECLARED_TEST_CHANGE", "AGENT_OUTPUT", "TEST_CHANGED_AFTER_FAIL"),
    (r"DEFECT_TEST_CHANGED", "AGENT_OUTPUT", "DEFECT_TEST_CHANGED"),
    (r"DEFECT_NOT_ADDRESSED", "AGENT_OUTPUT", "DEFECT_NOT_ADDRESSED"),
    (r"DEFECT_NOT_FIXED", "PRODUCT_ENGINEERING", "DEFECT_NOT_FIXED"),
    (r"MISSING_REQUIRED_OUTPUT:(?P<f>[^\s;]+)", "AGENT_OUTPUT", "MISSING_REQUIRED_OUTPUT:{f}"),
    (r"NO_WORKPRODUCTS|NO_TESTS|WORKPRODUCT_IS_AGENT_REPLY", "AGENT_OUTPUT", "NO_WORK_PRODUCT"),
    (r"REQUIRED_TOOL_NOT_PASS:(?P<op>\w+)", "PRODUCT_ENGINEERING", "REQUIRED_TOOL_NOT_PASS:{op}"),
    # product engineering
    (r"REWORK_BUDGET_EXHAUSTED|rework budget exhausted", "PRODUCT_ENGINEERING", "REWORK_BUDGET_EXHAUSTED"),
    (r"INSPECTION_FAIL:(?P<item>SWE1-\d+)", "REQUIREMENTS_SPEC", "INSPECTION_FAIL:{item}"),
    (r"INSPECTION_FAIL:(?P<item>[A-Z0-9]+-\d+)", "PRODUCT_ENGINEERING", "INSPECTION_FAIL:{item}"),
    (r"DEFECT:REQUIREMENT", "REQUIREMENTS_SPEC", "DEFECT:REQUIREMENT"),
    (r"DEFECT:(?P<k>CODE|ARCHITECTURE|TEST)", "PRODUCT_ENGINEERING", "DEFECT:{k}"),
    (r"DEFECT_REJECTED:(?P<k>\w+)", "AGENT_OUTPUT", "DEFECT_REJECTED:{k}"),
    (r"BUILD_FAIL|error: |undefined reference|compile|link(?:er)? ", "PRODUCT_ENGINEERING", "BUILD_FAIL"),
    (r"MISRA|cppcheck|GL-[A-Z]+-\d+|guideline", "PRODUCT_ENGINEERING", "STATIC_ANALYSIS_FINDING"),
    (r"REQUIREMENT_NOT_OBSERVED|EARS|traceab", "PRODUCT_ENGINEERING", "VERIFICATION_GAP"),
    (r"UPSTREAM_CHANGED|UPSTREAM_NOT_FROZEN|BASELINE_CHANGED", "PRODUCT_ENGINEERING", "STALE_BASELINE"),
    (r"PACKAGE_GAP:(?P<g>[a-z_]+)", "PRODUCT_ENGINEERING", "PACKAGE_GAP:{g}"),
]]
SUPERVISOR_FAULT = re.compile(r"\b([A-Z]+(?:_[A-Z]+)+)\b")


@dataclass(frozen=True)
class Classification:
    failure_class: str
    category: str
    error_code: str
    route: str
    rule: int  # index of the matching rule, -1 = none (auditable)


def normalize(text: str) -> str:
    """Strip volatile parts: timestamps, IDs, hashes, absolute/workspace paths (keep file names), numbers."""
    t = str(text)
    t = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:.]+Z?", "<ts>", t)
    t = re.sub(r"/?(?:[\w.@+-]+/)+([\w.@+-]+)", r"\1", t)  # absolute or nested paths -> base name (first)
    t = re.sub(r"\b[0-9a-f]{12,64}\b", "<hash>", t)
    t = re.sub(r"\b(?:DEF|INS|BL|inc|att|cfp1|cre)-[\w.-]+", lambda m: m.group(0).split("-")[0] + "-<id>", t)
    t = re.sub(r"WO-[\w-]+", "WO-<id>", t)
    t = re.sub(r"\d+", "N", t)
    return re.sub(r"\s+", " ", t).strip()


def classify(raw: str) -> Classification:
    for i, (rx, cat, code) in enumerate(RULES):
        m = rx.search(raw or "")
        if not m:
            continue
        # identifiers (tool op, checklist item, defect kind) are kept verbatim; free text/paths are normalized
        groups = {k: (normalize(v).replace(" ", "_") if k == "f" else v)[:60] for k, v in m.groupdict().items() if v}
        if "{supervisor}" in code:
            sm = SUPERVISOR_FAULT.search(raw)
            groups["supervisor"] = sm.group(1) if sm else "SUPERVISOR_FAULT"
        error_code = code.format(**groups) if groups or "{" not in code else code
        cls = CLASS_OF[cat]
        route = "REQUIRES_OFFLINE_ATTENTION" if cat in NOT_REPAIRABLE else ROUTE_OF[cls]
        return Classification(cls, cat, error_code, route, i)
    return Classification("UNKNOWN", "UNKNOWN", "UNCLASSIFIED", ROUTE_OF["UNKNOWN"], -1)


def fingerprint(failure_class: str, component: str, error_code: str, operation: str,
                tool_major_version: str = "forge-factory-0", contract_schema_version: str = "1",
                environment_family: str = "linux-host") -> str:
    """cfp1- + sha256 of the canonical identity tuple (ADR-CRE-002); volatile data never enters it."""
    ident = {"algorithm": "cfp-v1", "failure_class": failure_class, "source_component": component,
             "error_code": error_code, "normalized_operation": operation, "tool_major_version": tool_major_version,
             "contract_schema_version": contract_schema_version, "environment_family": environment_family}
    return "cfp1-" + hashlib.sha256(canonical_json(ident)).hexdigest()[:40]
