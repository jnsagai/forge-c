"""Static policy for agent-written Robot Framework suites, applied by run_robot BEFORE Robot executes anything.

A Robot suite is code. Without this check an SWE.6 author could run arbitrary shell commands through `run_robot`
(r57 imported the `Process` library and called an invented shell script with shell=True), bypassing its MCP-only
grant. Allowed: `Library    ForgeTarget` only; no Resource/Variables imports; no inline Python (`${{...}}`); every
keyword call (test steps, user keywords, setups/teardowns, templates) must be a ForgeTarget keyword, a keyword
defined in the same file, or a small BuiltIn subset with no code evaluation or dynamic dispatch.
"""
from __future__ import annotations

from pathlib import Path

ALLOWED_LIBRARIES = {"forgetarget"}
FORGE_KEYWORDS = {"run target scenario", "target check should pass", "all target checks should pass",
                  "driver flash size should be at most", "driver static ram should be at most"}
# BuiltIn subset: logging and literal comparisons only. Deliberately excluded: Evaluate, Should Be True (evaluates
# Python), Call Method, Import Library/Resource/Variables, Run Keyword* (dynamic dispatch), Set Library Search Order.
SAFE_BUILTINS = {"log", "comment", "no operation", "should be equal", "should not be equal",
                 "should be equal as integers", "should be equal as numbers", "should be equal as strings",
                 "should contain", "should not contain", "set test variable", "set suite variable", "fail"}


def _norm(name: str) -> str:
    n = " ".join(name.replace("_", " ").split()).lower()
    for prefix in ("forgetarget.", "builtin."):
        if n.startswith(prefix):
            n = n[len(prefix):].strip()
    return n


def check_suite(path: Path) -> list[str]:
    from robot.api.parsing import ModelVisitor, get_model

    text = path.read_text(errors="replace")
    issues: list[str] = []
    if "${{" in text:
        issues.append(f"ROBOT_POLICY:INLINE_PYTHON:{path.name}")
    model = get_model(str(path))
    defined: set[str] = set()
    calls: list[tuple[str, int]] = []

    class V(ModelVisitor):
        def visit_LibraryImport(self, node):  # noqa: N802 - Robot visitor API
            if (node.name or "").strip().lower() not in ALLOWED_LIBRARIES:
                issues.append(f"ROBOT_POLICY:LIBRARY_NOT_ALLOWED:{node.name}:line {node.lineno}")

        def visit_ResourceImport(self, node):  # noqa: N802
            issues.append(f"ROBOT_POLICY:RESOURCE_IMPORT:{node.name}:line {node.lineno}")

        def visit_VariablesImport(self, node):  # noqa: N802
            issues.append(f"ROBOT_POLICY:VARIABLES_IMPORT:{node.name}:line {node.lineno}")

        def visit_KeywordName(self, node):  # noqa: N802
            defined.add(_norm(node.name))

        def visit_KeywordCall(self, node):  # noqa: N802
            if node.keyword:
                calls.append((node.keyword, node.lineno))

        def visit_Fixture(self, node):  # noqa: N802 - Suite/Test Setup/Teardown, [Setup]/[Teardown]
            if node.name and node.name.upper() != "NONE":
                calls.append((node.name, node.lineno))

        def visit_TestTemplate(self, node):  # noqa: N802
            if node.value:
                calls.append((node.value, node.lineno))

        def visit_Template(self, node):  # noqa: N802
            if node.value:
                calls.append((node.value, node.lineno))

    V().visit(model)
    for kw, line in calls:
        n = _norm(kw)
        if "${" in kw or "@{" in kw or "&{" in kw:
            issues.append(f"ROBOT_POLICY:DYNAMIC_KEYWORD:{kw[:40]}:line {line}")
        elif n not in FORGE_KEYWORDS and n not in SAFE_BUILTINS and n not in defined:
            issues.append(f"ROBOT_POLICY:KEYWORD_NOT_ALLOWED:{kw[:40]}:line {line}")
    return issues
