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
    check: Literal["ears", "hal_guideline", "register_map", "implementation", "architecture", "markdown", "json", "csv"] = "markdown"


class DocIn(ToolInput):
    pass


def validate_artifact(ctx: ToolContext, a: ValidateIn) -> dict:
    if a.check == "hal_guideline":
        rep = check_workspace(ctx.workspace)
        issues = [f"{v['rule']}:{v['file'].split('/')[-1]}:{v['line']}" for v in rep["violations"]]
        return result(ctx, rep["verdict"], f"HAL guideline: {len(rep['violations'])} violations",
                      [ctx.store(json.dumps(rep, indent=1).encode(), "json")], issues,
                      {"files_checked": len(rep["files_checked"])}, "forge-guideline-check",
                      input_obj=a.model_dump())
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
    Operation("validate_artifact", ValidateIn, validate_artifact,
              "Validate a workproduct (ears|hal_guideline|register_map|implementation|architecture|markdown|json|csv)."),
    Operation("render_diagram", DocIn, unsupported("plantuml"), "Render PlantUML (disabled)."),
    Operation("build_docs", DocIn, unsupported("mkdocs"), "Build MkDocs site (disabled)."),
]

if __name__ == "__main__":
    build_server("forge-docs-mcp", OPERATIONS).run("stdio")
