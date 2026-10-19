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

from .common import REPO_ROOT, canonical_json, pretty_json, sha256_bytes, sha256_file, state_dir, utc_now
from .events.emit import emit
from .fabro.runconfig import create_workspace, fabro_env, write_run
from .layer import HAL_UNIT_ISOLATION, REGISTER_CONTRACT, TRACE_PROFILE
from .mcp.preflight import fabro_mcp_config
from .mcp.preflight import preflight as mcp_preflight
from .registry.agents import preflight as agent_preflight
from .release.finalize import finalize
from .workflow.builder import binding_for, build


def factory_revision() -> dict:
    """CRE-FR-014: the exact factory source revision that runs this work order (commit + dirty flag)."""

    def git(*a: str) -> str:
        try:
            return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    commit = git("rev-parse", "HEAD")
    return {"commit": commit or "UNKNOWN", "dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD") or "UNKNOWN", "basis": "recorded_at_launch"}


def model_profile(model: str, provider: str, code_model: str | None, nodes: dict) -> dict:
    return {"default": model, "provider": provider, "code_nodes": code_model,
            "nodes": sorted(k for k, v in nodes.items() if v.get("model")),
            "local_only": provider == "ollama",
            # CRE-T051 (CRE-FR-014): sampling is what the factory pins - today nothing beyond the model id
            "sampling": {"temperature": "PROVIDER_DEFAULT (not set by the factory)",
                         "seed": "NOT_SUPPORTED (Fabro run config has no seed)",
                         "reproducibility": "stochastic: repeated runs of the same revision may differ"},
            "token_budget": "unlimited (owner decision 2026-10-15: no token limits for local qwen runs)"
            if provider == "ollama" else "per agent registry max_stage_tokens",
            "note": "local Ollama via gateway" if provider == "ollama" else
            "CLOUD BENCHMARK (user-authorized); not local-model evidence for T048"}


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


def provided_ll(source_wo: str) -> tuple[bytes, dict]:
    """ADR-0009: the HAL work order builds on the LL header of an earlier LL work order whose six phases all passed
    their gates (inspected, unit/integration/target/requirement tested). Returns the header bytes and provenance."""
    from .inspection.engine import PHASES, Store
    from .layer import LL_HEADER, layer_of

    src = state_dir() / "workorders" / source_wo / "workspace"
    if not (src / LL_HEADER).is_file():
        raise FileNotFoundError(f"PROVIDED_LL_MISSING:{source_wo}:{LL_HEADER}")
    if layer_of(src) != "LL":
        raise ValueError(f"PROVIDED_LL_NOT_FROM_LL_WORK_ORDER:{source_wo}:{layer_of(src)}")
    st = Store(src)
    failed = [ph for ph in PHASES if st.gate(ph)["decision"] != "PASS"]
    if failed:
        raise ValueError(f"PROVIDED_LL_NOT_VERIFIED:{source_wo}:{','.join(failed)}")
    data = (src / LL_HEADER).read_bytes()
    pkg = src / ".forge-run/package.json"
    return data, {"path": LL_HEADER, "role": "provided_ll_driver", "sha256": sha256_bytes(data),
                  "source_work_order": source_wo,
                  "source_package": json.loads(pkg.read_text()).get("archive_ref") if pkg.is_file() else None,
                  "rule": "read-only: the HAL work order must not change it (SWE.3 implementation check)"}


def owner_dispositions_for(example_name: str, repo: Path = REPO_ROOT) -> list[dict]:
    """Owner dispositions (config/factory/verification-dispositions.yaml) that apply to this example work order.
    Refuses a disposition without a human approver and date: an agent never settles an input issue."""
    from .assurance.policy import _human
    from .common import load_yaml

    p = Path(repo) / "config/factory/verification-dispositions.yaml"
    ods = [d for d in ((load_yaml(p) or {}).get("dispositions") or [] if p.is_file() else [])
           if example_name in (d.get("examples") or [])]
    bad = [d.get("id") for d in ods if not (_human(d.get("approved_by")) and d.get("approved_at"))]
    if bad:
        raise ValueError(f"OWNER_DISPOSITION_NOT_HUMAN_APPROVED:{bad}")
    return ods


def prepare(example: Path, wo: str, provided_from: str | None = None) -> tuple[Path, dict]:
    spec = json.loads((example / "workorder.json").read_text())
    layer = spec.get("layer", "LL+HAL")
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
    provided = []
    if layer == "HAL":
        if not provided_from:
            raise ValueError("HAL_LAYER_NEEDS_PROVIDED_LL: pass --provided-from <verified LL work order>")
        data, rec = provided_ll(provided_from)
        inputs[rec["path"]] = data
        provided.append(rec)
    head = create_workspace(ws, inputs)
    for rec in provided:
        (ws / rec["path"]).chmod(0o444)
    idx = {}
    for item in listed:
        if item["path"].endswith(".md"):
            idx[item["path"]] = register_index(ws / item["path"])
    manifest = {"schema": "forge-c/work-order/0.4", "work_order": wo, "created_at": utc_now(),
                "input_baseline_commit": head, "factory_revision": factory_revision(),
                "driver": spec["driver"], "layer": layer, "provided": provided, "target": target,
                "trace_profile": TRACE_PROFILE,
                "register_contract": REGISTER_CONTRACT,
                **({"hal_unit_isolation": HAL_UNIT_ISOLATION} if layer == "HAL" else {}),
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
    from .assurance.scope import owner_scope  # owner safety-scope decision (never derived by an agent)

    sc = owner_scope(example.name, wo, sha256_bytes(canonical_json(sorted((i["path"], i.get("sha256")) for i in listed))))
    from .inspection.defects import DISPOSITIONS

    ods = owner_dispositions_for(example.name)
    if ods:  # owner dispositions of known input issues (never written by an agent)
        manifest["owner_dispositions"] = [{"id": d["id"], "disposition": d["disposition"],
                                           "limitation": " ".join(str(d["limitation"]).split())} for d in ods]
        (ws / DISPOSITIONS).write_text(pretty_json(ods))
        (ws / DISPOSITIONS).chmod(0o444)
    if sc:
        from .assurance.scope import allocation_status

        manifest["safety_target"] = sc["scope"]["target_asil"]
        # CAPA-044: the owner scope supersedes the example's target.safety_allocation (it said QM while the scope is
        # ASIL B, and SWE.1 wrote "QM development scope" into ASIL B work products)
        manifest["target"]["safety_allocation"] = allocation_status(sc)
        (ws / ".forge-run/safety_scope.json").write_text(pretty_json(sc))
        (ws / ".forge-run/safety_scope.json").chmod(0o444)
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


RESUME_EXTRA = ["configuration/baselines", "inspection", "verification", "evidence"]
TARGET_BUILD = "build/target-cm55-gcc"


def resume_from(ws: Path, manifest: dict, source_wo: str) -> list[str]:
    """Carry over the leading phases of an earlier work order that genuinely PASSED (gate PASS on an intact,
    non-stale baseline with its recorded inspection), stopping at the first phase that did not. Returns the phases
    still to run. Files are copied byte-identical, so gates recompute PASS from the same evidence."""
    from .inspection.engine import PHASE_PATHS, PHASES, Store

    src = state_dir() / "workorders" / source_wo / "workspace"
    if not src.is_dir():
        raise FileNotFoundError(f"no workspace for {source_wo}")
    st = Store(src)
    stable: list[str] = []
    for ph in PHASES:
        g = st.gate(ph)
        if g["decision"] != "PASS":
            break
        stable.append(ph)
    # CAPA-040 (r132/r133): provided read-only inputs (HAL: the LL header) are this work order's own verified copy;
    # they are never overwritten, and the source's copy must be byte-identical or its carried phases do not apply
    provided = {r["path"]: r["sha256"] for r in manifest.get("provided") or []}
    for rel, sha in provided.items():
        if (src / rel).is_file() and sha256_file(src / rel) != sha:
            raise ValueError(f"RESUME_PROVIDED_MISMATCH:{rel}:{source_wo} built on a different provided file")
    copied = []
    for ph in stable:
        for rel in PHASE_PATHS[ph]:
            if (src / rel).exists():
                (ws / rel).parent.mkdir(parents=True, exist_ok=True)
                if (src / rel).is_dir():
                    base = src / rel
                    shutil.copytree(base, ws / rel, dirs_exist_ok=True, ignore=lambda d, names, base=base, rel=rel: [
                        n for n in names if f"{rel}/{(Path(d) / n).relative_to(base)}" in provided])
                elif rel not in provided:
                    shutil.copy2(src / rel, ws / rel)
                copied.append(rel)
    if stable:
        for rel in RESUME_EXTRA:  # baselines/inspections/verification reports/tool evidence of the stable phases
            if (src / rel).is_dir():
                shutil.copytree(src / rel, ws / rel, dirs_exist_ok=True)
        # r57: the target ELF/map are the build of the carried-over SWE.3 sources (byte-identical) and are referenced by
        # the carried tool evidence; without them the package lacks software/build/*.elf|*.map
        if "SWE.3" in stable and (src / TARGET_BUILD).is_dir():
            shutil.copytree(src / TARGET_BUILD, ws / TARGET_BUILD, dirs_exist_ok=True)
        for ph in PHASES[len(stable):]:  # nothing of a non-stable phase is carried over as passed
            for rel in (f"configuration/baselines/{ph}", f"inspection/{ph}"):
                if (ws / rel).exists():
                    shutil.rmtree(ws / rel)
    d = Store(ws)
    for ph in stable:  # carried-over phases must still pass in the new workspace (integrity check)
        if d.gate(ph)["decision"] != "PASS":
            raise ValueError(f"carried-over {ph} does not pass in the new workspace: {d.gate(ph)}")
    remaining = PHASES[len(stable):]
    rid = src / ".forge-run" / "fabro_run_id"
    manifest["resumed_from"] = {
        "source_work_order": source_wo, "source_fabro_run_id": rid.read_text().strip() if rid.is_file() else None,
        "stable_phases": {ph: st.gate(ph)["reason"] for ph in stable}, "restart_phase": remaining[0] if remaining else None,
        "rule": "leading phases with gate PASS on an intact baseline are carried over byte-identical; the workflow "
                "restarts at the first phase that did not pass"}
    (ws / ".forge-run/manifest.json").write_text(pretty_json(manifest))
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.email=factory@forge-c.local", "-c", "user.name=forge-factory", "commit", "-qm",
                    f"forge: resume from {source_wo} (stable: {', '.join(stable) or 'none'})"], cwd=ws, check=True)
    return remaining


def launch_run(ws: Path, wo: str, toml: Path, fab: str) -> str:
    """Start the Fabro run (CRE-T045: journaled `workorder_launch`, idempotency key = work-order id)."""
    import os

    from .reliability.production import JournalRefused, enforcing, guarded

    prior = ws / ".forge-run/fabro_run_id"

    def launch(_key: str) -> dict:
        # idempotency key honoured by the receiver side (enforcing modes; observe-only keeps the 002 behaviour)
        if enforcing() and prior.is_file() and prior.read_text().strip():
            return {"fabro_run_id": prior.read_text().strip(), "reused": True}
        out = subprocess.run([fab, "run", str(toml), "--detach", "--auto-approve", "--environment", "local",
                              "--label", f"forge={wo}"], cwd=ws, env=fabro_env(), capture_output=True, text=True,
                             timeout=180)
        rid = (out.stdout.strip().splitlines() or [""])[-1]
        if out.returncode != 0 or not rid:  # r58: a rejected workflow used to leave an empty run id silently
            emit("human", "ERROR", f"{wo} Fabro launch failed (exit {out.returncode})", correlation_id=wo)
            raise RuntimeError(f"fabro run failed (exit {out.returncode}): {(out.stderr or out.stdout)[-600:]}")
        prior.write_text(rid)
        return {"fabro_run_id": rid, "fabro_url": os.environ.get("FORGE_FABRO_URL", "")}

    j = guarded("workorder_launch", f"workorder_launch:{wo}", launch)
    if j["status"] == "REQUIRES_OFFLINE_ATTENTION":
        raise JournalRefused(j["status"], f"workorder_launch:{wo}")
    rid = j["receipt"]["fabro_run_id"]  # ALREADY_DONE (enforcing) returns the journaled run id
    prior.write_text(rid)
    return rid


def run(example: Path, wo: str, detach: bool = False, timeout_s: int = 6 * 3600, code_model: str | None = None,
        model: str = "qwen3:8b", provider: str = "ollama", resume: str | None = None,
        provided_from: str | None = None, acp_authors: str | None = None) -> dict:
    if acp_authors:  # owner decision 2026-10-18 (option 3): Codex authors behind the forge ACP proxy + policy gates
        from .acp import codex_home

        if acp_authors != "codex":
            raise ValueError(f"unknown ACP author backend: {acp_authors}")
        codex_home.ensure()
        if not codex_home.logged_in():
            raise RuntimeError(f"CODEX_HOME {codex_home.home()} is not logged in (run: CODEX_HOME=<it> codex login)")
    ws, manifest = prepare(example, wo, provided_from)
    phases = resume_from(ws, manifest, resume) if resume else None
    if phases == []:
        return {"work_order": wo, "workspace": str(ws), "package": finalize(ws, wo), "resumed_from": resume}
    secmap = {}
    for line in (ws / "inputs/index.md").read_text().splitlines():
        parts = [x.strip() for x in line.split(" | ")]
        if len(parts) == 4 and parts[0][:1].isdigit() and parts[0] not in secmap:
            secmap[parts[0]] = parts[3]
    graph, nodes = build(wo, goal=f"{manifest['driver']} for {manifest['target'].get('part_number')} (offline review)",
                         sections=secmap, code_model=code_model, chunk_lines=40 if provider == "ollama" else 150,
                         phases=phases, layer=manifest.get("layer", "LL+HAL"),
                         trace=manifest.get("trace_profile") == TRACE_PROFILE,
                         isolation=manifest.get("hal_unit_isolation") == HAL_UNIT_ISOLATION)
    prof = model_profile(model, provider, code_model, nodes)
    if acp_authors:
        from . import acp
        from .acp import codex_home

        graph, acp_nodes = acp.attach(graph, nodes, ws)
        prof["acp_authors"] = {"nodes": acp_nodes, "model": codex_home.MODEL, "reasoning_effort": codex_home.EFFORT,
                               "provider": acp.ACP_PROVIDER, "codex": codex_home.CODEX,
                               "note": "author roles on Codex; inspectors and every other node on the run model"}
        manifest["acp_authors"] = acp_nodes
        (ws / ".forge-run/manifest.json").write_text(pretty_json(manifest))
    (ws / ".forge-run/model-profile.json").write_text(pretty_json(prof))
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
    fabro_run_id = launch_run(ws, wo, toml, fab)
    # which Fabro server holds the run (local :32290 or the cloud benchmark :32291); no secrets, the token stays in
    # that server's storage. The supervisor's external finalizer uses it to seal packages for runs on either server.
    (ws / ".forge-run/fabro_server.json").write_text(json.dumps(
        {"url": os.environ.get("FORGE_FABRO_URL", ""), "storage": os.environ.get("FORGE_FABRO_STORAGE", "")}))
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
    ap.add_argument("--resume-from", default=None, help="carry over the leading PASSED phases of this work order")
    ap.add_argument("--provided-from", default=None,
                    help="HAL layer (ADR-0009): the verified LL work order whose LL header this HAL builds on")
    ap.add_argument("--acp-authors", choices=["codex"], default=None,
                    help="owner decision 2026-10-18: author roles on Codex via the forge ACP proxy and policy gates")
    a = ap.parse_args(argv)
    res = run(a.example.resolve(), a.wo, a.detach, code_model=a.code_model, model=a.model, provider=a.provider,
              resume=a.resume_from, provided_from=a.provided_from, acp_authors=a.acp_authors)
    print(json.dumps({k: res.get(k) for k in ("work_order", "fabro_run_id", "workspace")}
                     | {"status": (res.get("package") or {}).get("package_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
