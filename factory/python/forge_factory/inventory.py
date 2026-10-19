"""T001 — installed tool/model/dependency inventory, OSS licence matrix and CycloneDX SBOM.

Probes what is *actually installed* on this host (never assumes). Missing tools are recorded as
MISSING with the dependent MCP operation marked DISABLED/BLOCKED by later preflight.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import urllib.request
from importlib import metadata
from pathlib import Path
from typing import Any

from .common import REPO_ROOT, pretty_json, sha256_file, utc_now

# name, candidate executables, version argv, licence (upstream declared), role, required_for_pilot
TOOLS: list[tuple[str, list[str], list[str], str, str, bool]] = [
    ("fabro", ["${FORGE_FABRO_BIN}", "fabro"], ["--version"], "MIT", "orchestration", True),
    ("ollama", ["${FORGE_DATA_ROOT}/ollama-0.34.0/bin/ollama", "ollama"], ["--version"], "MIT",
     "local-model-server", True),
    ("python3", ["python3"], ["--version"], "PSF-2.0", "control-plane-runtime", True),
    ("cmake", ["cmake"], ["--version"], "BSD-3-Clause", "build", True),
    ("ninja", ["ninja"], ["--version"], "Apache-2.0", "build", True),
    ("ctest", ["ctest"], ["--version"], "BSD-3-Clause", "unit-test-runner", True),
    ("clang", ["clang"], ["--version"], "Apache-2.0 WITH LLVM-exception", "host-compiler-analyzer", True),
    ("llvm-profdata", ["llvm-profdata"], ["merge", "--version"], "Apache-2.0 WITH LLVM-exception",
     "coverage", True),
    ("llvm-cov", ["llvm-cov"], ["--version"], "Apache-2.0 WITH LLVM-exception", "coverage", True),
    ("clang-tidy", ["clang-tidy"], ["--version"], "Apache-2.0 WITH LLVM-exception", "static-analysis", False),
    ("gcc", ["gcc"], ["--version"], "GPL-3.0-or-later WITH GCC-exception-3.1", "host-compiler", False),
    ("arm-none-eabi-gcc", ["arm-none-eabi-gcc"], ["--version"], "GPL-3.0-or-later WITH GCC-exception-3.1",
     "target-compiler", False),
    ("arm-none-eabi-size", ["arm-none-eabi-size"], ["--version"], "GPL-3.0-or-later", "footprint", False),
    ("size", ["size", "llvm-size"], ["--version"], "GPL-3.0-or-later", "footprint", True),
    ("objdump", ["objdump", "llvm-objdump"], ["--version"], "GPL-3.0-or-later", "disassembly", True),
    ("cppcheck", ["cppcheck"], ["--version"], "GPL-3.0-or-later", "MISRA-subset-static", True),
    ("cbmc", ["cbmc"], ["--version"], "BSD-4-Clause", "bounded-model-checking", False),
    ("frama-c", ["frama-c"], ["-version"], "LGPL-2.1-only", "abstract-interpretation", False),
    ("why3", ["why3"], ["--version"], "LGPL-2.1-only", "deductive-proof-platform", False),
    ("alt-ergo", ["alt-ergo"], ["--version"], "CECILL-C", "smt-prover", False),
    ("cvc5", ["cvc5"], ["--version"], "BSD-3-Clause", "smt-prover", False),
    ("renode", ["renode"], ["--version"], "MIT", "simulation", False),
    ("gcovr", ["gcovr"], ["--version"], "BSD-3-Clause", "gcc-coverage", False),
    ("git", ["git"], ["--version"], "GPL-2.0-only", "scoped-repo", True),
    ("dot", ["dot"], ["-V"], "EPL-1.0", "workflow-graph-render", False),
    ("systemctl", ["systemctl"], ["--version"], "LGPL-2.1-or-later", "service-watchdog", False),
    ("node", ["node"], ["--version"], "MIT", "browser-smoke-optional", False),
    ("firefox", ["firefox"], ["--version"], "MPL-2.0", "browser-smoke-optional", False),
]

FORBIDDEN_LICENCE_MARKERS = ("proprietary", "commercial", "closed")


def _expand(candidate: str) -> str:
    return os.path.expandvars(candidate) if "$" in candidate else candidate


def _resolve(candidates: list[str]) -> str | None:
    for c in candidates:
        c = _expand(c)
        if "$" in c:
            continue
        if os.sep in c:
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        elif shutil.which(c):
            return shutil.which(c)
    return None


def probe_tool(name: str, candidates: list[str], vargs: list[str]) -> dict:
    exe = _resolve(candidates)
    if not exe:
        return {"name": name, "status": "MISSING", "path": None, "version": None, "sha256": None}
    try:
        p = subprocess.run([exe, *vargs], capture_output=True, text=True, timeout=30)
        text = (p.stdout or p.stderr).strip()
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        status = "INSTALLED" if first else "UNKNOWN_VERSION"
    except (OSError, subprocess.SubprocessError) as exc:
        first, status = f"probe_error:{type(exc).__name__}", "PROBE_FAILED"
    real = os.path.realpath(exe)
    try:
        digest = sha256_file(Path(real)) if os.path.getsize(real) < 400 * 1024 * 1024 else None
    except OSError:
        digest = None
    return {"name": name, "status": status, "path": real, "version": first[:200], "sha256": digest}


def probe_models(base_url: str) -> list[dict]:
    if not base_url.startswith(("http://127.0.0.1", "http://localhost")):
        return [{"name": "ollama-endpoint", "status": "REJECTED_NON_LOCAL", "detail": base_url[:80]}]
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=5) as r:  # noqa: S310
            data = json.load(r)
    except (OSError, ValueError) as exc:
        return [{"name": "ollama-endpoint", "status": "UNREACHABLE", "detail": type(exc).__name__}]
    out = []
    for m in data.get("models", []):
        out.append({"name": m.get("name"), "digest": m.get("digest"), "size": m.get("size"),
                    "family": (m.get("details") or {}).get("family"),
                    "parameter_size": (m.get("details") or {}).get("parameter_size"),
                    "quantization": (m.get("details") or {}).get("quantization_level"),
                    "licence": "Apache-2.0" if (m.get("name") or "").startswith("qwen3") else "UNVERIFIED",
                    "status": "INSTALLED"})
    return out


def python_dependencies(lock: Path) -> list[dict[str, Any]]:
    names = []
    for line in lock.read_text().splitlines():
        if line and not line.startswith((" ", "#")) and "==" in line:
            names.append(line.split("==")[0].strip())
    deps: list[dict[str, Any]] = []
    for n in sorted(set(names)):
        try:
            md = metadata.metadata(n)
            lic = md.get("License-Expression") or md.get("License") or ""
            if not lic or len(lic) > 80:
                classifiers = [c.split("::")[-1].strip() for c in (md.get_all("Classifier") or [])
                               if c.startswith("License ::")]
                lic = "; ".join(classifiers) or (lic[:80] if lic else "UNDECLARED")
            deps.append({"name": n, "version": metadata.version(n), "licence": lic, "status": "INSTALLED"})
        except metadata.PackageNotFoundError:
            deps.append({"name": n, "version": None, "licence": "UNKNOWN", "status": "MISSING"})
    return deps


def licence_issues(entries: list[dict]) -> list[str]:
    issues = []
    for e in entries:
        lic = str(e.get("licence", "")).lower()
        if any(m in lic for m in FORBIDDEN_LICENCE_MARKERS):
            issues.append(f"NON_OSS_LICENCE:{e['name']}:{e.get('licence')}")
        if e.get("status") == "INSTALLED" and lic in ("", "unknown", "undeclared"):
            issues.append(f"LICENCE_UNDECLARED:{e['name']}")
    return issues


def cyclonedx(tools: list[dict], deps: list[dict], models: list[dict]) -> dict:
    comps = []
    for t in tools:
        if t["status"] == "INSTALLED":
            comps.append({"type": "application", "name": t["name"], "version": t["version"],
                          "licenses": [{"expression": t["licence"]}],
                          **({"hashes": [{"alg": "SHA-256", "content": t["sha256"]}]} if t.get("sha256") else {})})
    for d in deps:
        if d["status"] == "INSTALLED":
            comps.append({"type": "library", "name": d["name"], "version": d["version"],
                          "purl": f"pkg:pypi/{d['name'].lower()}@{d['version']}",
                          "licenses": [{"license": {"name": d["licence"][:120]}}]})
    for m in models:
        if m.get("status") == "INSTALLED":
            comps.append({"type": "machine-learning-model", "name": m["name"], "version": m.get("digest", "")[:16],
                          "licenses": [{"license": {"name": m["licence"]}}]})
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
            "metadata": {"timestamp": utc_now(), "component": {"type": "application", "name": "forge-c-factory",
                                                                "version": "0.4.0"}},
            "components": comps}


def build_inventory(ollama_url: str) -> dict:
    tools = []
    for name, cands, vargs, lic, role, required in TOOLS:
        rec = probe_tool(name, cands, vargs)
        rec.update({"licence": lic, "role": role, "required_for_pilot": required})
        tools.append(rec)
    deps = python_dependencies(REPO_ROOT / "requirements" / "forge-factory.lock")
    models = probe_models(ollama_url)
    issues = licence_issues(tools + deps)
    missing_required = [t["name"] for t in tools if t["required_for_pilot"] and t["status"] != "INSTALLED"]
    return {
        "schema": "forge-c/tool-inventory/0.4",
        "generated_at": utc_now(),
        "host": {"node": platform.node(), "platform": platform.platform(), "machine": platform.machine()},
        "policy": {"allow_paid_api": False, "allow_proprietary_static_analyzer": False,
                   "local_inference_only": True},
        "tools": tools, "python_dependencies": deps, "models": models,
        "licence_issues": issues, "missing_required_tools": missing_required,
        "status": "PASS" if not issues and not missing_required else "BLOCKED",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "evidence" / "v0.4" / "inventory")
    ap.add_argument("--ollama-url", default=os.environ.get("FORGE_OLLAMA_URL", "http://127.0.0.1:11435"))
    a = ap.parse_args(argv)
    inv = build_inventory(a.ollama_url)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "tool-inventory.json").write_text(pretty_json(inv), encoding="utf-8")
    (a.out_dir / "sbom.cdx.json").write_text(
        pretty_json(cyclonedx(inv["tools"], inv["python_dependencies"], inv["models"])), encoding="utf-8")
    rows = ["| Tool | Status | Version | Licence | Role |", "|---|---|---|---|---|"]
    rows += [f"| {t['name']} | {t['status']} | {(t['version'] or '-')[:60]} | {t['licence']} | {t['role']} |"
             for t in inv["tools"]]
    (a.out_dir / "TOOL_MATRIX.md").write_text("# Forge-C v0.4 tool matrix (generated)\n\n" + "\n".join(rows) + "\n")
    print(f"T001 {inv['status']} — {a.out_dir}/tool-inventory.json — issues:{len(inv['licence_issues'])} "
          f"missing_required:{','.join(inv['missing_required_tools']) or 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
