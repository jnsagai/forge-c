"""F011-T005: static checks of the authored feature 011 package (no runtime, no model, no SafeC binary).

    python -m forge_factory.safec_bridge.static_check [--out <json>]

- Both bridge schemas are valid JSON Schema 2020-12, and the frozen example messages validate (or are rejected) as
  the fixture states.
- Every repository path the feature documents name resolves to a file, a directory or a git branch. Paths the plan
  lists as proposed new files are reported as PROPOSED until they exist; anything else unresolved is MISSING.
A capability is never inferred from prose: this module only resolves names.
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import re
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, pretty_json

FEATURE = "specs/011-safec-semantic-first"
DOCS = ("CLAUDE_FEATURE011_START.md", "docs/adr/ADR-0015-safec-semantic-boundary.md",
        *(f"{FEATURE}/{n}.md" for n in ("spec", "plan", "research", "data-model", "acceptance-tests", "tasks",
                                        "validation", "quickstart")))
SCHEMAS = {"request": f"{FEATURE}/contracts/bridge-request.schema.json",
           "result": f"{FEATURE}/contracts/bridge-result.schema.json"}
EXAMPLES = "factory/python/tests/fixtures/safec_bridge/examples.json"
# where a bare file name in the documents is meant to live
SEARCH = ("", f"{FEATURE}/", "docs/adr/", "evidence/v0.4/runs/", "factory/python/forge_factory/",
          "factory/python/forge_factory/lrtx/", "factory/python/forge_factory/safec_bridge/")


def _braces(ref: str) -> list[str]:
    m = re.search(r"\{([^{}]+)\}", ref)
    if not m:
        return [ref]
    return [x for alt in m.group(1).split(",") for x in _braces(ref[:m.start()] + alt + ref[m.end():])]


def references(repo: Path) -> list[str]:
    refs = set()
    for doc in DOCS:
        for ref in re.findall(r"`([^`\s]+)`", (repo / doc).read_text()):
            if "/" in ref.strip("/") or re.search(r"\.(md|py|json|yaml|sh)$", ref):
                refs.add(ref)
    return sorted(refs)


def proposed(repo: Path) -> set[str]:
    """Bare names of the new files the plan's 'Source/project changes (proposed; not yet present)' block lists."""
    text = (repo / FEATURE / "plan.md").read_text()
    block = text.split("## Source/project changes", 1)[1].split("```", 2)[1]
    names = set()
    for line in block.splitlines():
        m = re.match(r"\s*(\S+)", line)
        if m and "/" in m.group(1):
            for p in _braces(m.group(1)):
                names.add(p)
                names.add(Path(p).name)
    return names


def _branch(repo: Path, ref: str) -> bool:
    return any(subprocess.run(["git", "rev-parse", "--verify", "--quiet", r], cwd=repo,
                              capture_output=True).returncode == 0 for r in (ref, f"origin/{ref}"))


def resolve(repo: Path, ref: str, planned: set[str]) -> dict:
    hits = []
    for alt in _braces(ref):
        found = [p for prefix in SEARCH for p in glob.glob(str(repo / (prefix + alt)))]
        hits.append(bool(found) or _branch(repo, alt))
    if all(hits):
        return {"ref": ref, "status": "RESOLVED"}
    missing = [alt for alt, ok in zip(_braces(ref), hits, strict=True) if not ok]
    if all(any(fnmatch.fnmatchcase(m, p) or fnmatch.fnmatchcase(Path(m).name, p) for p in planned) for m in missing):
        return {"ref": ref, "status": "PROPOSED", "not_yet_present": missing}
    return {"ref": ref, "status": "MISSING", "unresolved": missing}


def schema_check(repo: Path) -> dict:
    from jsonschema import Draft202012Validator

    out = {}
    validators = {}
    for name, rel in SCHEMAS.items():
        schema = json.loads((repo / rel).read_text())
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(schema)
        out[name] = {"path": rel, "id": schema["$id"], "status": "VALID_2020_12"}
    ex = json.loads((repo / EXAMPLES).read_text())
    rows = []
    for case in ex["cases"]:
        errors = sorted(e.message for e in validators[case["schema"]].iter_errors(case["message"]))
        ok = (not errors) == case["valid"]
        rows.append({"id": case["id"], "expected_valid": case["valid"], "errors": len(errors), "as_expected": ok})
    out["examples"] = rows
    return out


def check(repo: Path = REPO_ROOT) -> dict:
    planned = proposed(repo)
    refs = [resolve(repo, r, planned) for r in references(repo)]
    schemas = schema_check(repo)
    bad = [r for r in refs if r["status"] == "MISSING"] + [e for e in schemas["examples"] if not e["as_expected"]]
    return {"schema": "forge-c/f011-static-check/1", "references": refs, "schemas": schemas,
            "status": "PASS" if not bad else "FAIL"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    res = check()
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(pretty_json(res))
    counts = {s: sum(r["status"] == s for r in res["references"]) for s in ("RESOLVED", "PROPOSED", "MISSING")}
    print(json.dumps({"status": res["status"], "references": counts,
                      "missing": [r for r in res["references"] if r["status"] == "MISSING"],
                      "examples": sum(e["as_expected"] for e in res["schemas"]["examples"])}))
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
