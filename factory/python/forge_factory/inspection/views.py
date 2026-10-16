"""SWE.2 architecture views in PlantUML (static + dynamic) - deterministic checks and rendering.

The SWE.2 author writes `architecture_static.puml` (component view) and `architecture_dynamic.puml` (sequence
view). This module checks them with the pinned PlantUML (Apache-2.0 build, `-checkonly` syntax check), checks
their content against the architecture (driver components and allocated HAL APIs appear; the dynamic view covers a
timeout path), and renders SVGs next to them (before the baseline is frozen). Backs checklist item SWE2-08.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ..layer import components, layer_of
from .implementation import allocated_functions

STATIC = "workproducts/SWE.2/architecture_static.puml"
DYNAMIC = "workproducts/SWE.2/architecture_dynamic.puml"
JAR_REL = "toolchains/plantuml/plantuml-asl-1.2026.8.jar"


def plantuml_jar() -> Path | None:
    roots = [os.environ.get("FORGE_DATA_ROOT")]
    if os.environ.get("FORGE_STATE_DIR"):
        roots.append(str(Path(os.environ["FORGE_STATE_DIR"]).parent))
    for r in filter(None, roots):
        if (Path(r) / JAR_REL).is_file():
            return Path(r) / JAR_REL
    return None


def _plantuml(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    jar = plantuml_jar()
    if jar is None:
        raise FileNotFoundError("plantuml jar")
    return subprocess.run(["java", "-Djava.awt.headless=true", "-Xmx512m", "-jar", str(jar), *args], cwd=cwd,
                          capture_output=True, text=True, timeout=120, check=False)


def check_views(ws: Path, render: bool = False) -> dict:
    findings: list[str] = []
    files = {"static": ws / STATIC, "dynamic": ws / DYNAMIC}
    for name, p in files.items():
        if not p.is_file() or not p.read_text(errors="replace").strip():
            findings.append(f"VIEWS:MISSING:{name}:{p.relative_to(ws).as_posix()}")
    if findings:
        return {"verdict": "FAIL", "major_findings": findings, "stats": {}}
    st, dy = files["static"].read_text(errors="replace"), files["dynamic"].read_text(errors="replace")
    for name, txt in (("static", st), ("dynamic", dy)):
        if not re.search(r"^\s*@startuml", txt, re.M) or not re.search(r"^\s*@enduml", txt, re.M):
            findings.append(f"VIEWS:NOT_PLANTUML:{name}")
    if not re.search(r"^\s*(component|package|node|rectangle|interface)\b|\[[^\]]+\]", st, re.M):
        findings.append("VIEWS:STATIC_HAS_NO_COMPONENTS")
    layer = layer_of(ws)  # ADR-0009: an LL work order has no HAL component and no HAL timeout path
    for comp in components(layer):
        if comp not in st:
            findings.append(f"VIEWS:STATIC_MISSING_COMPONENT:{comp}")
    if not re.search(r"^\s*(participant|actor|boundary|control|entity)\b|->", dy, re.M):
        findings.append("VIEWS:DYNAMIC_HAS_NO_SEQUENCE")
    apis = allocated_functions(ws)
    shown = [f for f in apis if f in dy]
    if apis and not shown:
        findings.append("VIEWS:DYNAMIC_SHOWS_NO_ALLOCATED_API")
    if layer != "LL" and "HAL_TIMEOUT" not in dy:
        findings.append("VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH")
    syntax = "NOT_RUN"
    if plantuml_jar() is None:
        findings.append("VIEWS:TOOL_MISSING:plantuml")
    else:
        r = _plantuml(["-checkonly", STATIC, DYNAMIC], ws)
        syntax = "PASS" if r.returncode == 0 else "FAIL"
        if r.returncode != 0:
            findings.append("VIEWS:SYNTAX:" + (r.stdout + r.stderr).strip().replace("\n", " ")[:200])
        elif render:
            rr = _plantuml(["-tsvg", STATIC, DYNAMIC], ws)
            if rr.returncode != 0:
                findings.append("VIEWS:RENDER_FAILED")
    return {"verdict": "FAIL" if findings else "PASS", "major_findings": findings,
            "stats": {"syntax": syntax, "allocated_apis": len(apis), "apis_in_dynamic_view": len(shown)}}
