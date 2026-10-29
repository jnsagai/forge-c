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


def selected(ws):
    path = Path(ws) / ".forge-run/manifest.json"
    man = json.loads(path.read_text()) if path.is_file() else {}
    if (man.get("development_execution") or {}).get("name") != development.DEMO:
        return None
    return development.selected(ws)


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


def workflow(graph, nodes, gate_cmd):
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
    note = NOTE.replace("\\", "\\\\").replace('"', '\\"')
    for start, end, _indent, name, attrs in spans:
        if name == "graph":
            continue
        if name not in needed:
            edits.append((start, end, ""))
        elif name in nodes and 'prompt="' in attrs:
            text = graph[start:end].replace('prompt="', 'prompt="' + note + " ", 1)
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
    extra += [f"  {a} -> {b}" for a, b in zip(chain, chain[1:], strict=False)]
    end = graph.rfind("\n}")
    return graph[:end] + "\n" + "\n".join(extra) + graph[end:], {k: v for k, v in nodes.items() if k in needed}
