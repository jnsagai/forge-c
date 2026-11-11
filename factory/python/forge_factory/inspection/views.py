"""SWE.2 architecture views in PlantUML (static + dynamic) - deterministic checks and rendering.

The SWE.2 author writes `architecture_static.puml` (component view) and `architecture_dynamic.puml` (sequence
view). This module checks them with the pinned PlantUML (Apache-2.0 build, `-checkonly` syntax check), checks
their content against the architecture (driver components and allocated HAL APIs appear; the dynamic view of a HAL
that waits covers a timeout path, CAPA-124), and renders SVGs next to them (before the baseline is frozen).
Backs checklist item SWE2-08.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ..layer import components, hal_standalone, hal_waits, layer_of, profile
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


def _plantuml(args: list[str], cwd: Path, *, source: str | None = None) -> subprocess.CompletedProcess:
    jar = plantuml_jar()
    if jar is None:
        raise FileNotFoundError("plantuml jar")
    return subprocess.run(["java", "-Djava.awt.headless=true", "-Xmx512m", "-jar", str(jar), *args], cwd=cwd,
                          input=source, capture_output=True, text=True,
                          timeout=15 if source is not None else 120, check=False)


# CAPA-229 (owner SWE.2 review 2026-11-11, WWDG HAL L35 passed with these flaws): deterministic view rules of SWE2-08.
_PART = re.compile(r'^\s*(participant|actor|boundary|control|entity|database|collections|queue)\s+'
                   r'(?:"([^"]+)"|(\S+))(?:\s+as\s+(\w+))?', re.I)
_MSG = re.compile(r'^\s*("[^"]+"|[\w.]+)\s*(<<?-{1,2}|-{1,2}>{1,2})\s*("[^"]+"|[\w.]+)\s*(?::\s*(.*))?$')
_OPEN = re.compile(r"^\s*(group|alt|opt|loop|par|break|critical)\b", re.I)
_END = re.compile(r"^\s*end\s*$", re.I)
_NOTE_OPEN = re.compile(r"^\s*[hr]?note\b[^:]*$", re.I)
_NOTE_END = re.compile(r"^\s*end\s*[hr]?note\b", re.I)
_CALLER = re.compile(r"caller|application|\buser\b", re.I)


def _role(name: str, label: str, kind: str, hal: str, ll: str) -> str:
    if kind.lower() == "actor" or _CALLER.search(name) or _CALLER.search(label):
        return "caller"
    if name == "SWC_HAL" or hal in label or hal in name or name.upper() == "HAL":  # RPR-124: module-named elements
        return "hal"
    if name == "SWC_LL" or ll in label or ll in name or name.upper() == "LL":
        return "ll"
    return "registers"


def view_rules(ws: Path, st: str, dy: str, layer: str, apis: list[str]) -> list[str]:
    """No stray PlantUML file next to the two views; a HAL's dynamic view shows every allocated HAL API; when the
    dynamic view uses function blocks (group), every message is inside one; the Caller sends no message labelled as a
    return; a HAL on the
    provided LL never exchanges a message with the register block; every kind of interaction the dynamic view shows
    (HAL-LL, LL-registers) is an interface (connection) of the static view."""
    f = [f"VIEWS:STRAY_PLANTUML:{p.name}" for p in sorted((ws / STATIC).parent.glob("*.puml"))
         if p.name not in (Path(STATIC).name, Path(DYNAMIC).name)]
    if layer != "LL":
        f += [f"VIEWS:DYNAMIC_MISSING_API:{a}" for a in apis if not re.search(rf"\b{re.escape(a)}\b", dy)]
    p = profile(ws)
    hal, ll = Path(p["hal"]["header"]).stem, Path(p["ll"]["header"]).stem
    on_ll = layer != "LL" and not hal_standalone(ws)
    roles = {}
    for line in dy.splitlines():
        m = _PART.match(line)
        if m:
            label = m.group(2) or m.group(3)
            roles[m.group(4) or label] = _role(m.group(4) or label, label, m.group(1), hal, ll)
    grouped = any(re.match(r"^\s*group\b", x, re.I) for x in dy.splitlines())
    depth, note, kinds = 0, False, set()
    for n, line in enumerate(dy.splitlines(), 1):
        if note:
            note = not _NOTE_END.match(line)
            continue
        if _NOTE_OPEN.match(line):
            note = True
            continue
        if _OPEN.match(line):
            depth += 1
            continue
        if _END.match(line):
            depth = max(0, depth - 1)
            continue
        m = _MSG.match(line)
        if not m:
            continue
        a, arrow, b, label = m.group(1).strip('"'), m.group(2), m.group(3).strip('"'), (m.group(4) or "").strip()
        if arrow.startswith("<"):
            a, b = b, a
        ra, rb = roles.get(a), roles.get(b)
        if grouped and depth == 0:
            f.append(f"VIEWS:MESSAGE_OUTSIDE_FUNCTION_BLOCK:line {n}")
        if ra == "caller" and rb != "caller" and label.lower().startswith("return"):  # dashed calls are a style
            f.append(f"VIEWS:RETURN_FROM_CALLER:line {n}")
        if on_ll and {ra, rb} == {"hal", "registers"}:
            f.append(f"VIEWS:HAL_BYPASSES_LL:line {n}")
        if {ra, rb} in ({"hal", "ll"}, {"ll", "registers"}):
            kinds.add(frozenset((ra, rb)))
    if kinds and layer != "LL+HAL":
        from .swtrace import parse_architecture

        model = parse_architecture(st)
        decl = {m.group(2): m.group(1) for m in re.finditer(r'^\s*\w+\s+"([^"]+)"[^\n]*?\s+as\s+(\w+)', st, re.M)}
        have = {frozenset((_role(c["from"], decl.get(c["from"], ""), "", hal, ll),
                           _role(c["to"], decl.get(c["to"], ""), "", hal, ll))) for c in model["interfaces"]}
        names = {frozenset(("hal", "ll")): "HAL-LL", frozenset(("ll", "registers")): "LL-REGISTERS"}
        f += [f"VIEWS:STATIC_MISSING_INTERFACE:{names[k]}" for k in sorted(kinds, key=names.get) if k not in have]
    return f


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
    for comp in components(layer, ws):
        if comp not in st:
            findings.append(f"VIEWS:STATIC_MISSING_COMPONENT:{comp}")
    if not re.search(r"^\s*(participant|actor|boundary|control|entity)\b|->", dy, re.M):
        findings.append("VIEWS:DYNAMIC_HAS_NO_SEQUENCE")
    apis = allocated_functions(ws)
    shown = [f for f in apis if f in dy]
    if apis and not shown:
        findings.append("VIEWS:DYNAMIC_SHOWS_NO_ALLOCATED_API")
    rules = view_rules(ws, st, dy, layer, apis)  # CAPA-229: reported after the view's own syntax/render findings
    # CAPA-124: only a HAL with a bounded wait has a timeout path (a no-wait HAL such as CRC returns no HAL_TIMEOUT)
    # F015/F016: ST's standalone CRC/GPIO/TIM HAL never waits unless its profile names a time base
    timeout_required = layer != "LL" and hal_waits(ws) and (
        not hal_standalone(ws) or bool(profile(ws)["hal"].get("time_base")))
    if timeout_required and "HAL_TIMEOUT" not in dy:
        findings.append("VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH")
    syntax = "NOT_RUN"
    syntax_by_view = {name: "NOT_RUN" for name in files}
    if plantuml_jar() is None:
        findings.append("VIEWS:TOOL_MISSING:plantuml")
    else:
        # PlantUML can report only a generic error for a multi-file invocation.
        # Name the failing source without weakening the complete workspace check.
        for name, path in files.items():
            rel = path.relative_to(ws).as_posix()
            r = _plantuml(["-checkonly", rel], ws)
            syntax_by_view[name] = "PASS" if r.returncode == 0 else "FAIL"
            if r.returncode != 0:
                detail = (r.stdout + r.stderr).strip().replace("\n", " ")[:200]
                # The pinned CLI's stdin syntax mode reports a zero-based line.
                # This extra diagnostic cannot turn the failed file check into PASS.
                text = path.read_text(errors="replace")
                try:
                    diagnostic = _plantuml(["-syntax"], path.parent, source=text)
                    lines = diagnostic.stdout.splitlines()
                    if (diagnostic.returncode != 0 and len(lines) >= 3 and lines[0] == "ERROR"
                            and re.fullmatch(r"[0-9]{1,8}", lines[1])
                            and 0 <= int(lines[1]) < len(text.splitlines())):
                        detail = f"line {int(lines[1]) + 1}:" + lines[2][:160]
                except (OSError, subprocess.SubprocessError):
                    pass  # retain the original failure when optional diagnostics are unavailable
                findings.append("VIEWS:SYNTAX:" + rel + ":" + detail)
        syntax = "PASS" if all(v == "PASS" for v in syntax_by_view.values()) else "FAIL"
        if syntax == "PASS" and render:
            rr = _plantuml(["-tsvg", STATIC, DYNAMIC], ws)
            if rr.returncode != 0:
                findings.append("VIEWS:RENDER_FAILED")
    findings += rules
    return {"verdict": "FAIL" if findings else "PASS", "major_findings": findings,
            "stats": {"syntax": syntax, "allocated_apis": len(apis), "apis_in_dynamic_view": len(shown),
                      "timeout_path_required": timeout_required,
                      "checked_static": STATIC, "checked_dynamic": DYNAMIC,
                      **{"syntax_" + name: status for name, status in syntax_by_view.items()}}}
