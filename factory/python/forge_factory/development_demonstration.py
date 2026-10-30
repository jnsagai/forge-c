"""Owner-selected QM demonstration through the existing workflow and evidence stores."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import development_execution as development
from .common import sha256_file

NOTE = ("QM PIPELINE DEMONSTRATION ONLY. Perform one engineering/inspection pass and retain actual artifacts, "
        "test results and unresolved findings. Quality findings do not stop the demonstration's next phase. "
        "Do not spend this visit repeatedly improving quality. Inspectors record honest judgments; never invent "
        "PASS, test evidence or missing inputs. Downstream artifacts using failed upstream work are provisional. "
        "The final package is demonstration-only and is not accepted delivery.")
REPAIR_NOTE = ("QM PIPELINE DEMONSTRATION ONLY. Address the current review and tool findings within this phase. "
               "The controller permits at most two phase correction cycles and reruns verification and inspection. "
               "After that it advances with unresolved findings retained. Reuse valid artifacts and correct the "
               "affected obligations. Do not invent PASS, missing inputs or test evidence. Downstream artifacts "
               "using failed upstream work remain provisional; the package is not accepted delivery.")


def selected(ws):
    path = Path(ws) / ".forge-run/manifest.json"
    man = json.loads(path.read_text()) if path.is_file() else {}
    if (man.get("development_execution") or {}).get("name") not in (development.DEMO, development.DEMO_REPAIR):
        return None
    return development.selected(ws)


def note(ws):
    policy = selected(ws)
    return REPAIR_NOTE if policy and policy["name"] == development.DEMO_REPAIR else NOTE


def validate_inputs(ws):
    ws = Path(ws)
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    for item in man.get("inputs") or []:
        path = ws / item["path"]
        if (path.is_symlink() or not path.resolve().is_relative_to(ws.resolve())
                or not path.is_file() or sha256_file(path) != item["sha256"]):
            raise ValueError("DEMONSTRATION_INPUT_CHANGED:" + item["path"])


def snapshot(store, phase):
    if not selected(store.workspace):
        raise ValueError("QM_DEMONSTRATION_REQUIRED")
    validate_inputs(store.workspace)
    try:
        base = store.freeze(phase, f"swe{phase[-1]}-author")
        result = {"status": "SNAPSHOT_UNQUALIFIED", "baseline_id": base["baseline_id"],
                  "baseline_hash": base["baseline_hash"], "quality_accepted": False}
    except ValueError as exc:
        result = {"status": "SNAPSHOT_UNAVAILABLE", "reason": str(exc)[:200], "quality_accepted": False}
    from .inspection.gate import _state

    _state(store.workspace, phase, {"step": "demonstration_snapshot", **result})
    return result


def workflow(graph, nodes, gate_cmd, *, repair=False):
    """Use the existing graph's successful path once, observing gate failures without branching on them."""
    from .acp import statements

    spans = list(statements(graph))
    edges = [m for m in re.finditer(r'^  (\w+) -> (\w+)(?: \[condition="([^"]+)"\])?\n', graph, re.M)
             if not any(start <= m.start() < end for start, end, *_ in spans)]
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(edge[1], []).append(edge)
    path, current = [], "start"
    while current != "exit":
        if current in path:
            raise ValueError("DEMONSTRATION_PATH_CYCLE")
        path.append(current)
        choices = outgoing.get(current, [])
        success = [m for m in choices if m[3] == "outcome=succeeded"]
        if len(success) == 1:
            current = success[0][2]
        elif len(choices) == 1 and choices[0][3] is None:
            current = choices[0][2]
        else:
            raise ValueError("DEMONSTRATION_PATH_UNRESOLVED:" + current)
    path.append("exit")
    needed = set(path)
    edits = [(m.start(), m.end(), "") for m in edges]
    instruction = (REPAIR_NOTE if repair else NOTE).replace("\\", "\\\\").replace('"', '\\"')
    for start, end, _indent, name, attrs in spans:
        if name == "graph":
            continue
        if name not in needed:
            edits.append((start, end, ""))
        elif name in nodes and 'prompt="' in attrs:
            text = graph[start:end].replace('prompt="', 'prompt="' + instruction + " ", 1)
            edits.append((start, end, text))
    for start, end, replacement in sorted(edits, reverse=True):
        graph = graph[:start] + replacement + graph[end:]
    extra, chain = [], []
    for node in path:
        chain.append(node)
        match = re.fullmatch(r"swe([1-6])_author_gate", node)
        if match:
            phase = "SWE." + match[1]
            snap = "swe" + match[1] + "_demo_snapshot"
            cmd = gate_cmd(phase, "demo-snapshot").replace("\\", "\\\\").replace('"', '\\"')
            extra.append(f'  {snap} [shape=parallelogram, label="{phase} DEMO snapshot (unqualified)", script="{cmd}"]')
            chain.append(snap)
    for a, b in zip(chain, chain[1:], strict=False):
        match = re.fullmatch(r"swe([1-6])_inspect_gate", a)
        if repair and match:
            phase = "SWE." + match[1]
            authors = [n for n in path if nodes.get(n, {}).get("phase") == phase
                       and nodes[n]["role"].endswith("-author")]
            if not authors:
                raise ValueError("DEMONSTRATION_REPAIR_AUTHOR_MISSING:" + phase)
            route = "swe" + match[1] + "_demo_repair"
            cmd = gate_cmd(phase, "demo-repair").replace("\\", "\\\\").replace('"', '\\"')
            extra += [f'  {route} [shape=parallelogram, label="{phase} bounded repair or advisory advance", '
                      f'max_visits=3, script="{cmd}"]', f"  {a} -> {route}",
                      f'  {route} -> {authors[0]} [condition="outcome=succeeded"]', f"  {route} -> {b}"]
        else:
            extra.append(f"  {a} -> {b}")
    end = graph.rfind("\n}")
    return graph[:end] + "\n" + "\n".join(extra) + graph[end:], {k: v for k, v in nodes.items() if k in needed}


def repair_route(store, phase):
    """Return success only to request a repair; the graph's other edge advances the demonstration."""
    policy = selected(store.workspace)
    if not policy or policy["name"] != development.DEMO_REPAIR:
        raise ValueError("QM_BOUNDED_REPAIR_DEMONSTRATION_REQUIRED")
    validate_inputs(store.workspace)
    from .inspection.gate import _epoch_lines, _state, advisory_record

    rows = [json.loads(line) for line in _epoch_lines(store.workspace, phase, store.budget_start())]
    latest = {}
    for row in rows:
        if row.get("step") in ("author", "verify", "inspect"):
            latest[(row["step"], row.get("check"))] = row
    latest.setdefault(("author", None), {"step": "author", "result": "NO_RECORDED_AUTHOR_GATE"})
    author = latest[("author", None)]
    if phase == "SWE.3":
        manifest = json.loads((store.workspace / ".forge-run/manifest.json").read_text())
        check = "delivery" if manifest.get("delivery") else "hal_guideline"
        verify = latest.get(("verify", check))
        if verify is None or verify.get("ts", "") < author.get("ts", ""):
            latest[("verify", check)] = {"step": "verify", "check": check, "verdict": "NOT_RECORDED_AFTER_AUTHOR"}
    failures = [row for row in latest.values() if (row["step"] == "author"
                and row.get("result") not in ("FROZEN", "FROZEN_BY_EVIDENCE", "FROZEN_BY_TOOL_EVIDENCE"))
                or (row["step"] == "verify" and row.get("verdict") != "PASS")]
    gate = store.gate(phase)
    if gate["decision"] == "PASS" and not failures:
        _state(store.workspace, phase, {"step": "demonstration_repair", "decision": "ADVANCE", "gate": gate})
        return 1
    from .afo.durable import digest

    evidence_key = digest({"gate": gate, "observations": list(latest.values())})
    prior = next((row for row in reversed(rows) if row.get("step") == "demonstration_repair"
                  and row.get("evidence_key") == evidence_key), None)
    if prior is not None:
        return 0 if prior["decision"] == "REWORK" else 1
    allowed = development.reserve_phase_rework(store.workspace, phase, evidence_key=evidence_key)
    result = {**gate, "decision": "REWORK" if allowed else "ADVISORY_CONTINUE",
              "reason": "bounded demonstration correction" if allowed else "two demonstration repairs exhausted",
              "quality_accepted": False, "author_or_verify_failures": failures,
              "development_ladder": development.ladder(store.workspace, phase), "evidence_key": evidence_key}
    if not allowed:
        ref = advisory_record(store, phase, store.budget_start(), result, 3, 2, None, None)
        result["advisory_ref"] = str(ref.relative_to(store.workspace))
    _state(store.workspace, phase, {"step": "demonstration_repair", **result})
    return 0 if allowed else 1


def provided_ll(source_wo, peripheral):
    """Import sealed provisional code only inside the separately selected QM demonstration lane."""
    from .common import sha256_bytes, state_dir
    from .inspection.engine import PHASES, Store
    from .layer import layer_of, ll_header, profile

    if not isinstance(source_wo, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", source_wo):
        raise ValueError("DEMONSTRATION_LL_SOURCE_INVALID")
    ws = state_dir() / "workorders" / source_wo / "workspace"
    if not selected(ws) or layer_of(ws) != "LL" or profile(ws)["id"] != peripheral:
        raise ValueError("DEMONSTRATION_LL_SOURCE_SCOPE_MISMATCH")
    validate_inputs(ws)
    store = Store(ws)
    # An attempt snapshot is a record of execution, never a passing quality gate.
    rows = (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()
    for phase in PHASES:
        if not any((row := json.loads(line)).get("phase") == phase
                   and row.get("step") == "demonstration_snapshot" for line in rows):
            raise ValueError("DEMONSTRATION_LL_PHASE_NOT_ATTEMPTED:" + phase)
    baseline = store.latest_baseline("SWE.3")
    if baseline is None or store.stale_reason("SWE.3", baseline) is not None:
        raise ValueError("DEMONSTRATION_LL_IMPLEMENTATION_UNSEALED")
    relative = ll_header(ws)
    header = ws / relative
    if header.is_symlink() or not header.resolve().is_relative_to(ws.resolve()) or not header.is_file():
        raise ValueError("DEMONSTRATION_LL_HEADER_UNAVAILABLE")
    data = header.read_bytes()
    # Require the exact header itself in the sealed implementation baseline.
    if baseline.get("files", {}).get(relative) != sha256_bytes(data):
        raise ValueError("DEMONSTRATION_LL_HEADER_NOT_BASELINED")
    gates = {phase: store.gate(phase)["decision"] for phase in PHASES}
    return data, {"path": relative, "role": "provided_ll_driver", "sha256": sha256_bytes(data),
                  "source_work_order": source_wo, "source_baseline_hash": baseline["baseline_hash"],
                  "source_phase_gates": gates, "qualification": "PROVISIONAL_QM_DEMONSTRATION_ONLY",
                  "quality_accepted": False,
                  "rule": "read-only provisional LL; neither this import nor gate agreement accepts the product"}
