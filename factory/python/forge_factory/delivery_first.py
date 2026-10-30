"""Delivery-first experiment inside the existing native graph, verifier and finalizer.

This reports a functional slice separately from process/release acceptance. It
never supplies candidate implementation code or changes the strict release gates.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .afo.durable import immutable_bytes, immutable_json
from .common import pretty_json, sha256_file, utc_now
from .development_demonstration import validate_inputs
from .mcp.sdk import ToolContext, run_argv

MODE = "QM_DELIVERY_FIRST_DEMO"
FIELD = "delivery_first"


def contract(man):
    value = man.get(FIELD)
    if value is None:
        return None
    from .development_execution import DEMO

    if (not isinstance(value, dict) or man.get("purpose") != "QM" or (man.get("development_execution") or {}).get("name") != DEMO
            or man.get("delivery") or value.get("schema") != "forge-c/delivery-first/1"):
        raise ValueError("DELIVERY_FIRST_REQUIRES_NEW_GREENFIELD_QM_DEMONSTRATION")
    paths = value.get("candidate_files")
    names = value.get("required_functions")
    if (not isinstance(paths, list) or not paths or len(paths) != len(set(paths))
            or not isinstance(names, list) or not names or len(names) != len(set(names))
            or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z_]\w*", n) for n in names)
            or names != (man.get("operation_scope") or {}).get("functions")
            or value.get("max_corrections") != 2):
        raise ValueError("DELIVERY_FIRST_SCOPE_INVALID")
    for key in ("contract", "host_oracle", "target_probe", *(["unit_harness"] if "unit_harness" in value else [])):
        raw = value.get(key)
        if not isinstance(raw, str) or not raw.startswith("inputs/") or raw not in {
                i["path"] for i in man.get("inputs", [])}:
            raise ValueError("DELIVERY_FIRST_INPUT_NOT_DECLARED:" + key)
    if (not isinstance(value.get("include_dirs"), list) or not value["include_dirs"]
            or any(not isinstance(p, str) for p in paths + value["include_dirs"])):
        raise ValueError("DELIVERY_FIRST_PATHS_INVALID")
    return value


def selected(ws):
    path = Path(ws) / ".forge-run/manifest.json"
    if not path.is_file():
        return None, {}
    man = json.loads(path.read_text())
    return contract(man), man


def context(ws):
    return ToolContext("forge-tests-mcp", "delivery_first", "swe3-author", "SWE.3", Path(ws).resolve(), "delivery-first")


def include_flags(ws):
    """The declared adapter's includes, only on explicitly selected work orders."""
    path = Path(ws) / ".forge-run/manifest.json"
    if not path.is_file():
        return []
    cfg, _ = selected(ws)
    if cfg is None:
        return []
    ctx = context(ws)
    return [arg for raw in cfg["include_dirs"] for arg in ("-I", str(ctx.path(raw, must_exist=False)))]


def checked_paths(ws, cfg):
    ctx = context(ws)
    from .policy.authz import Authorizer, Binding

    auth = Authorizer(Binding("delivery-first", str(ctx.workspace), {"author": {"role": "swe3-author", "phase": "SWE.3"}}))
    paths = {}
    for raw in cfg["candidate_files"]:
        p = ctx.path(raw, must_exist=False)
        if not auth.decide("author", "write_file", {"file_path": raw}).allow:
            raise ValueError("DELIVERY_FIRST_CANDIDATE_PATH_DENIED:" + raw)
        paths[raw] = p
    for raw in cfg["include_dirs"]:
        ctx.path(raw, must_exist=False)
    return paths


def preflight(ws):
    cfg, man = selected(ws)
    if not cfg:
        raise ValueError("DELIVERY_FIRST_NOT_SELECTED")
    validate_inputs(ws)
    paths = checked_paths(ws, cfg)
    initial = Path(ws) / ".forge-run/delivery-first/initial.json"
    if initial.exists():
        record = json.loads(initial.read_text())
        if record["contract"] != cfg:
            raise ValueError("DELIVERY_FIRST_CONTRACT_CHANGED")
        return record
    if any(p.exists() for p in paths.values()):
        raise ValueError("DELIVERY_FIRST_INITIAL_CANDIDATE_MUST_BE_ABSENT")
    record = {"at": utc_now(), "mode": MODE, "work_order": man["work_order"],
              "factory_revision": man.get("factory_revision"), "contract": cfg,
              "candidate_initially_absent": True, "candidate_code_substituted": False,
              "inputs": man["inputs"], "local_profile": man.get("local_profile"),
              "authorship": "NATIVE_WRITE_EVENTS_REQUIRED"}
    immutable_json(initial, record)
    return record


def verify(ws, attempt):
    """Real tool calls; archive every candidate before compiling, with no hidden retries."""
    from .mcp.servers.build import PROFILES, WARN

    ws = Path(ws).resolve()
    cfg, man = selected(ws)
    if not cfg or attempt not in (0, 1, 2):
        raise ValueError("DELIVERY_FIRST_ATTEMPT_INVALID")
    validate_inputs(ws)
    if not (ws / ".forge-run/delivery-first/initial.json").is_file():
        raise ValueError("DELIVERY_FIRST_PREFLIGHT_REQUIRED")
    paths = checked_paths(ws, cfg)
    root = ws / ".forge-run/delivery-first" / ("attempt-" + str(attempt))
    if attempt and not (root.parent / ("attempt-" + str(attempt - 1)) / "result.json").is_file():
        raise ValueError("DELIVERY_FIRST_PREVIOUS_ATTEMPT_REQUIRED")
    receipt = root / "result.json"
    current = {raw: sha256_file(p) if p.is_file() else None for raw, p in paths.items()}
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old["candidate_hashes"] != current:
            raise ValueError("DELIVERY_FIRST_COMPLETED_ATTEMPT_CHANGED")
        return old
    # An interrupted tool attempt is evidence, never a fresh correction reservation.
    if (root / "intent.json").exists():
        raise ValueError("DELIVERY_FIRST_INCOMPLETE_ATTEMPT_REQUIRES_RECONCILIATION")
    root.mkdir(parents=True, exist_ok=True)
    immutable_json(root / "intent.json", {"at": utc_now(), "attempt": attempt, "candidate_hashes": current})
    for raw, p in paths.items():
        if p.is_file():
            immutable_bytes(root / "candidate" / raw, p.read_bytes())
    missing = [raw for raw, digest in current.items() if digest is None]
    calls = []
    if not missing:
        ctx = context(ws)
        includes = [arg for raw in cfg["include_dirs"] for arg in ("-I", str(ctx.path(raw)))]
        sources = [str(p) for p in paths.values() if p.suffix == ".c"]
        for label, profname, fixture in (("host_compile", "host-clang", "host_oracle"),
                                         ("target_compile", "target-cm55-gcc", "target_probe")):
            prof = PROFILES[profname]
            dest = root / ("oracle" if label == "host_compile" else "probe.o")
            argv = [prof["cc"], *prof["flags"], *WARN, *includes, str(ctx.path(cfg[fixture], kind="file")),
                    *sources, *(["-c"] if label == "target_compile" and not sources else []), "-o", str(dest)]
            # Multi-source target link requires a target adapter; do not silently
            # claim it as a successful object-only verification.
            if label == "target_compile" and sources:
                calls.append({"check": label, "status": "NOT_RUN", "reason": "TARGET_MULTISOURCE_ADAPTER_REQUIRED"})
                continue
            calls.append(_call(root, label, argv, ws, {prof["cc"]}))
        if calls[0]["status"] == "PASS":
            calls.append(_call(root, "independent_behavior", [str(root / "oracle")], ws, {"oracle"}))
    outcomes = {c["check"]: c["status"] for c in calls}
    passed = not missing and all(outcomes.get(k) == "PASS" for k in
                                ("host_compile", "target_compile", "independent_behavior"))
    unchanged = current == {raw: sha256_file(p) if p.is_file() else None for raw, p in paths.items()}
    result = {"at": utc_now(), "mode": MODE, "attempt": attempt, "correction_count": attempt,
              "work_order": man["work_order"], "factory_revision": man.get("factory_revision"),
              "candidate_hashes": current, "candidate_unchanged_during_checks": unchanged,
              "status": "PASS" if passed and unchanged else "FAIL", "missing": missing, "calls": calls,
              "verification_scope": "DECLARED_HOST_BEHAVIOR_AND_TARGET_COMPILATION_ONLY",
              "simulation": "NOT_RUN", "physical_hardware": "NOT_RUN",
              "authorship": "NATIVE_WRITE_EVENTS_REQUIRED", "release_eligibility": "BLOCKED"}
    immutable_json(receipt, result)
    # A convenience pointer, not an overwrite of a failed attempt's evidence.
    (root.parent / "latest.json").write_text(pretty_json(result))
    return result


def _call(root, label, argv, ws, allow):
    import shutil

    if not shutil.which(argv[0]):
        return {"check": label, "status": "NOT_RUN", "reason": "TOOL_MISSING:" + argv[0]}
    r = run_argv(argv, ws, 60, allow)
    immutable_bytes(root / (label + ".stdout"), r.stdout)
    immutable_bytes(root / (label + ".stderr"), r.stderr)
    return {"check": label, "status": "PASS" if r.exit_code == 0 else "FAIL", "argv": argv,
            "exit_code": r.exit_code, "duration_ms": round(r.duration_ms, 1), "timed_out": r.timed_out,
            "stdout_sha256": sha256_file(root / (label + ".stdout")),
            "stderr_sha256": sha256_file(root / (label + ".stderr"))}


def workflow(graph, nodes, manifest, command_env, python):
    """Prepend a three-attempt native author/check sequence; reuse all six phase nodes."""
    from .workflow.builder import _q

    cfg = contract(manifest)
    if cfg is None:
        return graph, nodes
    nodes = dict(nodes)
    edge = re.search(r"^  start -> (\w+)\n", graph, re.M)
    if edge is None:
        raise ValueError("DELIVERY_FIRST_START_EDGE_MISSING")
    continuation = edge[1]
    graph = graph[:edge.start()] + graph[edge.end():]
    # The native fast author already generated this candidate. Re-running a
    # second generator using the legacy array API would replace its pointer API.
    # Keep the existing compile/fix, documentation, review and verification nodes.
    for obsolete in ("swe3_regmap", "swe3_ll_author"):
        from .acp import statements

        incoming = list(re.finditer(r"^  (\w+) -> " + obsolete + r"\n", graph, re.M))
        outgoing = list(re.finditer(r"^  " + obsolete + r" -> (\w+)\n", graph, re.M))
        if len(incoming) != 1 or len(outgoing) != 1:
            raise ValueError("DELIVERY_FIRST_GENERATOR_ROUTE_AMBIGUOUS:" + obsolete)
        source, target = incoming[0][1], outgoing[0][1]
        spans = [(start, end) for start, end, _, name, _ in statements(graph) if name == obsolete]
        for start, end in sorted(spans + [(m.start(), m.end()) for m in incoming + outgoing], reverse=True):
            graph = graph[:start] + graph[end:]
        graph = graph.replace("\n}", f"\n  {source} -> {target}\n}}", 1)
        nodes.pop(obsolete, None)
    cmd = f"{command_env} {python} -m forge_factory.delivery_first --workspace ."
    declarations = [f'  df_preflight [shape=parallelogram, script="{_q(cmd + " --step preflight")}"]',
                    "  start -> df_preflight",
                    '  df_preflight -> df_author_0 [condition="outcome=succeeded"]',
                    "  df_preflight -> finalize"]
    for i in range(3):
        name, check = f"df_author_{i}", f"df_verify_{i}"
        nodes[name] = {"role": "swe3-author", "phase": "SWE.3"}
        text = ("LOCAL QWEN DELIVERY-FIRST DEVELOPMENT. Use your swe3-author skill. Read " + cfg["contract"] +
                " and the declared primary inputs in .forge-run/manifest.json. Author actual C in " +
                ", ".join(cfg["candidate_files"]) + ". Required functions: " + ", ".join(cfg["required_functions"]) +
                ". No vendor implementation is supplied or substituted. Retain correct existing candidate content. "
                "Use write_file/edit_file/apply_patch directly, no Python helper execution is available. "
                "Independent immutable oracle checks compile and exercise your code after this visit. "
                "Do not edit inputs, tests, inspection evidence or factory code. "
                "Write the candidate now; do not write a plan instead of code. "
                "Requirements/design documentation follows later and is retrospective for this early implementation. ")
        if i:
            text += ("This is correction " + str(i) + " of at most two. Read .forge-run/delivery-first/latest.json and "
                     "the stdout/stderr in .forge-run/delivery-first/attempt-" + str(i - 1) +
                     ". Correct the actual errors only; do not change the independent oracle. ")
        text += ('Finish ONLY {"status":"PASS","artifacts":' + json.dumps(cfg["candidate_files"]) +
                 ',"issues":[],"next_action":"next"} if written; otherwise honest BLOCKED. '
                 "Your status does not decide test success.")
        declarations += [f'  {name} [label="Qwen C author {i}", max_visits=1, timeout="1500s", prompt="{_q(text)}"]',
                         f'  {check} [shape=parallelogram, script="{_q(cmd + " --step verify --attempt " + str(i))}"]',
                         f"  {name} -> {check}",
                         f'  {check} -> {continuation} [condition="outcome=succeeded"]',
                         f"  {check} -> " + (f"df_author_{i + 1}" if i < 2 else continuation)]
    # Subsequent engineering phases see the same generated candidate, not a second
    # untracked implementation. Their original evidence/checks remain authoritative.
    from .acp import statements

    edits = []
    for start, end, _, name, attrs in statements(graph):
        if name in nodes and 'prompt="' in attrs:
            note = ("DELIVERY-FIRST: read .forge-run/delivery-first/latest.json if present. Early Qwen implementation "
                    "and independent checks happened before this documentation; report that chronology honestly. "
                    "Keep the candidate if correct; do not replace it solely to satisfy a different API example. "
                    "Use the exact scoped function signatures in " + cfg["contract"] + ". ")
            edits.append((start, end, graph[start:end].replace('prompt="', 'prompt="' + _q(note), 1)))
    for start, end, text in reversed(edits):
        graph = graph[:start] + text + graph[end:]
    pos = graph.rfind("\n}")
    return graph[:pos] + "\n" + "\n".join(declarations) + graph[pos:], nodes


def report(ws):
    cfg, man = selected(ws)
    if not cfg:
        return None
    root = Path(ws) / ".forge-run/delivery-first"
    records = [json.loads(p.read_text()) for p in sorted(root.glob("attempt-*/result.json"))]
    paths = checked_paths(ws, cfg)
    current = {raw: sha256_file(p) if p.is_file() else None for raw, p in paths.items()}
    last = records[-1] if records else None
    matching = bool(last and last["candidate_hashes"] == current)
    slice_status = last["status"] if matching else "NOT_RUN"
    # The reviewed scope also includes startup and simulation/performance
    # obligations. Host behavior plus a target object cannot establish those.
    functional = "INCONCLUSIVE" if slice_status == "PASS" else slice_status
    integrity_issues = []
    try:
        validate_inputs(ws)
    except (ValueError, OSError) as exc:
        integrity_issues.append(str(exc))
        functional = "FAIL"
        slice_status = "INCONCLUSIVE"
    from .inspection.engine import PHASES, Store

    store = Store(Path(ws))
    phases = {ph: {"baseline": bool(store.latest_baseline(ph)), "gate": store.gate(ph)["decision"]}
              for ph in PHASES}
    return {"mode": MODE, "work_order": man["work_order"], "candidate_hashes": current,
            "artifact_delivery": "COMPLETE" if all(current.values()) else "PARTIAL" if any(current.values()) else "NONE",
            "functional_verification": functional,
            "slice_behavior_and_compile": slice_status,
            "integrity_issues": integrity_issues,
            "functional_scope": "HOST_BEHAVIOR_AND_TARGET_COMPILATION; SIMULATION_PERFORMANCE_NOT_QUALIFIED",
            "final_candidate_matches_last_verification": matching, "attempts": records,
            "process_qualification": "GAPS", "release_eligibility": "BLOCKED", "phases": phases,
            "authorship": "NATIVE_WRITE_EVENTS_REQUIRED", "milestone": "NOT_PROVEN",
            "unrun": ["physical_hardware", "complete simulation/performance requirement qualification"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--step", choices=("preflight", "verify"), required=True)
    ap.add_argument("--attempt", type=int, default=0)
    args = ap.parse_args(argv)
    try:
        out = preflight(args.workspace) if args.step == "preflight" else verify(args.workspace, args.attempt)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}))
        return 2
    print(json.dumps(out))
    return 0 if args.step == "preflight" or out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

