"""Gate-side defect verification with the cited tests restored from the tool snapshots (ADR-0008, r75).

A FIXED defect is verified by the detecting phase with the SAME tests that failed. r75: the SWE.4 author added new
unit tests (UT-059..) to the cited test_rcc.c before its first post-fix run, so no run ever used the cited version
and DEFECT_TEST_CHANGED rejected the phase although the fix was right. The gate now runs the cited version itself:
a scratch copy of the workspace with the cited files restored byte-identical from `.forge-run/test-snapshots`, the
fixed product code, and the test tool of each cited file. PASS = VERIFIED; FAIL = the fix does not make the cited
test pass, whatever the author did to its copy afterwards.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from ..common import canonical_json, safe_id, sha256_bytes, sha256_file, utc_now

# cited test location -> (server module, operation)
TOOLS = (("software/tests/unit/", "tests", "run_unit"), ("software/tests/integration/", "tests", "run_integration"),
         ("software/tests/target/", "sim", "run_renode"), ("software/tests/software/", "tests", "run_robot"))
SKIP = (".git", "evidence", ".forge-run")  # no integrity history or defect register in the scratch copy
RECEIPT_SCHEMA = "forge-c/normal-test-reverification/1"
_LAST = {}  # synchronous controller handoff only; durable authority is the hash-bound receipt + normal history


def receipt_binding(ws, defect):
    return _LAST.get((str(Path(ws).resolve()), _identifier(defect)))


def _identifier(defect):
    # Preserve the legacy direct helper API, whose minimal fixtures have no id.
    return safe_id(defect.get("id") or "legacy-" + sha256_bytes(canonical_json(defect))[:16])


def _tools_for(files: list[str]) -> list[tuple[str, str]]:
    out = []
    for f in files:
        t = next(((m, op) for prefix, m, op in TOOLS if f.startswith(prefix)), None)
        if t is None:
            return []  # a cited file no test tool runs: cannot re-verify deterministically
        if t not in out:
            out.append(t)
    return out


def reverify(ws: Path, defect: dict, snapshots: Path) -> tuple[str, list[str]]:
    """('PASS' | 'FAIL' | 'UNAVAILABLE', issues) of the cited tests, restored, against the current product code."""
    from ..mcp import sdk
    from ..mcp.servers import sim, tests
    from ..workflow import provided_input_identity as I
    from . import defects as D

    identifier = _identifier(defect)
    _LAST.pop((str(Path(ws).resolve()), identifier), None)

    cited = defect["test_files"]
    tools = _tools_for(sorted(cited))
    if not tools or not all((snapshots / h).is_file() for h in cited.values()):
        return "UNAVAILABLE", ["REVERIFY_UNAVAILABLE:cited test snapshot or test tool missing"]
    try:
        if not all(sha256_file(I.safe_path(ws, (snapshots / h).relative_to(ws).as_posix())) == h for h in cited.values()):
            return "UNAVAILABLE", ["REVERIFY_SNAPSHOT_CHANGED"]
    except (OSError, ValueError) as exc:
        return "UNAVAILABLE", ["REVERIFY_SNAPSHOT_UNAVAILABLE:" + str(exc)[:100]]
    before = D.code_hash(ws)
    manifest = ws / ".forge-run/manifest.json"
    provided = json.loads(manifest.read_text()).get("provided", []) if manifest.is_file() else []
    if provided:
        try:
            for item in provided:
                I.effective_identity(ws, item["path"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return "UNAVAILABLE", ["REVERIFY_APPROVAL_CONTEXT_UNAVAILABLE:" + str(exc)[:150]]
    mods = {"tests": tests, "sim": sim}
    with tempfile.TemporaryDirectory(prefix="forge-reverify-") as tmp:
        copy = Path(tmp) / "ws"
        shutil.copytree(ws, copy, ignore=lambda d, names: [n for n in names if Path(d) == ws and n in SKIP],
                        symlinks=True)
        if provided:
            I.copy_validation_context(ws, copy)
        for f, h in cited.items():
            (copy / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshots / h, copy / f)
            assert sha256_file(copy / f) == h
        issues: list[str] = []
        status = "PASS"
        outcomes = []
        for mod, op in tools:
            o = next(x for x in mods[mod].OPERATIONS if x.name == op)
            ctx = sdk.ToolContext(f"forge-{mod}-mcp", op, "route-gate", defect["detected_phase"], copy,
                                  "reverify")
            res = o.handler(ctx, o.model())
            outcomes.append({"server": ctx.server, "op": op, "invocation_id": ctx.invocation_id, "result": res})
            I.copy_artifacts(copy, ws, res.get("artifact_refs", []))
            if res["status"] != "PASS":
                status = "FAIL"
                issues += [f"{op}:{i}" for i in res.get("issues", [])[:6]]
        if D.code_hash(ws) != before:
            return "UNAVAILABLE", ["REVERIFY_SOURCE_CHANGED_DURING_EXECUTION"]
        # The approval context is optional for legacy workspaces, mandatory when
        # effective_identity has authorized a corrected provided LL.
        from .engine import Store

        store = Store(ws)
        baseline = store.latest_baseline("SWE.3")
        inspections = store.inspections("SWE.3")
        receipt = {"schema": RECEIPT_SCHEMA, "defect": {k: v for k, v in defect.items() if k not in ("status", "history")},
                   "code_sha256": before, "cited_test_sha256": cited, "status": status, "tools": outcomes,
                   "phase3_baseline_sha256": sha256_bytes(canonical_json(baseline)) if baseline else None,
                   "phase3_inspection_sha256": sha256_bytes(canonical_json(inspections[-1])) if inspections else None,
                   "created_at": utc_now()}
        raw = canonical_json(receipt)
        digest = sha256_bytes(raw)
        rel = ".forge-run/reverify/" + identifier + "/" + digest + ".json"
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw:
                return "UNAVAILABLE", ["REVERIFY_RECEIPT_COLLISION"]
        else:
            path.write_bytes(raw)
            path.chmod(0o444)
        if status == "PASS":
            _LAST[(str(ws.resolve()), identifier)] = {"path": rel, "sha256": digest}
        return status, issues


def validate_receipt(ws, defect, event, fixed, baseline, inspection, file_row):
    """Pure check of normal controller execution evidence, not an asserted tools/status string."""
    from ..common import schema_errors
    from ..workflow import provided_input_identity as I
    from . import defects as D

    ref = event.get("reverify_receipt") or {}
    I.require(set(ref) == {"path", "sha256"} and ref["path"].startswith(".forge-run/reverify/" + defect["id"] + "/"),
              "REVERIFY_RECEIPT_UNBOUND")
    path = I.safe_path(ws, ref["path"])
    I.require(sha256_file(path) == ref["sha256"], "REVERIFY_RECEIPT_CHANGED")
    frame = json.loads(path.read_text())
    I.require(frame.get("schema") == RECEIPT_SCHEMA and frame.get("status") == "PASS"
              and frame["defect"] == {k: v for k, v in defect.items() if k not in ("status", "history")}
              and frame["cited_test_sha256"] == defect["test_files"]
              and fixed["ts"] < frame["created_at"] <= event["ts"], "REVERIFY_RECEIPT_CONTEXT_CHANGED")
    from .engine import Store

    store = Store(Path(ws))
    measured_baseline = next((b for b in store.baselines("SWE.3")
                              if sha256_bytes(canonical_json(b)) == frame["phase3_baseline_sha256"]), None)
    I.require(measured_baseline is not None, "REVERIFY_BASELINE_UNBOUND")
    I.historical_correction(ws, measured_baseline, file_row["path"], file_row)
    import hashlib
    from pathlib import PurePosixPath

    code = hashlib.sha256()
    for root in D.CODE_DIRS:
        for rel in sorted((r for r in measured_baseline["files"] if r.startswith(root + "/")),
                          key=lambda r: PurePosixPath(r).parts):
            code.update(rel.encode() + b"\0" + measured_baseline["files"][rel].encode())
    I.require(frame["code_sha256"] == code.hexdigest(), "REVERIFY_CODE_SNAPSHOT_CHANGED")
    checks = store.applicable(store.checklist("SWE.3"))["checks"]
    I.require(any(sha256_bytes(canonical_json(i)) == frame["phase3_inspection_sha256"]
                  and i.get("baseline_id") == measured_baseline["baseline_id"]
                  and i.get("baseline_hash") == measured_baseline["baseline_hash"]
                  and i.get("verdict") == "PASS" and i.get("author_role") == "swe3-author"
                  and i.get("inspector_role") == "swe3-inspector" and i.get("checklist_sha256") == inspection["checklist_sha256"]
                  and i["recorded_at"] <= frame["created_at"]
                  and all(i.get("items", {}).get(c["id"], {}).get("verdict") == "PASS"
                          for c in checks if c.get("required")) for i in store.inspections("SWE.3")),
              "REVERIFY_INSPECTION_UNBOUND")
    expected = [("forge-" + mod + "-mcp", op) for mod, op in _tools_for(sorted(defect["test_files"]))]
    I.require(bool(expected) and [(r["server"], r["op"]) for r in frame["tools"]] == expected,
              "REVERIFY_TOOL_SET_CHANGED")
    for row in frame["tools"]:
        result = row["result"]
        I.require(result["status"] == "PASS" and not schema_errors("tool-result.schema.json", result)
                  and result["provenance"]["invocation_id"] == row["invocation_id"], "REVERIFY_TOOL_RESULT_INVALID")
        I.artifact_paths(ws, result.get("artifact_refs", []))
    for sha in defect["test_files"].values():
        I.require(sha256_file(I.safe_path(ws, D.SNAPSHOTS + "/" + sha)) == sha, "REVERIFY_SNAPSHOT_CHANGED")
