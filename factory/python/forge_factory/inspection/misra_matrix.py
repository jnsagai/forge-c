"""Deterministic MISRA C:2012 coverage matrix (rule numbers only, no licensed rule text).

For every rule of the main body: is it automated by the installed cppcheck MISRA addon (implemented rule functions
read from the addon source), did the latest recorded cppcheck run hit it, or does it require manual review.
This records *coverage*, never compliance (`misra_compliance: NOT_CLAIMED`). Written by the SWE.3 verify node.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..common import sha256_file, utc_now

MATRIX = "verification/static/misra_coverage_matrix.md"


def addon_rules(addon: Path) -> set[str]:
    if not addon.is_file():
        return set()
    return {m.replace("_", ".") for m in re.findall(r"def misra_(\d+_\d+)\b", addon.read_text(errors="replace"))}


def build(ws: Path) -> dict:
    from ..mcp.servers.analysis import MISRA_ADDON, MISRA_RULES
    from ..release.finalize import latest, tool_results

    addon = Path(MISRA_ADDON)
    automated = addon_rules(addon)
    cpp = latest(tool_results(ws), "forge-analysis-mcp", "cppcheck")
    hits: dict[str, list[str]] = {}
    for issue in (cpp["result"]["issues"] if cpp else []):
        m = re.match(r"MISRA-(\d+\.\d+):(.+)$", issue)
        if m:
            hits.setdefault(m.group(1), []).append(m.group(2))
    rows = []
    for rule in MISRA_RULES:
        if rule in hits:
            status = f"HIT ({len(hits[rule])}x: {', '.join(hits[rule][:3])})"
        elif rule in automated and cpp is not None:
            status = "no hit (automated subset)"
        elif rule in automated:
            status = "automated, cppcheck not run"
        else:
            status = "not automated - manual review required"
        rows.append(f"| {rule} | {'yes' if rule in automated else 'no'} | {status} |")
    n_auto = sum(1 for r in MISRA_RULES if r in automated)
    text = "\n".join([
        "# MISRA C:2012 coverage matrix (generated, deterministic)", "",
        f"- Generated: {utc_now()} by forge_factory.inspection.misra_matrix",
        f"- Tool: cppcheck MISRA addon `{addon}` (sha256 {sha256_file(addon) if addon.is_file() else 'n/a'})",
        f"- Latest cppcheck result: {cpp['result']['status'] + ' - ' + cpp['result']['summary'] if cpp else 'NOT RUN'}",
        f"- Rules automated by the addon: {n_auto}/{len(MISRA_RULES)} main-body rules; the rest need manual review.",
        "- **MISRA compliance is NOT claimed**; directives and undecidable rules are not covered.", "",
        "| Rule | Automated | Status |", "|---|---|---|", *rows, ""])
    out = ws / MATRIX
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return {"automated": n_auto, "rules": len(MISRA_RULES), "hits": sorted(hits), "cppcheck_run": cpp is not None}
