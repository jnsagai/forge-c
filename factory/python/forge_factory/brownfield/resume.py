"""Validated, new-work-order brownfield resume (feature 012).

Accepted phases are copied byte-identical and rechecked. Delivery is injected anew
after the inherited SWE.1 PASS. Source attempts and archives are never written.
Compatibility is deliberately strict: a clean, identical factory revision, input
contract, tool identities and local profile are required. Legacy runs without an
identity record must start fresh. No compatibility override exists.
"""
from __future__ import annotations

import copy
import importlib.metadata
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, pretty_json, safe_id, sha256_bytes, sha256_file, state_dir, utc_now

SCHEMA = "forge-c/brownfield-resume/1"
DEFAULT_LIMITS = {"max_attempts": 6, "max_wall_seconds": 86400}
TOOLS = ("clang", "gcc", "arm-none-eabi-gcc", "cppcheck", "cmake", "ninja", "gcovr", "lcov", "cbmc", "goto-cc",
         "frama-c", "why3", "alt-ergo", "cvc5", "robot", "renode", "java")
CONTRACT_FIELDS = ("driver", "layer", "target", "scope", "budgets", "system_names", "guideline", "trace_profile",
                   "register_contract", "hal_unit_isolation", "upstream", "owner_dispositions", "safety_target",
                   "owner_safety_documents", "owner_safety_document_issues", "peripheral", "peripheral_profile_sha256",
                   "delivery", "code_mode", "purpose", "development_safety")
TABLES = ("CREATE TABLE IF NOT EXISTS lineages (root TEXT PRIMARY KEY, started REAL, limits TEXT)",
          "CREATE TABLE IF NOT EXISTS attempts (wo TEXT PRIMARY KEY, root TEXT, parent TEXT, reserved REAL)")


class ResumeRefused(ValueError):
    pass


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ResumeRefused(f"RESUME_RECORD_UNREADABLE:{path.name}") from exc


def files(root: Path, rel: str) -> dict[str, str]:
    """Reject symlinked files AND directories; every copied byte stays inside its workspace."""
    p = root / rel
    if not p.exists() and not p.is_symlink():
        return {}
    out = {}
    for f in ([p] if p.is_file() or p.is_symlink() else [p, *sorted(p.rglob("*"))]):
        if f.is_symlink() or not f.resolve().is_relative_to(root.resolve()):
            raise ResumeRefused(f"RESUME_UNSAFE_PATH:{f.relative_to(root)}")
        if f.is_file():
            out[f.relative_to(root).as_posix()] = sha256_file(f)
    return out


def runtime_identity() -> dict:
    """Content identities, not guessed tool versions; absent tools remain explicitly ABSENT."""
    code = {}
    for rel in ("factory/python/forge_factory", "factory/checklists", "factory/release-manager/policies",
                "config/factory", ".fabro/skills", "requirements/forge-factory.lock", "pyproject.toml"):
        code.update({k: v for k, v in files(REPO_ROOT, rel).items() if "__pycache__" not in k and not k.endswith(".pyc")})
    tools = {}
    for name in TOOLS:
        exe = shutil.which(name)
        tools[name] = {"path": str(Path(exe).resolve()), "sha256": sha256_file(Path(exe).resolve())} if exe else "ABSENT"
    from ..inspection.views import plantuml_jar

    jar = plantuml_jar()
    tools["plantuml_jar"] = {"path": str(jar.resolve()), "sha256": sha256_file(jar)} if jar else "ABSENT"
    packages = {d.metadata["Name"].lower(): d.version for d in importlib.metadata.distributions() if d.metadata["Name"]}
    return {"factory_assets_sha256": sha256_bytes(canonical_json(code)), "tools": tools,
            "python": sys.version, "packages": packages,
            "build_environment": {k: os.environ.get(k) for k in ("CC", "CXX", "CFLAGS", "CPPFLAGS", "LDFLAGS")}}


def contract(man: dict) -> dict:
    historical = man.get("historical_safety_scope")
    version = {}
    if "aspice_resume_contract_version" in man:
        if type(man["aspice_resume_contract_version"]) is not int or man["aspice_resume_contract_version"] != 2 or \
                man.get("purpose") != "ASPICE_ONLY" or not isinstance(man.get("aspice_development"), dict):
            raise ResumeRefused("RESUME_ASPICE_CONTRACT_VERSION_INVALID")
        version["aspice_resume_contract_version"] = 2
        if historical is not None:
            historical = copy.deepcopy(historical)
            scope = historical.get("scope") if isinstance(historical, dict) else None
            if not isinstance(scope, dict) or not man.get("work_order") or \
                    scope.get("work_order_id") != man["work_order"]:
                raise ResumeRefused("RESUME_HISTORICAL_SCOPE_IDENTITY_MISMATCH")
            # This record remains intact in the manifest. Only its own administrative
            # attempt ID is excluded from compatibility; allocation/policy/input provenance stays bound.
            del scope["work_order_id"]
    return {**{k: man.get(k) for k in CONTRACT_FIELDS},
            **{k: man[k] for k in ("aspice_development",) if k in man},
            **({"historical_safety_scope": historical} if "historical_safety_scope" in man else {}),
            **version,
            **({"semantic_required_operations": man["semantic_required_operations"]}
               if "semantic_required_operations" in man else {}),
            "inputs": sorted((r["path"], r["role"], r["sha256"]) for r in man.get("inputs", [])),
            "provided": sorted((r["path"], r["sha256"]) for r in man.get("provided", [])),
            "delivered": sorted((r["path"], r["role"], r["sha256"]) for r in man.get("delivered", []))}


def initialize(ws: Path, man: dict, limits: dict | None = None) -> None:
    limits = dict(DEFAULT_LIMITS if limits is None else limits)
    if set(limits) != set(DEFAULT_LIMITS) or any(type(v) is not int or v < 1 for v in limits.values()):
        raise ResumeRefused("RESUME_LIMITS_INVALID")
    configuration = {}
    for rel in ("configuration/system_names.json", "configuration/target_baseline.json", ".forge-run/safety_scope.json",
                ".forge-run/checklists", *[d["path"] for d in man.get("owner_safety_documents", [])]):
        configuration.update(files(ws, rel))
    man["resume_identity"] = {"schema": SCHEMA, "contract_sha256": sha256_bytes(canonical_json(contract(man))),
                              "configuration": configuration, "input_files": files(ws, "inputs"),
                              "runtime": runtime_identity(), "limits": limits}
    # Register the original budget before any model runs. A missing ledger can never reset an old root's budget.
    folder = state_dir() / "resume"
    folder.mkdir(parents=True, exist_ok=True)
    started = datetime.fromisoformat(man["created_at"].replace("Z", "+00:00")).timestamp()
    identity = (started, json.dumps(limits, sort_keys=True))
    with sqlite3.connect(folder / "lineages.sqlite3", timeout=30) as db:
        for sql in TABLES:
            db.execute(sql)
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT started,limits FROM lineages WHERE root=?", (man["work_order"],)).fetchone()
        if row is not None and row != identity:
            raise ResumeRefused("RESUME_INITIAL_BUDGET_ALREADY_REGISTERED: use a new work-order ID")
        db.execute("INSERT OR IGNORE INTO lineages VALUES (?,?,?)", (man["work_order"], *identity))


def source_workspace(source_wo: str) -> Path:
    return state_dir() / "workorders" / safe_id(source_wo) / "workspace"


def check_source(source_wo: str, destination_wo: str) -> tuple[Path, dict]:
    from ..fabro.client import client_for_workspace, run_status

    try:
        safe_id(destination_wo)
        safe_id(source_wo)
    except ValueError as exc:
        raise ResumeRefused("RESUME_UNSAFE_WORK_ORDER_ID") from exc
    if source_wo == destination_wo:
        raise ResumeRefused("RESUME_SOURCE_EQUALS_DESTINATION")
    src = source_workspace(source_wo)
    if src.is_symlink() or not src.resolve().is_relative_to((state_dir() / "workorders").resolve()):
        raise ResumeRefused("RESUME_UNSAFE_SOURCE")
    man = _read(src / ".forge-run/manifest.json")
    if man.get("work_order") != source_wo or not man.get("delivery"):
        raise ResumeRefused("RESUME_SOURCE_NOT_MATCHING_BROWNFIELD")
    identity = man.get("resume_identity", {})
    if not isinstance(identity, dict) or identity.get("schema") != SCHEMA:
        raise ResumeRefused("RESUME_SOURCE_UNVERSIONED: start a fresh work order")
    limits = identity.get("limits")
    if not isinstance(limits, dict) or set(limits) != set(DEFAULT_LIMITS) or \
            any(type(v) is not int or v < 1 for v in limits.values()) or \
            not isinstance(identity.get("runtime"), dict) or not isinstance(identity.get("contract_sha256"), str):
        raise ResumeRefused("RESUME_SOURCE_IDENTITY_INVALID")
    if man.get("resumed_from") and not man.get("resume_lineage"):
        raise ResumeRefused("RESUME_LINEAGE_RECORD_MISSING")
    remaining_seconds(src)
    rid = src / ".forge-run/fabro_run_id"
    if not rid.is_file():
        raise ResumeRefused("RESUME_SOURCE_NO_RUN_RECEIPT")
    try:
        status = run_status(client_for_workspace(src).get_run(rid.read_text().strip()))
    except Exception as exc:  # noqa: BLE001 - unknown launch/run outcome never permits copying a live workspace
        raise ResumeRefused("RESUME_SOURCE_STATUS_UNKNOWN") from exc
    if status not in {"SUCCEEDED", "FAILED", "CANCELLED", "CANCELED", "DEAD"}:
        raise ResumeRefused(f"RESUME_SOURCE_NOT_TERMINAL:{status}")
    return src, man


def _verify_inputs(ws: Path, man: dict) -> None:
    dynamic = {r["path"] for r in man.get("delivered", [])}
    actual_inputs = {p: sha for p, sha in files(ws, "inputs").items() if p not in dynamic}
    expected_inputs = {p: sha for p, sha in man["resume_identity"]["input_files"].items() if p not in dynamic}
    if actual_inputs != expected_inputs:
        raise ResumeRefused("RESUME_INPUT_MISMATCH:derived sections/index or approved inputs")
    for rel, sha in man["resume_identity"].get("configuration", {}).items():
        if files(ws, rel).get(rel) != sha:
            raise ResumeRefused(f"RESUME_CONFIGURATION_MISMATCH:{rel}")
    for r in [*man.get("inputs", []), *man.get("provided", [])]:
        rel = r["path"]
        if files(ws, rel).get(rel) != r["sha256"]:
            raise ResumeRefused(f"RESUME_INPUT_MISMATCH:{rel}")
    from .delivery import store_dir

    store = store_dir(man["work_order"]) / "files"
    actual = files(store, ".")
    expected = {r["path"]: r["sha256"] for r in man.get("delivered", [])}
    if not expected or actual != expected:
        raise ResumeRefused("RESUME_DELIVERY_STORE_MISMATCH")


def _reserve(source: dict, dest: dict) -> dict:
    """One durable ledger shared by CLI/AFO and sibling resumes. Failed copies consume a reservation."""
    parent = source.get("resume_lineage") or {}
    root = parent.get("root_work_order", source["work_order"])
    limits = source["resume_identity"]["limits"]
    started = parent.get("started_epoch") or datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")).timestamp()
    folder = state_dir() / "resume"
    if not (folder / "lineages.sqlite3").is_file():
        raise ResumeRefused("RESUME_LINEAGE_LEDGER_MISSING")
    with sqlite3.connect(folder / "lineages.sqlite3", timeout=30) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT started,limits FROM lineages WHERE root=?", (root,)).fetchone()
        if row is None:
            raise ResumeRefused("RESUME_LINEAGE_LEDGER_MISSING")
        elif row != (started, json.dumps(limits, sort_keys=True)):
            raise ResumeRefused("RESUME_LINEAGE_IDENTITY_MISMATCH")
        if not parent and root == source["work_order"]:
            db.execute("INSERT OR IGNORE INTO attempts VALUES (?,?,?,?)", (root, root, None, started))
        if not db.execute("SELECT 1 FROM attempts WHERE wo=? AND root=?", (source["work_order"], root)).fetchone():
            raise ResumeRefused("RESUME_PARENT_NOT_RESERVED")
        n = db.execute("SELECT count(*) FROM attempts WHERE root=?", (root,)).fetchone()[0]
        if n >= limits["max_attempts"]:
            raise ResumeRefused("RESUME_ATTEMPT_BUDGET_EXHAUSTED")
        if time.time() >= started + limits["max_wall_seconds"]:
            raise ResumeRefused("RESUME_WALL_BUDGET_EXHAUSTED")
        try:
            db.execute("INSERT INTO attempts VALUES (?,?,?,?)", (dest["work_order"], root, source["work_order"], time.time()))
        except sqlite3.IntegrityError as exc:
            raise ResumeRefused("RESUME_DESTINATION_ALREADY_RESERVED") from exc
    return {"root_work_order": root, "parent_work_order": source["work_order"], "attempt_seq": n + 1,
            "started_epoch": started, "deadline_epoch": started + limits["max_wall_seconds"], "limits": limits,
            "tokens": "UNKNOWN unless reported by Fabro; existing per-role and AFO budgets remain enforced"}


def remaining_seconds(ws: Path) -> float | None:
    """Enforce the original deadline at launch, native stage/tool hooks and structured model calls."""
    path = Path(ws) / ".forge-run/manifest.json"
    if not path.is_file():
        return None
    man = _read(path)
    lineage = man.get("resume_lineage")
    identity = man.get("resume_identity")
    if not lineage and not identity:
        return None
    if lineage:
        dbpath = state_dir() / "resume/lineages.sqlite3"
        if not dbpath.is_file():
            raise ResumeRefused("RESUME_LINEAGE_LEDGER_MISSING")
        with sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True) as db:
            row = db.execute("SELECT started,limits FROM lineages WHERE root=?", (lineage["root_work_order"],)).fetchone()
            member = db.execute("SELECT 1 FROM attempts WHERE wo=? AND root=?",
                                (man["work_order"], lineage["root_work_order"])).fetchone()
        if not row:
            raise ResumeRefused("RESUME_LINEAGE_LEDGER_MISSING")
        if not member or row != (lineage["started_epoch"], json.dumps(lineage["limits"], sort_keys=True)):
            raise ResumeRefused("RESUME_LINEAGE_IDENTITY_MISMATCH")
        deadline = row[0] + json.loads(row[1])["max_wall_seconds"]
        if deadline != lineage["deadline_epoch"]:
            raise ResumeRefused("RESUME_DEADLINE_CHANGED")
    else:
        dbpath = state_dir() / "resume/lineages.sqlite3"
        if not dbpath.is_file():
            raise ResumeRefused("RESUME_LINEAGE_LEDGER_MISSING")
        with sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True) as db:
            row = db.execute("SELECT started,limits FROM lineages WHERE root=?", (man["work_order"],)).fetchone()
        if not row:
            raise ResumeRefused("RESUME_LINEAGE_LEDGER_MISSING")
        started = datetime.fromisoformat(man["created_at"].replace("Z", "+00:00")).timestamp()
        if row != (started, json.dumps(identity["limits"], sort_keys=True)):
            raise ResumeRefused("RESUME_LINEAGE_IDENTITY_MISMATCH")
        deadline = started + identity["limits"]["max_wall_seconds"]
    remaining = deadline - time.time()
    if remaining <= 0:
        raise ResumeRefused("RESUME_WALL_BUDGET_EXHAUSTED")
    return remaining


def resume(ws: Path, man: dict, source_wo: str, upto: str | None = None) -> list[str]:
    from ..inspection.engine import PHASE_PATHS, PHASES, Store
    from .delivery import store_dir
    from .inject import inject
    from .verify import verify

    src, old = check_source(source_wo, man["work_order"])
    if ws.resolve() != source_workspace(man["work_order"]).resolve() or ws.resolve() == src.resolve():
        raise ResumeRefused("RESUME_DESTINATION_PATH_MISMATCH")
    if (ws / ".forge-run/fabro_run_id").exists() or (ws / ".forge-run/package.json").exists():
        raise ResumeRefused("RESUME_DESTINATION_ALREADY_LAUNCHED")
    files(ws, ".")  # a caller-provided destination cannot redirect any copy through symlinked directories
    if upto is not None and upto not in PHASES:
        raise ResumeRefused(f"RESUME_INVALID_PHASE:{upto}")
    a, b = old["resume_identity"], man.get("resume_identity")
    if b is None or a["contract_sha256"] != sha256_bytes(canonical_json(contract(old))) or \
            b["contract_sha256"] != sha256_bytes(canonical_json(contract(man))) or a != b:
        raise ResumeRefused("RESUME_CONTRACT_OR_RUNTIME_CHANGED")
    revision = old.get("factory_revision", {})
    if revision.get("dirty") or not revision.get("commit") or revision.get("commit") == "UNKNOWN" or \
            {k: revision.get(k) for k in ("commit", "dirty")} != \
            {k: man.get("factory_revision", {}).get(k) for k in ("commit", "dirty")}:
        raise ResumeRefused("RESUME_FACTORY_REVISION_CHANGED_OR_DIRTY")
    if old.get("local_profile") != man.get("local_profile"):
        raise ResumeRefused("RESUME_LOCAL_PROFILE_CHANGED")
    _verify_inputs(src, old)
    _verify_inputs(ws, man)
    st = Store(src)
    stable = []
    invalidation = "ALL_PHASES_PASSED"
    for phase in PHASES:
        g = st.gate(phase)
        if phase == upto or g["decision"] != "PASS":
            invalidation = "REQUESTED_UPSTREAM_RETURN" if phase == upto else g["reason"]
            break
        inspection = st.inspections(phase)[-1]
        baseline = st.latest_baseline(phase)
        if inspection.get("inspector_role") != f"swe{phase[-1]}-inspector" or \
                inspection.get("checklist_sha256") != st.checklist(phase)["sha256"] or \
                baseline.get("author_role") != f"swe{phase[-1]}-author" or \
                any(inspection.get("items", {}).get(c["id"], {}).get("verdict") != "PASS" for c in
                    st.applicable(st.checklist(phase))["checks"] if c.get("required")):
            invalidation = "INSPECTION_IDENTITY_OR_CHECKLIST_CHANGED"
            break
        stable.append(phase)
    # OPEN/IN_FIX upstream defects invalidate their owning phase and everything after it.
    defects = files(src, ".forge-run/defects")
    for rel in defects:
        d = _read(src / rel)
        target = d.get("target_phase")
        if d.get("status") in ("OPEN", "IN_FIX") and target in stable:
            stable = stable[:stable.index(target)]
            invalidation = "OPEN_UPSTREAM_DEFECT"
    # The historical injection must point to precisely the inherited requirement baseline.
    if stable:
        injection = _read(src / ".forge-run/delivery/injection.json")
        base = st.latest_baseline("SWE.1")
        if injection.get("swe1_baseline_hash") != base["baseline_hash"] or \
                injection.get("swe1_baseline_id") != base["baseline_id"] or \
                injection.get("files") != old["delivered"] or injection.get("injected_at", "") < base["frozen_at"]:
            raise ResumeRefused("RESUME_INJECTION_PROVENANCE_MISMATCH")
        for r in old["delivered"]:
            if old["code_mode"] == "FROZEN" or r["role"] != "delivered_code":
                if files(src, r["path"]).get(r["path"]) != r["sha256"]:
                    code = "FROZEN_DELIVERY_CHANGED" if old["code_mode"] == "FROZEN" else "DEPENDENCY_CHANGED"
                    raise ResumeRefused(f"RESUME_{code}:{r['path']}")
    selected = {}
    for phase in stable:
        for rel in [*PHASE_PATHS[phase], f"configuration/baselines/{phase}", f"inspection/{phase}",
                    f".forge-run/lrtx/{phase}", f".forge-run/lrtx/{phase}-inspect"]:
            selected.update(files(src, rel))
    if stable:
        for rel in ("verification", "evidence", ".forge-run/safec", ".forge-run/assurance"):
            selected.update(files(src, rel))
    for rel in (".forge-run/defects", ".forge-run/test-snapshots", ".forge-run/gates/upstream-loops.jsonl"):
        selected.update(files(src, rel))
    if "SWE.3" in stable:
        selected.update(files(src, "build/target-cm55-gcc"))
    # Copy accepted evidence from a stable snapshot; never import a terminal package or failed inspection as PASS.
    man["resume_lineage"] = _reserve(old, man)
    protected = {r["path"]: r["sha256"] for r in man.get("provided", [])}
    delivered = {r["path"]: r["sha256"] for r in man["delivered"]}
    for rel, sha in selected.items():
        if rel in protected or rel in delivered:
            continue
        p = ws / rel
        if p.exists() and sha256_file(p) != sha:
            raise ResumeRefused(f"RESUME_DESTINATION_CONFLICT:{rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, p)
        if sha256_file(p) != sha or sha256_file(src / rel) != sha:
            raise ResumeRefused(f"RESUME_COPY_HASH_MISMATCH:{rel}")
    if stable:
        from ..assurance.package import attestation

        (ws / ".forge-run/resume").mkdir(parents=True, exist_ok=True)
        (ws / ".forge-run/resume/inherited-independence.json").write_text(pretty_json(attestation(src)))
        result = inject(ws)  # re-establish SWE.1-before-code in the NEW work order using its own intake store
        if result["status"] != "INJECTED":
            raise ResumeRefused("RESUME_DELIVERY_INJECTION_REFUSED:" + ";".join(result["issues"]))
        if "SWE.3" in stable and man["code_mode"] == "FIX_ALLOWED":
            for rel, sha in delivered.items():
                if selected.get(rel, sha) != sha:
                    (ws / rel).write_bytes((src / rel).read_bytes())
        result = verify(ws, "resume")
        if result["issues"]:
            raise ResumeRefused("RESUME_DELIVERY_VERIFICATION_FAILED:" + ";".join(result["issues"]))
        ledger = ws / "evidence/tool-results.jsonl"
        if ledger.is_file():
            rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
            ledger.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows if r.get("phase") in stable))
        assurance = ws / ".forge-run/assurance/gate-log.jsonl"
        if assurance.is_file():
            rows = [json.loads(line) for line in assurance.read_text().splitlines() if line.strip()]
            # Keep source-context findings only for inherited phases and their current inspected baseline.
            # Future phases must acquire their own assurance observations in the new attempt.
            rows = [r for r in rows if r.get("phase") in stable and r.get("ts_utc", "") >=
                    st.inspections(r["phase"])[-1]["recorded_at"]]
            assurance.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
        # Later tool records never substitute for checks on the carried code baseline.
        for phase in stable:
            if Store(ws).gate(phase)["decision"] != "PASS":
                raise ResumeRefused(f"RESUME_CARRIED_GATE_INVALID:{phase}")
    for rel, sha in selected.items():
        if sha256_file(src / rel) != sha:
            raise ResumeRefused(f"RESUME_SOURCE_CHANGED_DURING_COPY:{rel}")
    remaining = PHASES[len(stable):]
    report = {"schema": SCHEMA, "source_work_order": source_wo,
              "source_fabro_run_id": (src / ".forge-run/fabro_run_id").read_text().strip(),
              "source_manifest_sha256": sha256_file(src / ".forge-run/manifest.json"),
              "stable_phases": {ph: st.gate(ph)["reason"] for ph in stable},
              "restart_phase": remaining[0] if remaining else None, "invalidation_reason": invalidation,
              "copied_files_sha256": selected, "lineage": man["resume_lineage"], "validated_at": utc_now()}
    report["filtered_evidence_sha256"] = {
        rel: sha256_file(ws / rel) for rel in ("evidence/tool-results.jsonl", ".forge-run/assurance/gate-log.jsonl")
        if (ws / rel).is_file()}
    man["resumed_from"] = {k: report[k] for k in ("source_work_order", "source_fabro_run_id", "stable_phases", "restart_phase")}
    man["resumed_from"]["validation_ref"] = ".forge-run/resume/validation.json"
    (ws / ".forge-run/resume").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/resume/source-manifest.json").write_bytes((src / ".forge-run/manifest.json").read_bytes())
    (ws / ".forge-run/resume/validation.json").write_text(pretty_json(report))
    (ws / ".forge-run/manifest.json").write_text(pretty_json(man))
    # Keep the independent intake store referenced by the new manifest; never import the source's store path.
    if Path(man["delivery_intake"]["store"]) != store_dir(man["work_order"]):
        raise ResumeRefused("RESUME_DELIVERY_STORE_PATH_MISMATCH")
    return remaining
