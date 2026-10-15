"""T048 — one-command unattended work order: inputs -> preflight -> Fabro SWE.1–6 run -> finalizer.

    python -m forge_factory.workorder --example examples/0002-arm_55_rcc_st --wo WO-0002 [--detach]

No human prompt anywhere. Preflight BLOCKED => immediate BLOCKED package (no agent is started).
Every terminal path ends in the deterministic finalizer (workflow node, or external fallback here).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from .common import REPO_ROOT, pretty_json, sha256_file, state_dir, utc_now
from .events.emit import emit
from .fabro.runconfig import create_workspace, fabro_env, write_run
from .mcp.preflight import fabro_mcp_config
from .mcp.preflight import preflight as mcp_preflight
from .registry.agents import preflight as agent_preflight
from .release.finalize import finalize
from .workflow.builder import binding_for, build


def register_index(md: Path) -> list[dict]:
    """Deterministic heading -> line index so agents can read_file(offset) the exact RM section."""
    out = []
    for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^(#{2,6}) (\d+(?:\.\d+)*) (.+)$", line)
        if m:
            out.append({"section": m.group(2), "title": m.group(3).strip(), "line": n})
    return out


def split_sections(md_text: str, doc_stem: str) -> tuple[dict[str, str], list[str]]:
    """Split a converted document into one file per numbered section (verbatim content, page anchors kept).

    Small local models cannot reliably page through multi-MB files; per-section files remove offsets entirely.
    """
    files: dict[str, str] = {}
    index: list[str] = []
    cur_name: str | None = None
    cur: list[str] = []
    page = "?"

    def flush() -> None:
        if not (cur_name and cur):
            return
        text = "\n".join(cur) + "\n"
        if len(text) <= 40_000:
            files[cur_name] = text
            return
        # Oversized section: split at page anchors into <=40 kB parts (content unchanged, order kept).
        parts: list[list[str]] = []
        buf: list[str] = []
        for ln in cur:
            size: int = sum(len(x) + 1 for x in buf)
            if (ln.startswith("<a id=\"p-") and size > 30_000) or size > 38_000:
                parts.append(buf)
                buf = []
            buf.append(ln)
        parts.append(buf)
        base = cur_name[:-3]
        title_line = index.pop()
        for k, part in enumerate(parts, 1):
            files[f"{base}_part{k}.md"] = "\n".join(part) + "\n"
            index.append(title_line.rsplit(" | ", 1)[0] + f" (part {k}/{len(parts)}) | {base}_part{k}.md")

    for line in md_text.splitlines():
        pm = re.match(r"^<!-- source: (\S+) p\.(\d+) -->", line)
        if pm:
            page = pm.group(2)
        m = re.match(r"^(#{2,6}) (\d+(?:\.\d+)*) (.+)$", line)
        if m:
            flush()
            slug = re.sub(r"[^A-Za-z0-9]+", "_", m.group(3)).strip("_")[:60]
            cur_name = f"inputs/sections/{doc_stem}/{m.group(2)}_{slug}.md"
            cur = [f"<!-- source: {doc_stem} section {m.group(2)} starting p.{page} -->", line]
            index.append(f"{m.group(2)} | {m.group(3).strip()} | p.{page} | {cur_name}")
        elif cur_name:
            cur.append(line)
    flush()
    return files, index


def prepare(example: Path, wo: str) -> tuple[Path, dict]:
    spec = json.loads((example / "workorder.json").read_text())
    ws = state_dir() / "workorders" / wo / "workspace"
    inputs: dict[str, bytes] = {}
    listed = []
    for item in spec["inputs"]:
        src = (example / item["path"]).resolve()
        if not src.is_file() or (REPO_ROOT not in src.parents):
            raise FileNotFoundError(item["path"])
        dst = f"inputs/{src.name}"
        inputs[dst] = src.read_bytes()
        listed.append({"path": dst, "role": item["role"], "sha256": sha256_file(src), "bytes": src.stat().st_size})
    index_lines = ["# Input section index (one line per section: number | title | page | file to read_file)", ""]
    for item in list(listed):
        if item["path"].startswith("inputs/RM") and item["path"].endswith(".md"):
            stem = Path(item["path"]).stem.split("-")[0]
            files, idx_lines = split_sections(inputs[item["path"]].decode("utf-8"), stem)
            inputs.update({k: v.encode() for k, v in files.items()})
            index_lines += idx_lines
    inputs["inputs/index.md"] = ("\n".join(index_lines) + "\n").encode()
    from .upstream import UPSTREAM_FILE, load_upstream

    upstream = load_upstream(example)  # human-approved HSI/safety allocation/budgets, else NOT_PROVIDED
    target, budgets = dict(spec["target"]), dict(spec["budgets"])
    if upstream["status"] == "APPROVED":
        d = upstream["data"]
        inputs["inputs/upstream-inputs.yaml"] = (example / UPSTREAM_FILE).read_bytes()
        listed.append({"path": "inputs/upstream-inputs.yaml", "role": "approved_upstream_inputs",
                       "sha256": upstream["sha256"], "bytes": len(inputs["inputs/upstream-inputs.yaml"])})
        who = f"approved by {d['approval']['approved_by']} on {d['approval']['approved_on']}"
        target.update({"hsi_contract": f"PROVIDED {d['hsi_contract']['contract_id']} ({who})",
                       "safety_allocation": f"PROVIDED ASIL {d['safety_allocation']['asil']} ({who})",
                       "part_number": d["target"]["part_number"], "silicon_revision": d["target"]["silicon_revision"]})
        budgets = {k: d["budgets"][k] for k in ("flash_bytes", "static_ram_bytes", "stack_bytes")} | {"status": who}
    head = create_workspace(ws, inputs)
    idx = {}
    for item in listed:
        if item["path"].endswith(".md"):
            idx[item["path"]] = register_index(ws / item["path"])
    manifest = {"schema": "forge-c/work-order/0.4", "work_order": wo, "created_at": utc_now(),
                "input_baseline_commit": head, "driver": spec["driver"], "target": target,
                "upstream": {k: upstream[k] for k in ("status", "issues", "sha256")},
                "scope": spec["scope"], "budgets": budgets, "inputs": listed,
                "guideline": spec.get("guideline"), "system_names": spec["system_names"],
                "outputs": {"SWE.1": "workproducts/SWE.1/software_requirements.md (EARS) + traceability/"
                                     "requirements_to_tests.csv + safety/software_safety_requirements.md",
                            "SWE.2": "workproducts/SWE.2/software_architecture.md",
                            "SWE.3": "workproducts/SWE.3/detailed_design.md + software/hal/*.c|h + software/ll/*.h",
                            "SWE.4": "workproducts/SWE.4/unit_verification_report.md + software/tests/unit/test_*.c",
                            "SWE.5": "workproducts/SWE.5/integration_verification_report.md + software/tests/integration/test_*.c + software/tests/target/test_*.c (Renode)",
                            "SWE.6": "workproducts/SWE.6/software_verification_report.md"},
                "section_index_files": {k: f".forge-run/index/{Path(k).stem}.json" for k in idx},
                "rules": ["Cite source as DOC p.N for every hardware fact", "Never invent registers or bits",
                          "Final reply: compact JSON only"]}
    (ws / ".forge-run/index").mkdir(parents=True, exist_ok=True)
    for k, v in idx.items():
        (ws / f".forge-run/index/{Path(k).stem}.json").write_text(json.dumps(v))
    (ws / ".forge-run/manifest.json").write_text(pretty_json(manifest))
    from .inspection.engine import PHASES, load_checklist

    (ws / ".forge-run/checklists").mkdir(parents=True, exist_ok=True)
    for ph in PHASES:  # read-only copy of the resolved (hash-pinned) checklist for inspectors
        cl = load_checklist(ph)
        (ws / f".forge-run/checklists/{ph}.json").write_text(pretty_json(
            {"phase": ph, "version": cl["version"], "sha256": cl["sha256"],
             "checks": [{k: c.get(k) for k in ("id", "required", "severity_if_failed", "criterion", "deterministic_check")}
                        for c in cl["checks"]]}))
    (ws / "configuration").mkdir(exist_ok=True)
    (ws / "configuration/system_names.json").write_text(json.dumps(spec["system_names"]))
    (ws / "configuration/target_baseline.json").write_text(pretty_json(spec["target"]))
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.email=factory@forge-c.local", "-c", "user.name=forge-factory", "commit", "-qm",
                    "forge: work order configuration"], cwd=ws, check=True)
    return ws, manifest


def run(example: Path, wo: str, detach: bool = False, timeout_s: int = 6 * 3600, code_model: str | None = None,
        model: str = "qwen3:8b", provider: str = "ollama") -> dict:
    ws, manifest = prepare(example, wo)
    secmap = {}
    for line in (ws / "inputs/index.md").read_text().splitlines():
        parts = [x.strip() for x in line.split(" | ")]
        if len(parts) == 4 and parts[0][:1].isdigit() and parts[0] not in secmap:
            secmap[parts[0]] = parts[3]
    graph, nodes = build(wo, goal=f"{manifest['driver']} for {manifest['target'].get('part_number')} (offline review)",
                         sections=secmap, code_model=code_model, chunk_lines=40 if provider == "ollama" else 150)
    (ws / ".forge-run/model-profile.json").write_text(pretty_json(
        {"default": model, "provider": provider, "code_nodes": code_model,
         "nodes": sorted(k for k, v in nodes.items() if v.get("model")),
         "local_only": provider == "ollama",
         "note": "local Ollama via gateway" if provider == "ollama" else
         "CLOUD BENCHMARK (user-authorized); not local-model evidence for T048"}))
    roles = sorted({n["role"] for n in nodes.values()})
    ap = agent_preflight(roles)
    mp = mcp_preflight(roles, live=True)
    pre = {"agents": {k: ap[k] for k in ("status", "issues")}, "mcp": {k: mp[k] for k in ("status", "issues",
                                                                                          "disabled_optional_ops")}}
    (ws / ".forge-run/preflight.json").write_text(pretty_json(pre))
    emit("human", "INFO", f"{wo} preflight agents={ap['status']} mcp={mp['status']}", correlation_id=wo)
    if ap["status"] != "PASS" or mp["status"] != "PASS":
        emit("human", "WARN", f"{wo} preflight BLOCKED; no agent started; packaging BLOCKED", correlation_id=wo)
        return {"work_order": wo, "preflight": pre, "package": finalize(ws, wo)}
    toml = write_run(ws, graph, f"{wo} {manifest['driver']}", binding_for(wo, str(ws), nodes),
                     fabro_mcp_config(mp["servers"]), model=model, provider=provider)
    fab = shutil.which("fabro") or str(Path.home() / ".fabro/bin/fabro")
    import os

    fab = os.environ.get("FORGE_FABRO_BIN", fab)
    out = subprocess.run([fab, "run", str(toml), "--detach", "--auto-approve", "--environment", "local", "--label",
                          f"forge={wo}"], cwd=ws, env=fabro_env(), capture_output=True, text=True, timeout=180)
    fabro_run_id = (out.stdout.strip().splitlines() or [""])[-1]
    (ws / ".forge-run/fabro_run_id").write_text(fabro_run_id)
    emit("human", "INFO", f"{wo} started Fabro run {fabro_run_id}", correlation_id=wo, run_id=fabro_run_id)
    if detach:
        return {"work_order": wo, "fabro_run_id": fabro_run_id, "workspace": str(ws), "preflight": pre}
    subprocess.run([fab, "wait", fabro_run_id], env=fabro_env(), capture_output=True, timeout=timeout_s)
    pkg = ws / ".forge-run/package.json"
    package = json.loads(pkg.read_text()) if pkg.is_file() else finalize(ws, wo, fabro_run_id)  # external finalizer
    return {"work_order": wo, "fabro_run_id": fabro_run_id, "workspace": str(ws), "preflight": pre, "package": package}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--example", type=Path, required=True)
    ap.add_argument("--wo", required=True)
    ap.add_argument("--detach", action="store_true")
    ap.add_argument("--code-model", default=None, help="local model for the C code/test author nodes (trial profile)")
    ap.add_argument("--model", default="qwen3:8b", help="run-level model (default local qwen3:8b)")
    ap.add_argument("--provider", default="ollama", help="Fabro provider; non-ollama = user-authorized cloud benchmark")
    a = ap.parse_args(argv)
    res = run(a.example.resolve(), a.wo, a.detach, code_model=a.code_model, model=a.model, provider=a.provider)
    print(json.dumps({k: res.get(k) for k in ("work_order", "fabro_run_id", "workspace")}
                     | {"status": (res.get("package") or {}).get("package_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
