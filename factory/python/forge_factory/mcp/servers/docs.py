"""T017 — forge-docs-mcp: deterministic artifact validation (EARS, HAL guideline, SWE.2 architecture, markdown/json/csv).

PlantUML and MkDocs are not installed: render_diagram/build_docs are optional and report UNSUPPORTED.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Literal

from pydantic import Field

from ...inspection.architecture import check_architecture, is_agent_reply
from ...inspection.ears import check_file
from ...inspection.guideline import check_workspace
from ...inspection.implementation import check_implementation
from ...inspection.regmap import check_regmap
from ..sdk import Operation, ToolContext, ToolInput, build_server, result


class ValidateIn(ToolInput):
    path: str = Field(default=".", max_length=200)
    check: Literal["ears", "hal_guideline", "register_map", "implementation", "swe3_all", "architecture", "plantuml",
                   "markdown", "json", "csv"] = "markdown"


class DocIn(ToolInput):
    pass


class OnboardingReadIn(ToolInput):
    path: str = Field(pattern=r"^inputs/[A-Za-z0-9_./-]+$", max_length=200)
    offset: int = Field(default=0, ge=0, le=4_000_000)
    search: str | None = Field(default=None, min_length=1, max_length=80)


def read_onboarding_input(ctx: ToolContext, a: OnboardingReadIn) -> dict:
    """Read only the frozen authoring input corpus; the search is literal, not executable regex."""
    from ...common import sha256_file

    path = ctx.path(a.path, kind="file")
    if not path.is_relative_to(ctx.workspace / "inputs"):
        from ..sdk import ToolDenied

        raise ToolDenied("ONBOARDING_INPUT_SCOPE")
    text = path.read_text()
    offset = a.offset
    if a.search:
        found = text.find(a.search, offset)
        if found < 0:
            return result(ctx, "PASS", "literal text not found", metrics={"found": False, "offset": offset},
                          tool="forge-onboarding-reader", input_obj=a.model_dump())
        offset = max(offset, found - 100)
    excerpt = text[offset:offset + 800]
    # Keep the response comfortably inside the existing 2048-byte tool-result budget.
    excerpt = excerpt.encode()[:900].decode(errors="ignore")
    return result(ctx, "PASS", "immutable onboarding input excerpt", metrics={"path": a.path, "excerpt": excerpt,
                  "offset": offset, "next_offset": offset + len(excerpt), "total_chars": len(text),
                  "sha256": sha256_file(path), "found": True}, tool="forge-onboarding-reader",
                  input_obj=a.model_dump())


BROWNFIELD_CHECKS = {"hal_guideline": ("delivered_guideline",), "register_map": ("delivered_register_definitions",),
                     "implementation": ("delivered_implementation",),
                     "swe3_all": ("delivered_guideline", "delivered_register_definitions", "delivered_implementation")}


def _brownfield_swe3(ctx: ToolContext, a: ValidateIn) -> dict:
    """CAPA-057 (b006 DEF-002): for a delivery the SWE.3 checks are the v0.4-brownfield items (OD-2026-10-20-02), not
    the factory-style rules (ll_rcc_regs defines, static inline, Cube2 guideline on vendor code). Findings in the
    delivered code are reported for the record (the SWE.3 verify node records them as owner findings); the author
    fails only on what it must act on: a build/probe failure, a fingerprint change, or a fixable (FIX_ALLOWED,
    forge-style) finding."""
    from ...brownfield import checks as K
    from ...brownfield import code_mode, manifest_of

    m = manifest_of(ctx.workspace)
    fixable = code_mode(m) == "FIX_ALLOWED" and K.style_of(m) == "forge"
    reps, blocking, info = {}, [], []
    for name in BROWNFIELD_CHECKS[a.check]:
        rep = K.RUN[name](ctx.workspace, m)
        reps[name] = rep
        if rep.get("build") in ("FAIL", "NOT_RUN") and rep.get("probes"):
            blocking.append(f"{name}:REGISTER_PROBES_{rep['build']}")
        blocking += [f"{name}:{x}" for x in rep["findings"] if x.startswith("DELIVERY:") or fixable]
        info += [f"DELIVERED_FINDING(recorded for the owner):{x}" for x in rep["findings"]
                 if not (x.startswith("DELIVERY:") or fixable)]
    verdict = "FAIL" if blocking else "PASS"
    return result(ctx, verdict, f"SWE.3 delivered-code checks ({a.check}): {len(blocking)} blocking, {len(info)} "
                  "recorded findings", [ctx.store(json.dumps(reps, indent=1).encode(), "json")], (blocking + info)[:30],
                  {"blocking": len(blocking), "recorded_findings": len(info)}, "forge-brownfield-checks",
                  input_obj=a.model_dump())


def validate_artifact(ctx: ToolContext, a: ValidateIn) -> dict:
    if a.check in BROWNFIELD_CHECKS:
        from ...brownfield import is_brownfield, manifest_of

        if is_brownfield(manifest_of(ctx.workspace)):
            return _brownfield_swe3(ctx, a)
    if a.check == "hal_guideline":
        rep = check_workspace(ctx.workspace)
        issues = [f"{v['rule']}:{v['file'].split('/')[-1]}:{v['line']}" for v in rep["violations"]]
        return result(ctx, rep["verdict"], f"HAL guideline: {len(rep['violations'])} violations",
                      [ctx.store(json.dumps(rep, indent=1).encode(), "json")], issues,
                      {"files_checked": len(rep["files_checked"])}, "forge-guideline-check",
                      input_obj=a.model_dump())
    if a.check == "swe3_all":  # one call for the three deterministic SWE.3 verification checks (saves agent turns)
        g, r, i = check_workspace(ctx.workspace), check_regmap(ctx.workspace), check_implementation(ctx.workspace)
        issues = ([f"{v['rule']}:{v['file'].split('/')[-1]}:{v['line']}:{v['detail'][:60]}" for v in g["violations"]]
                  + r["major_findings"] + i["major_findings"])
        verdict = "PASS" if g["verdict"] == r["verdict"] == i["verdict"] == "PASS" else "FAIL"
        return result(ctx, verdict, f"SWE.3 checks: guideline {g['verdict']} ({len(g['violations'])}), register map "
                      f"{r['verdict']}, implementation {i['verdict']}",
                      [ctx.store(json.dumps({"hal_guideline": g, "register_map": r, "implementation": i},
                                            indent=1).encode(), "json")], issues[:30],
                      {"guideline_violations": len(g["violations"]), "register_map_findings": len(r["major_findings"]),
                       "implementation_findings": len(i["major_findings"])}, "forge-swe3-checks",
                      input_obj=a.model_dump())
    if a.check == "plantuml":  # SWE.2 static + dynamic views (syntax with pinned PlantUML, content vs architecture)
        from ...inspection.views import check_views

        rep = check_views(ctx.workspace)
        return result(ctx, rep["verdict"], f"PlantUML views: {len(rep['major_findings'])} findings",
                      [], rep["major_findings"][:30], rep["stats"], "plantuml", input_obj=a.model_dump())
    if a.check == "implementation":
        rep = check_implementation(ctx.workspace)
        return result(ctx, rep["verdict"], f"SWE.3 implementation completeness: {len(rep['major_findings'])} findings",
                      [ctx.store(json.dumps(rep, indent=1).encode(), "json")], rep["major_findings"][:30],
                      rep["stats"], "forge-implementation-check", input_obj=a.model_dump())
    if a.check == "register_map":
        rep = check_regmap(ctx.workspace)
        return result(ctx, rep["verdict"], f"register map vs RM0486: {len(rep['major_findings'])} findings",
                      [ctx.store(json.dumps(rep, indent=1).encode(), "json")], rep["major_findings"][:30],
                      rep["stats"], "forge-regmap-check", input_obj=a.model_dump())
    if a.check == "architecture":
        rep = check_architecture(ctx.workspace)
        return result(ctx, rep["verdict"], f"SWE.2 architecture: {len(rep['major_findings'])} findings",
                      [ctx.store(json.dumps(rep, indent=1).encode(), "json")], rep["major_findings"][:30],
                      rep["stats"], "forge-architecture-check", input_obj=a.model_dump())
    p = ctx.path(a.path, must_exist=True, kind="file")
    if a.check == "ears":
        rep = check_file(p)
        return result(ctx, rep["verdict"], f"EARS: {rep['requirements']} reqs, {len(rep['major_findings'])} major",
                      [ctx.store(json.dumps(rep, indent=1).encode(), "json")],
                      rep["major_findings"] + rep["minor_findings"], {"requirements": rep["requirements"]},
                      "forge-ears-check", input_obj=a.model_dump())
    text = p.read_text(encoding="utf-8", errors="replace")
    issues = []
    if a.check == "markdown":
        if not text.strip():
            issues.append("EMPTY_DOCUMENT")
        if is_agent_reply(text.strip()):
            issues.append("WORKPRODUCT_IS_AGENT_REPLY")
        if not any(line.startswith("#") for line in text.splitlines()):
            issues.append("NO_HEADINGS")
        for marker in ("TBD", "TODO", "lorem ipsum"):
            if marker.lower() in text.lower():
                issues.append(f"PLACEHOLDER:{marker}")
    elif a.check == "json":
        try:
            json.loads(text)
        except ValueError as exc:
            issues.append(f"JSON_INVALID:{str(exc)[:80]}")
    else:
        rows = list(csv.reader(io.StringIO(text)))
        if len(rows) < 2:
            issues.append("CSV_NO_ROWS")
        elif len({len(r) for r in rows}) != 1:
            issues.append("CSV_RAGGED")
    return result(ctx, "PASS" if not issues else "FAIL", f"{a.check}: {len(issues)} issues", [], issues,
                  {"bytes": len(text)}, "forge-artifact-check", input_obj=a.model_dump())


def unsupported(name: str):
    def h(ctx: ToolContext, a: DocIn) -> dict:
        return result(ctx, "UNSUPPORTED", f"{name} not installed; optional op disabled",
                      issues=[f"TOOL_MISSING:{name}"], tool=name, version="unavailable")
    return h


OPERATIONS = [
    Operation("read_onboarding_input", OnboardingReadIn, read_onboarding_input,
              "Read an immutable inputs/ document by character offset or bounded literal search (onboarding roles only)."),
    Operation("validate_artifact", ValidateIn, validate_artifact,
              "Validate a workproduct (ears|hal_guideline|register_map|implementation|swe3_all|architecture|plantuml|"
              "markdown|json|csv)."),
    Operation("render_diagram", DocIn, unsupported("plantuml"), "Render PlantUML (disabled)."),
    Operation("build_docs", DocIn, unsupported("mkdocs"), "Build MkDocs site (disabled)."),
]

if __name__ == "__main__":
    build_server("forge-docs-mcp", OPERATIONS).run("stdio")
