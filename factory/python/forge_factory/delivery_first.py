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
    optional = [key for key in ("unit_harness", "simulation_oracle") if key in value]
    for key in ("contract", "host_oracle", "target_probe", *optional):
        raw = value.get(key)
        if not isinstance(raw, str) or not raw.startswith("inputs/") or raw not in {
                i["path"] for i in man.get("inputs", [])}:
            raise ValueError("DELIVERY_FIRST_INPUT_NOT_DECLARED:" + key)
    if value.get("simulation_oracle"):
        from .mcp.servers import sim
        from .simulation_performance import validate

        validate(man.get("simulation_performance"))
        sim.validate_adapter(man, value.get("simulation_adapter"))
    from .mcp.servers.build import PROFILES

    compilers = value.get("compiler_profiles")
    if (not isinstance(compilers, dict) or set(compilers) != {"host", "target"}
            or any(not isinstance(v, str) or v not in PROFILES or not v.startswith(k + "-")
                   for k, v in compilers.items())):
        raise ValueError("DELIVERY_FIRST_COMPILER_ADAPTER_UNSUPPORTED")
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
    from .policy.authz import ALWAYS_PROTECTED, ROLE_WRITE_PREFIXES, _match

    paths = {}
    for raw in cfg["candidate_files"]:
        p = ctx.path(raw, must_exist=False)
        rel = p.relative_to(ctx.workspace).as_posix()
        if (_match(rel, ALWAYS_PROTECTED) or not any(rel.startswith(prefix)
                for prefix in ROLE_WRITE_PREFIXES["swe3-author"] if prefix.startswith("software/"))):
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


def independent_target(ws, cfg, root):
    """Use a build/test snapshot, never overwrite the model's tests or implementation."""
    import shutil

    from . import simulation_performance as performance
    from .mcp.servers import build, sim

    shadow = root / "independent-target" / "workspace"
    shadow.mkdir(parents=True)
    _, man = selected(ws)
    for item in man["inputs"]:
        source = context(ws).path(item["path"], kind="file")
        target = shadow / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for raw, source in checked_paths(ws, cfg).items():
        target = shadow / raw
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (shadow / ".forge-run").mkdir()
    (shadow / ".forge-run/manifest.json").write_text(pretty_json(man))
    oracle = context(ws).path(cfg["simulation_oracle"], kind="file")
    target = shadow / performance.TEST
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(oracle, target)
    bc = ToolContext("forge-build-mcp", "compile", "deterministic-verifier", "SWE.3", shadow, man["work_order"])
    profile = cfg["compiler_profiles"]["target"]
    compiled = build.compile_(bc, build.CompileIn(profile=profile))
    outputs = {"compile": compiled}
    if compiled["status"] == "PASS":
        outputs["size"] = build.measure_elf(bc, build.ProfileIn(profile=profile))
        outputs["stack"] = build.stack_usage(bc, build.ProfileIn(profile=profile))
        sc = ToolContext("forge-sim-mcp", "run_renode", "deterministic-verifier", "SWE.5", shadow, man["work_order"])
        outputs["simulation"] = sim.run_renode(sc, sim.SimIn())
        try:
            outputs["cost"] = performance.verify_result(shadow, outputs["simulation"])
        except (ValueError, OSError, KeyError, TypeError) as exc:
            outputs["cost"] = {"status": "NOT_VERIFIED", "reason": str(exc)}
    size = outputs.get("size", {}).get("metrics", {})
    stack = outputs.get("stack", {}).get("metrics", {})
    budgets = man["budgets"]
    resource_ok = (outputs.get("size", {}).get("status") == outputs.get("stack", {}).get("status") == "PASS"
                   and size.get("flash_bytes", float("inf")) <= budgets["flash_bytes"]
                   and size.get("ram_bytes", float("inf")) <= budgets["static_ram_bytes"]
                   and stack.get("max_frame_bytes", float("inf")) <= budgets["stack_bytes"])
    passed = (compiled["status"] == "PASS" and resource_ok
              and outputs.get("simulation", {}).get("status") == outputs.get("cost", {}).get("status") == "PASS")
    return {"status": "PASS" if passed else "FAIL", "outputs": outputs, "resources_within_declared_limits": resource_ok,
            "resource_scope": "OBJECT_LEVEL_AND_MAXIMUM_FRAME; NOT_LINKED_FIRMWARE_OR_CALL_GRAPH",
            "workspace": str(shadow.relative_to(ws)), "independent_oracle_sha256": sha256_file(oracle),
            "physical_hardware": "NOT_RUN", "source_rewritten": False}



def verify(ws, attempt):
    """Real tool calls; archive every candidate before compiling, with no hidden retries."""
    from .mcp.servers.build import PROFILES, WARN

    ws = Path(ws).resolve()
    cfg, man = selected(ws)
    if not cfg or attempt not in (0, 1, 2, "final"):
        raise ValueError("DELIVERY_FIRST_ATTEMPT_INVALID")
    validate_inputs(ws)
    if not (ws / ".forge-run/delivery-first/initial.json").is_file():
        raise ValueError("DELIVERY_FIRST_PREFLIGHT_REQUIRED")
    paths = checked_paths(ws, cfg)
    root = ws / ".forge-run/delivery-first" / ("attempt-" + str(attempt))
    if isinstance(attempt, int) and attempt and not (root.parent / ("attempt-" + str(attempt - 1)) / "result.json").is_file():
        raise ValueError("DELIVERY_FIRST_PREVIOUS_ATTEMPT_REQUIRED")
    if attempt == "final" and not (root.parent / "attempt-0/result.json").is_file():
        raise ValueError("DELIVERY_FIRST_INITIAL_ATTEMPT_REQUIRED")
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
        for label, profname, fixture in (("host_compile", cfg["compiler_profiles"]["host"], "host_oracle"),
                                         ("target_compile", cfg["compiler_profiles"]["target"], "target_probe")):
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
    target = independent_target(ws, cfg, root) if passed and cfg.get("simulation_oracle") else None
    if target is not None:
        passed = passed and target["status"] == "PASS"
    unchanged = current == {raw: sha256_file(p) if p.is_file() else None for raw, p in paths.items()}
    validate_inputs(ws)
    corrections = attempt if isinstance(attempt, int) else max(
        [int(p.parent.name.removeprefix("attempt-")) for p in root.parent.glob("attempt-[0-2]/result.json")], default=0)
    result = {"at": utc_now(), "mode": MODE, "attempt": attempt, "correction_count": corrections,
              "verification_round": "FINAL_RECHECK_NO_NEW_AUTHOR" if attempt == "final" else "BOUNDED_AUTHOR_ATTEMPT",
              "work_order": man["work_order"], "factory_revision": man.get("factory_revision"),
              "candidate_hashes": current, "candidate_unchanged_during_checks": unchanged,
              "status": "PASS" if passed and unchanged else "FAIL", "missing": missing, "calls": calls,
              "verification_scope": ("DECLARED_HOST_TARGET_SIMULATION_COST_AND_OBJECT_FRAME_RESOURCES" if target
                                     else "DECLARED_HOST_BEHAVIOR_AND_TARGET_COMPILATION_ONLY"),
              "simulation": target["status"] if target else "NOT_RUN", "independent_target": target,
              "physical_hardware": "NOT_RUN",
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
    for obsolete in ("swe3_regmap", "swe3_ll_author", "swe3_fix_author"):
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
        text = ("LOCAL QWEN DELIVERY-FIRST DEVELOPMENT. Use use_skill with skill_name swe3-author. Read " + cfg["contract"] +
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
    from .workflow import prompts as P

    access = ("Register access follows " + cfg["contract"] + ". Use only the actual API, device declarations and "
              "source-backed target addresses in the frozen inputs. Do not invent register arrays, offset defines "
              "or masks that the candidate/device inputs do not supply.")
    legacy_access = _q(P.peripheralize(P.cmsisize(P.REGISTER_BLOCK_NOTE)))
    robot_steps = P.LL_ROBOT_STEPS if manifest.get("layer") == "LL" else P.ROBOT_STEPS
    robot_read = P.peripheralize(P.cmsisize(robot_steps[0]))
    robot_read = robot_read.replace(
        "Read nothing else: no other sources, tests, reports or tools are needed in this step.",
        "Also read " + cfg["contract"] + " and the candidate's declared device inputs; the existing target tests "
        "may be consulted for the declared interface and simulation fidelity.")
    scenario = ("Write C scenarios software/tests/software/scn_<topic>.c, grouping the declared requirements by "
                "topic. Include the actual candidate header(s) and forge_target_test.h, declare FORGE_MAILBOX_DEFINE, "
                "and use int main(void) with FORGE_TEST_BEGIN(), TCHECK(number, actual_condition), FORGE_TEST_END(), "
                "then return 0. " + access + " Pass valid instance arguments exactly as the scoped prototypes require. "
                "Keep real behavioral assertions and the frozen implementation unchanged. No printf or stdlib.")

    edits = []
    for start, end, _, name, attrs in statements(graph):
        if name in nodes and 'prompt="' in attrs:
            note = ("DELIVERY-FIRST: read .forge-run/delivery-first/latest.json if present. Early Qwen implementation "
                    "and independent checks happened before this documentation; report that chronology honestly. "
                    "The bounded implementation authoring sequence is finished. Candidate code is now frozen; "
                    "produce your phase documents/tests and record remaining defects without changing the driver. "
                    "Use the exact scoped function signatures in " + cfg["contract"] + ". ")
            if name == "release_manager":
                note += ("Inventory and report existing gaps only. Do not call build_package: the deterministic graph "
                         "runs final independent verification after your visit, then seals the archive. ")
            text = graph[start:end].replace(legacy_access, _q(access))
            if name == "swe6_test_author":
                for old, new in ((P.peripheralize(P.cmsisize(robot_steps[0])), robot_read),
                                 (P.peripheralize(P.cmsisize(robot_steps[1])), scenario)):
                    if _q(old) not in text:
                        raise ValueError("DELIVERY_FIRST_SCENARIO_PROMPT_BOUNDARY_CHANGED")
                    text = text.replace(_q(old), _q(new))
            edits.append((start, end, text.replace('prompt="', 'prompt="' + _q(note), 1)))
    for start, end, text in reversed(edits):
        graph = graph[:start] + text + graph[end:]
    # Recheck final bytes after downstream authors may have changed the code.
    # This runs no new model correction and leaves every earlier receipt intact.
    graph = re.sub(r"^  (\w+) -> finalize\n", r"  \1 -> df_final_verify\n", graph, flags=re.M)
    declarations = [line.removesuffix(" -> finalize") + " -> df_final_verify"
                    if line.endswith(" -> finalize") else line for line in declarations]
    declarations += [f'  df_final_verify [shape=parallelogram, '
                     f'script="{_q(cmd + " --step final-verify")}"]', "  df_final_verify -> finalize"]
    pos = graph.rfind("\n}")
    return graph[:pos] + "\n" + "\n".join(declarations) + graph[pos:], nodes


def native_source_provenance(events, roles, ws, candidate_hashes):
    """Replay accepted whole writes and unambiguous literal edits; never infer a functional PASS.

    Complete chain material is source workproduct evidence, not model reasoning.
    Opaque patches, unfinished calls and unmatched final bytes remain unverified.
    """
    from .common import sha256_bytes

    ws = Path(ws).resolve()
    pending, states, ambiguous = {}, {}, set()

    def key(event, call):
        p = event.get("properties") or {}
        return event.get("node_id"), p.get("stream_id"), p.get("visit"), call

    def arguments(start):
        args = start.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                return None
        return args if isinstance(args, dict) else None

    def relative(args):
        raw = (args or {}).get("file_path") or (args or {}).get("path")
        if not isinstance(raw, str):
            return None
        try:
            path = (Path(raw) if Path(raw).is_absolute() else ws / raw).resolve()
        except (OSError, ValueError, RuntimeError):
            return None
        return path.relative_to(ws).as_posix() if path.is_relative_to(ws) else None

    for index, event in enumerate(events):
        payload = (event.get("properties") or {}).get("event")
        if not isinstance(payload, dict):
            continue
        start = payload.get("ToolCallStarted")
        if isinstance(start, dict) and start.get("tool_name") in ("write_file", "edit_file", "apply_patch"):
            call = start.get("tool_call_id")
            if not isinstance(call, str) or not call:
                states.clear()
                continue
            identity = key(event, call)
            if identity in pending:
                ambiguous.add(identity)
                states.clear()
            pending[identity] = (start, index)
        done = payload.get("ToolCallCompleted")
        if not isinstance(done, dict):
            continue
        identity = key(event, done.get("tool_call_id"))
        pair = pending.pop(identity, None)
        if pair is None or identity in ambiguous or done.get("is_error") is not False:
            continue
        start, start_index = pair
        args = arguments(start)
        if args is None or start["tool_name"] == "apply_patch":
            states.clear()  # no guessing at opaque mutation semantics
            continue
        rel = relative(args)
        if rel not in candidate_hashes:
            continue
        node = event.get("node_id")
        if roles.get(node, {}).get("role") != "swe3-author":
            states.pop(rel, None)
            continue
        call = {"tool_call_id": start["tool_call_id"], "node": node}
        if start["tool_name"] == "write_file" and isinstance(args.get("content"), str):
            states[rel] = {"content": args["content"], "anchor_content": args["content"], "edits": [],
                           "anchor": {**call, "path": rel, "sha256": sha256_bytes(args["content"].encode())},
                           "anchor_event_index": start_index}
        elif start["tool_name"] == "edit_file":
            state = states.get(rel)
            old, new = args.get("old_string"), args.get("new_string")
            if (not state or not isinstance(old, str) or not old or not isinstance(new, str)
                    or state["content"].count(old) != 1):
                states.pop(rel, None)
                continue
            before = sha256_bytes(state["content"].encode())
            state["content"] = state["content"].replace(old, new, 1)
            state["edits"].append({**call, "event_index": start_index, "old_string": old, "new_string": new,
                                   "before_sha256": before, "after_sha256": sha256_bytes(state["content"].encode())})
        else:
            states.pop(rel, None)
    for start, _ in pending.values():
        args = arguments(start)
        if args is None or start["tool_name"] == "apply_patch":
            states.clear()
        else:
            states.pop(relative(args), None)
    writes, chains, covered = [], [], set()
    for rel, state in states.items():
        if sha256_bytes(state["content"].encode()) != candidate_hashes[rel]:
            continue
        covered.add(rel)
        if state["edits"]:
            chains.append({k: v for k, v in {**state, "path": rel, "final_sha256": candidate_hashes[rel]}.items()
                           if k != "content"})
        else:
            writes.append(state["anchor"])
    confirmed = bool(candidate_hashes) and covered == set(candidate_hashes)
    status = ("CONFIRMED_NATIVE_WRITE_EDIT_CHAIN" if chains else "CONFIRMED_NATIVE_WRITE_FILE")
    return {"authorship": status if confirmed else "UNVERIFIED_EDIT_CHAIN",
            "write_evidence": writes, "edit_chain_evidence": chains,
            "authorship_basis": "SUCCESSFUL_NATIVE_SOURCE_TOOL_PAYLOAD_REPLAY_AND_EXACT_FINAL_BYTES; NOT_FUNCTIONAL_VERIFICATION"}


def native_record(ws, candidate_hashes):
    """Read actual native events/usage; never substitute fixture authorship or guessed tokens."""
    from .fabro.client import client_for_workspace

    ws = Path(ws)
    rid_file = ws / ".forge-run/fabro_run_id"
    server_file = ws / ".forge-run/fabro_server.json"
    if not rid_file.is_file() or not server_file.is_file():
        return {"status": "NOT_AVAILABLE", "authorship": "UNVERIFIED", "model_requests": "UNKNOWN"}
    rid = rid_file.read_text().strip()
    try:
        with client_for_workspace(ws, timeout=15) as client:
            events = list(client.iter_events(rid))
            usage = client.usage(rid)
            from .fabro.client import run_status

            native_status = run_status(client.get_run(rid))
        binding = ws / ".forge-run/binding.json"
        roles = json.loads(binding.read_text()).get("nodes", {}) if binding.is_file() else {}
        node_failures, phases = [], {}
        for i in range(1, 7):
            phases["SWE." + str(i)] = {
                kind + "_attempted": any(e["event"] == "stage.started" and e.get("node_id") == f"swe{i}_{kind}"
                                        for e in events) for kind in ("author", "inspector")}
        for event in events:
            if event["event"] == "stage.failed":
                node_failures.append({"node": event.get("node_id"), "failure":
                                      (event.get("properties") or {}).get("failure"), "at": event.get("ts")})
        provenance = native_source_provenance(events, roles, ws, candidate_hashes)
        output = usage.get("totals", {}).get("usage", {}).get("tokens", {})
        stages = usage.get("stages", [])
        author_tokens = [s.get("usage", {}).get("tokens", {}).get("output") for s in stages
                         if roles.get(s.get("stage", {}).get("id"), {}).get("role", "").endswith("-author")]
        return {"status": "OBSERVED", "native_id": rid, "native_status": native_status, **provenance,
                "phase_attempts": phases, "node_failures": node_failures,
                "external_guidance_events": sum("steer" in e["event"] for e in events),
                "model_requests": "UNKNOWN", "reported_tokens": output or "UNKNOWN",
                "reported_author_output_tokens": sum(author_tokens) if author_tokens and all(
                    type(n) is int and n >= 0 for n in author_tokens) else "UNKNOWN",
                "reasoning_token_breakdown": "UNKNOWN", "usage_by_stage": stages,
                "basis": "ACTUAL_NATIVE_API_NOT_MODEL_SELF_REPORT"}
    except Exception as exc:  # metadata unavailability must not destroy the candidate package
        return {"status": "NOT_AVAILABLE", "authorship": "UNVERIFIED", "reason": type(exc).__name__,
                "model_requests": "UNKNOWN"}



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
    target = (last or {}).get("independent_target") if matching else None
    # Legacy receipts without an independent simulation stay inconclusive.
    qualified = bool(target and target["status"] == "PASS" and slice_status == "PASS")
    functional = "PASS" if qualified else "INCONCLUSIVE" if slice_status == "PASS" else slice_status
    integrity_issues = []
    if qualified:
        from .simulation_performance import verify_result

        try:
            shadow = (Path(ws) / target["workspace"]).resolve()
            if not shadow.is_relative_to(root.resolve()):
                raise ValueError("DELIVERY_FIRST_INDEPENDENT_TARGET_PATH_CHANGED")
            if any(sha256_file(shadow / raw) != digest for raw, digest in current.items()):
                raise ValueError("DELIVERY_FIRST_INDEPENDENT_CANDIDATE_CHANGED")
            if verify_result(shadow, target["outputs"]["simulation"])["status"] != "PASS":
                raise ValueError("DELIVERY_FIRST_INDEPENDENT_COST_NOT_PASS")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            integrity_issues.append(str(exc))
            functional = "FAIL"
            qualified = False
    try:
        validate_inputs(ws)
    except (ValueError, OSError) as exc:
        integrity_issues.append(str(exc))
        functional = "FAIL"
        slice_status = "INCONCLUSIVE"
    from .inspection.engine import PHASES, Store

    store = Store(Path(ws))
    phases = {ph: {"baseline": bool(store.latest_baseline(ph)), "gate": store.gate(ph)["decision"],
                   "files": store.files_of(ph)}
              for ph in PHASES}
    native = native_record(ws, current)
    attempted = native.get("phase_attempts", {})
    execution = ("CANCELLED" if native.get("native_status") == "CANCELLED" else
                 "COMPLETED" if attempted and all(all(v.values()) for v in attempted.values())
                 else "PARTIAL" if attempted else "FAILED")
    model_file = Path(ws) / ".forge-run/model-profile.json"
    model = json.loads(model_file.read_text()) if model_file.is_file() else "UNKNOWN"
    from datetime import datetime

    initial = root / "initial.json"
    first = next((r for r in records if (r.get("independent_target") or {}).get("status") == "PASS"), None)
    seconds = "UNKNOWN"
    if initial.is_file() and first:
        seconds = round((datetime.fromisoformat(first["at"]) - datetime.fromisoformat(
            json.loads(initial.read_text())["at"])).total_seconds(), 3)
    return {"mode": MODE, "work_order": man["work_order"], "candidate_hashes": current,
            "factory_revision": man.get("factory_revision"), "local_profile": man.get("local_profile"),
            "model_profile": model, "declared_scope": man.get("operation_scope"),
            "execution": execution, "native_evidence": native,
            "artifact_delivery": "COMPLETE" if all(current.values()) else "PARTIAL" if any(current.values()) else "NONE",
            "functional_verification": functional,
            "slice_behavior_and_compile": slice_status,
            "integrity_issues": integrity_issues,
            "functional_scope": ("DECLARED_HOST_AND_SIMULATED_BEHAVIOR_AND_COST; OBJECT_AND_FRAME_RESOURCE_LIMITS"
                                 if qualified else "HOST_BEHAVIOR_AND_TARGET_COMPILATION; SIMULATION_NOT_QUALIFIED"),
            "artifact_delivery_scope": "DECLARED_CANDIDATE_FILES_ONLY; PHASE_BASELINES_REPORTED_SEPARATELY",
            "final_candidate_matches_last_verification": matching, "attempts": records,
            "process_qualification": "GAPS", "release_eligibility": "BLOCKED", "phases": phases,
            "authorship": native["authorship"], "milestone": "NOT_PROVEN",
            "metrics": {"attempted_products": 1, "functionally_verified_candidates": int(qualified),
                        "functionally_verified_products": "UNKNOWN_REQUIRES_REAL_MODEL_AND_TERMINAL_AUDIT",
                        "end_to_end_yield": "UNKNOWN", "cohort_scope": "THIS_WORK_ORDER_ONLY_NOT_REPEATABILITY",
                        "corrections": (last or {}).get("correction_count", 0),
                        "model_requests": native.get("model_requests", "UNKNOWN"),
                        "reported_tokens": native.get("reported_tokens", "UNKNOWN"),
                        "reported_author_output_tokens": native.get("reported_author_output_tokens", "UNKNOWN"),
                        "wall_clock_to_first_functional_result_s": seconds,
                        "wall_clock_basis": "PREFLIGHT_TO_COMPLETE_INDEPENDENT_CHECKS",
                        "human_interventions": "UNKNOWN_REQUIRES_EXTERNAL_OBSERVER",
                        "compiler_passes": sum(c["status"] == "PASS" for r in records for c in r["calls"]
                                               if c["check"].endswith("compile")),
                        "compiler_failures": sum(c["status"] == "FAIL" for r in records for c in r["calls"]
                                                 if c["check"].endswith("compile")),
                        "required_functions": cfg["required_functions"]},
            "unrun": ["physical_hardware", "whole-program call-graph stack analysis"]
                     + ([] if qualified else ["complete simulation/performance requirement qualification"])}


def scorecard(record):
    """One page from the same evidence as JSON; no independent success authority."""
    metrics = record["metrics"]
    lines = ["# Forge-C Delivery-First Experiment — " + record["work_order"], "",
             "Mode: " + record["mode"],
             "Source: " + json.dumps(record["factory_revision"], sort_keys=True),
             "Model/profile: " + json.dumps({"model": record["model_profile"], "profile": record["local_profile"]},
                                            sort_keys=True),
             "Declared functions: " + ", ".join(metrics["required_functions"]), ""]
    for key in ("execution", "artifact_delivery", "functional_verification", "process_qualification",
                "release_eligibility", "authorship", "milestone"):
        lines.append(key + ": " + record[key])
    lines += ["", "Functional scope: " + record["functional_scope"],
              "Metrics: " + json.dumps(metrics, sort_keys=True), "", "Phase evidence (hashes in report.json):"]
    for phase, item in record["phases"].items():
        lines.append(f"- {phase}: {len(item['files'])} files; baseline={item['baseline']}; gate={item['gate']}")
    lines += ["", "Unrun: " + "; ".join(record["unrun"]),
              "Gaps and failures: existing package gap register; report.json native_evidence.node_failures.",
              "No claims of production release, ASPICE compliance, safety, generic targets, 24/7 or model learning."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--step", choices=("preflight", "verify", "final-verify"), required=True)
    ap.add_argument("--attempt", type=int, default=0)
    args = ap.parse_args(argv)
    try:
        out = preflight(args.workspace) if args.step == "preflight" else verify(
            args.workspace, "final" if args.step == "final-verify" else args.attempt)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}))
        return 2
    print(json.dumps(out))
    return 0 if args.step == "preflight" or out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

