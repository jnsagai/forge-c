"""Static policy for agent-written Robot Framework suites, applied by run_robot BEFORE Robot executes anything.

A Robot suite is code. Without this check an SWE.6 author could run arbitrary shell commands through `run_robot`
(r57 imported the `Process` library and called an invented shell script with shell=True), bypassing its MCP-only
grant. Allowed: `Library    ForgeTarget` only; no Resource/Variables imports; no inline Python (`${{...}}`); every
keyword call (test steps, user keywords, setups/teardowns, templates) must be a ForgeTarget keyword, a keyword
defined in the same file, or a small BuiltIn subset with no code evaluation or dynamic dispatch.
"""
from __future__ import annotations

import re
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


# ---- requirement observability (ADR-0008, r60/r63) -----------------------------------------------------------
# A requirement-tagged test must observe what the requirement demands. r60 and r63 tagged SWR-014 ("shall return
# HAL_ERROR without any register write") on scenarios whose checks never mention HAL_ERROR: traced, never verified.
HAL_STATUS = re.compile(r"\bHAL_(?:OK|ERROR|TIMEOUT|BUSY)\b")
REG_FIELD = re.compile(r"\bRCC_[A-Z0-9]+\.([A-Z][A-Z0-9_]+)\b")
TCHECK = re.compile(r"TCHECK\(\s*([^,]+?)\s*,(.*?)\)\s*;", re.S)


def required_tokens(requirement_text: str) -> tuple[set[str], set[str]]:
    return set(HAL_STATUS.findall(requirement_text)), set(REG_FIELD.findall(requirement_text))


def _checks(scenario: Path) -> dict[str, str]:
    if not scenario.is_file():
        return {}
    return {m.group(1).strip(): m.group(2) for m in TCHECK.finditer(scenario.read_text(errors="replace"))}


def observed_checks(suite: Path) -> dict[str, list[tuple[str, str | None]]]:
    """SWR tag -> [(scenario file, check id or None for all checks)] from the suite's keyword calls (user keywords
    defined in the same file are expanded with their positional arguments)."""
    from robot.api import get_model
    from robot.api.parsing import ModelVisitor

    user: dict[str, tuple[list[str], list[list[str]]]] = {}
    tests: list[tuple[list[str], list[list[str]]]] = []

    class V(ModelVisitor):
        def visit_Keyword(self, node):  # noqa: N802
            args, body = [], []
            for st in node.body:
                if type(st).__name__ == "Arguments":
                    args = [t.value for t in st.get_tokens("ARGUMENT")]
                elif type(st).__name__ == "KeywordCall":
                    body.append([st.keyword, *st.args])
            user[_norm(node.name)] = (args, body)

        def visit_TestCase(self, node):  # noqa: N802
            tags, body = [], []
            for st in node.body:
                if type(st).__name__ == "Tags":
                    tags = list(st.values)
                elif type(st).__name__ == "KeywordCall":
                    body.append([st.keyword, *st.args])
            tests.append((tags, body))

    V().visit(get_model(str(suite)))

    def expand(call: list[str], depth: int = 0) -> list[list[str]]:
        k = _norm(call[0])
        if k in user and depth < 5:
            args, body = user[k]
            sub = dict(zip(args, call[1:], strict=False))  # missing args stay unexpanded
            out = []
            for c in body:
                for a, v in sub.items():
                    c = [x.replace(a, v) for x in c]
                out += expand(c, depth + 1)
            return out
        return [call]

    res: dict[str, list[tuple[str, str | None]]] = {}
    for tags, body in tests:
        cur, obs = "", []
        for call in [c for b in body for c in expand(b)]:
            k = _norm(call[0])
            if k == "run target scenario" and len(call) > 1:
                cur = call[1]
            elif k == "target check should pass" and len(call) > 1 and cur:
                obs.append((cur, call[1].strip()))
            elif k == "all target checks should pass" and cur:
                obs.append((cur, None))
        for t in tags:
            res.setdefault(t, []).extend(obs)
    return res


def unobserved_requirements(suite: Path, scenario_dir: Path, requirements: dict[str, str]) -> list[str]:
    issues = []
    obs = observed_checks(suite)
    for rid, text in sorted(requirements.items()):
        hal, fields = required_tokens(text)
        if not (hal or fields) or rid not in obs:
            continue  # size/budget requirements and untagged ids are judged by the other checks
        exprs = []
        for scn, cid in obs[rid]:
            checks = _checks(scenario_dir / scn)
            exprs += [e for i, e in checks.items() if cid is None or i == cid or not i.isdigit()]
        blob = " ".join(exprs)
        missing = sorted(h for h in hal if h not in blob) if hal else \
            ([] if any(f in blob for f in fields) else sorted(fields))
        if missing:
            issues.append(f"REQUIREMENT_NOT_OBSERVED:{rid}:{','.join(missing)} (the tagged checks never test it)")
    return issues
