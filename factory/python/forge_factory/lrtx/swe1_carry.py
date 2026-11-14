"""Owner factory rule 2026-11-13 (decision log D36; specs/021-preserve-validated-artifacts/granularity-analysis.md):
"whenever a run finish and need to run again due to any reason, the artifacts that was already inspected and validated
must be preserved between runs, it can be changed if other dependencies requires to, otherwise must be kept".

First application, functional-level SWE.1 at requirement granularity. A work order names its predecessor runs in
`swe1.carry_from` (manifest `swe1_carry_from`, first existing workspace of this line wins). The carry applies only
while the dependency it rests on is unchanged: the governance inventory (the order's inputs, delivered API and scope
rule) must be byte-identical to the source's, else nothing is carried (INPUT_CHANGED).

- Governance: the source's validated governance answer seeds this run's governance task; it is re-validated by the
  current checks (the package is re-assembled and its coverage re-checked deterministically) - no model call.
- Author: per task, the source's VALID requirements are migrated to the current template (template v2 adds
  `operations`, derived from the delivered functions the requirement names) and validated by the current validators.
  All valid: the task is kept as is (no model call). Otherwise only the requirements the findings name are reworked;
  every other requirement is kept byte-identical (merge after the answer). A task-level rule that reshapes the set
  (DESIGN_CONSTRAINT_LIMIT) lets the author rewrite the whole task - that dependency changed.
- Per-requirement inspection: a requirement still identical to the migrated source requirement keeps the source's
  PASS verdict (no re-judgement). Set-level checks (SQ, gate items) are judged again once on the new set.
Every carried record names its source (work order, record sha) so the evidence chain stays auditable."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import canonical_json, pretty_json, sha256_bytes, sha256_file, utc_now
from ..governance import inventory as GI
from . import visit as V

PHASE = "SWE.1"
SOURCE_KEY = "swe1_carry_from"
CARRY_NOTE = ("[carried] the requirements not named in the findings above were already inspected and validated in an "
              "earlier run of this order: return them unchanged, with the same key; change only the requirements the "
              "findings name")


def _manifest(ws: Path) -> dict:
    try:
        return json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    except (OSError, ValueError):
        return {}


# The line's own retries (afo/line_campaign.py: attempt n of a series appends B, C, ...) of a functional SWE.1 order.
RETRY_NAME = re.compile(r"^(WO-[A-Z0-9]+-SWE1-[A-Z0-9-]+-L\d+)([A-Z]{0,2})$")


def predecessors(wo: str | None) -> list[str]:
    """CAPA (run WO-F014-SWE1-SPIM-20261113-L51 -> L51B): the line's automatic retry of a functional SWE.1 order
    named no carry source and started over, although the owner rule D36 keeps what an earlier attempt already
    inspected and validated. Attempt n of a series carries from its earlier attempts, newest first; the inventory
    check in source() still refuses an attempt whose inputs changed."""
    from ..afo.line_campaign import retry_suffix

    m = RETRY_NAME.match(wo or "")
    if not m or not m.group(2):
        return []
    n = 0
    for ch in m.group(2):  # bijective base 26 (retry_suffix): B -> 2, Z -> 26, AA -> 27
        n = n * 26 + ord(ch) - 64
    return [m.group(1) + retry_suffix(k) for k in range(n - 1, 0, -1)]


def candidates(ws: Path) -> list[str]:
    """The work order's named sources (`swe1.carry_from`) first, then the earlier attempts of its own series."""
    man = _manifest(ws)
    named = list(man.get(SOURCE_KEY) or [])
    auto = predecessors(man.get("work_order")) if man.get("swe1_level") == "functional" else []
    return named + [w for w in auto if w not in named]


def source(ws: Path) -> tuple[Path | None, dict]:
    """The predecessor workspace to carry from and the provenance record (None and the reason when there is none)."""
    from ..brownfield.resume import source_workspace
    from ..common import state_dir

    ws = Path(ws)
    cands = candidates(ws)
    if not cands:
        return None, {"reason": "NO_CARRY_SOURCE"}
    inv = ws / GI.OUT
    if not inv.is_file():
        return None, {"reason": "INVENTORY_MISSING"}
    want = sha256_file(inv)
    root = (state_dir() / "workorders").resolve()
    reasons = []
    for wo in cands:
        try:
            p = source_workspace(wo)
        except (ValueError, OSError):
            reasons.append(f"{wo}:INVALID")
            continue
        if not p.is_dir() or p.resolve() == ws.resolve() or not p.resolve().is_relative_to(root):
            reasons.append(f"{wo}:NOT_AVAILABLE")
            continue
        if not (p / GI.OUT).is_file() or sha256_file(p / GI.OUT) != want:
            reasons.append(f"{wo}:INPUT_CHANGED")  # the inputs the requirements rest on changed: nothing is carried
            continue
        return p, {"source_work_order": wo, "inventory_sha256": want}
    return None, {"reason": ";".join(reasons) or "NO_CARRY_SOURCE"}


def _record(src: Path, phase: str, task: str) -> tuple[dict | None, bytes | None]:
    ck = V._ckpt(src, phase, task)
    if not ck.is_file() or ck.is_symlink() or not ck.resolve().is_relative_to(src.resolve()):
        return None, None
    raw = ck.read_bytes()
    try:
        rec = json.loads(raw)
    except ValueError:
        return None, None
    if rec.get("task") != task or rec.get("status") != "VALID" or rec.get("doc") is None:
        return None, None
    return rec, raw


def migrate(r: dict, task: dict, ctx: dict) -> dict:
    """A source requirement in the current template's shape. Template v2: `operations` from the delivered functions of
    the task the requirement names (design constraints: none); attributes the template does not have are dropped."""
    attrs = list(ctx["template"]["attributes"])
    out = {a: r[a] for a in attrs if a in r}
    if "operations" in attrs and "operations" not in r:
        if task.get("kind") == "design" or r.get("type") == "design_constraint":
            ops = []
        else:
            pool = list(task.get("functions") or sorted(ctx["in_scope"]))
            text = " ".join(str(r.get(k, "")) for k in ("statement", "title", "precondition"))
            ops = [f for f in pool if re.search(rf"(?<![A-Za-z0-9_]){re.escape(f)}(?![A-Za-z0-9_])", text)]
        out["operations"] = ops
    return {a: out[a] for a in attrs if a in out}


def _named_keys(findings: list[str]) -> set[str]:
    return {m.group(1) for f in findings for m in [re.match(r"^\[([^\]]+)\]", f)] if m}


def wanted(ws: Path) -> bool:
    return bool(candidates(ws))


def _keep_path(ws: Path, task: str) -> Path:
    return Path(ws) / ".forge-run/lrtx/SWE.1/carry" / (task.replace(":", "__") + ".json")


def _kept(ws: Path, task: str) -> dict:
    p = _keep_path(ws, task)
    try:
        return json.loads(p.read_text())["kept"] if p.is_file() else {}
    except (OSError, ValueError, KeyError):
        return {}


def release(ws: Path, task: str, findings: list[str] | None) -> None:
    """A later finding that names a kept requirement releases it: a dependency now requires the change."""
    named = _named_keys(findings or [])
    kept = _kept(ws, task)
    if not named or not (named & set(kept)):
        return
    p = _keep_path(ws, task)
    rec = json.loads(p.read_text())
    rec["kept"] = {k: v for k, v in kept.items() if k not in named}
    rec.setdefault("released", []).extend(sorted(named & set(kept)))
    p.write_text(pretty_json(rec))


def seed_task(ws: Path, task: dict, base_hash: str, ctx: dict) -> tuple[str, list[str], dict]:
    """Seed this run's checkpoint of `task` from the predecessor. Returns (state, findings, kept): CARRIED (every
    requirement still valid; VALID checkpoint written), REWORK (INVALID checkpoint with the migrated answer and the
    findings as its errors - the author's run_task repairs exactly that; `kept` = key -> requirement to keep unchanged,
    persisted for later node executions), or NONE."""
    from . import swe1_functional as F

    if V._ckpt(ws, PHASE, task["id"]).is_file():
        return "NONE", [], {}
    src, meta = source(ws)
    if src is None:
        return "NONE", [], {}
    old, raw = _record(src, PHASE, task["id"])
    if old is None:
        return "NONE", [], {}
    reqs = [migrate(r, task, ctx) for r in old["doc"].get("requirements") or []]
    doc = {"requirements": reqs, "open_points": list(old["doc"].get("open_points") or [])}
    errs = F.validate_task(ws, doc, task, ctx)
    reshape = any(f.startswith(f"[{task['id']}] ") for f in errs)  # a task-level rule: the set itself changes
    named = _named_keys(errs)
    kept = {} if reshape else {r["key"]: r for r in reqs if r.get("key") not in named}
    prov = {**meta, "record_sha256": sha256_bytes(raw), "requirements": len(reqs),
            "kept": len(reqs) if not errs else len(kept), "reshape": reshape}
    rec = {"task": task["id"], "status": "INVALID" if errs else "VALID", "doc": doc,
           "errors": errs + [CARRY_NOTE] if errs else [], "base_hash": base_hash, "attempts": [], "at": utc_now(),
           "reused": False, "carried_from": prov}
    ck = V._ckpt(ws, PHASE, task["id"])
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(pretty_json(rec))
    if not errs:
        return "CARRIED", [], kept
    kp = _keep_path(ws, task["id"])
    kp.parent.mkdir(parents=True, exist_ok=True)
    kp.write_text(pretty_json({"task": task["id"], "carried_from": prov, "kept": kept, "at": utc_now()}))
    return "REWORK", errs + [CARRY_NOTE], kept


def merge_kept(ws: Path, task: dict, rec: dict, ctx: dict) -> dict:
    """After the rework answer: every kept requirement back byte-identical, the reworked and new ones from the answer.
    Written only when the merged answer still validates (else the answer stays and the refusal is recorded)."""
    from . import swe1_functional as F

    kept = _kept(ws, task["id"])
    if rec.get("status") != "VALID" or not kept:
        return rec
    ans = rec["doc"]["requirements"]
    merged = [kept[r["key"]] if r.get("key") in kept else r for r in ans]
    have = {r.get("key") for r in merged}
    merged += [r for k, r in kept.items() if k not in have]  # a kept requirement the answer dropped comes back
    doc = {**rec["doc"], "requirements": merged}
    if doc == rec["doc"]:
        return rec
    errs = F.validate_task(ws, doc, task, ctx)
    ck = V._ckpt(ws, PHASE, task["id"])
    if errs:
        out = {**rec, "carry_merge": {"refused": errs[:10]}}
    else:
        out = {**rec, "doc": doc, "carry_merge": {"restored": sorted(k for k in kept if
                                                                     kept[k] not in ans)}}
    ck.write_text(pretty_json(out))
    return out


def seed_governance(ws: Path, visit: str, task: str, base_hash: str, check) -> bool:
    """The predecessor's validated governance answer as this run's checkpoint (same inventory, current checks)."""
    if V._ckpt(ws, visit, task).is_file():
        return False
    src, meta = source(ws)
    if src is None:
        return False
    old, raw = _record(src, visit, task)
    if old is None or check(old["doc"]):
        return False
    ck = V._ckpt(ws, visit, task)
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(pretty_json({**old, "base_hash": base_hash, "at": utc_now(), "reused": False,
                               "carried_from": {**meta, "record_sha256": sha256_bytes(raw)}}))
    return True


def verdict_carrier(ws: Path):
    """A function ref -> carried PASS verdict (or None), for the per-requirement inspection of this run."""
    from . import swe1_functional as F
    from . import swe1_quality as Q

    src, meta = source(ws)
    if src is None:
        return None
    try:
        ctx = F.context(ws)
        tasks = {t["id"]: t for t in F.plan(ws)}
    except ValueError:
        return None
    old_verdicts = Q.verdicts(src)
    docs: dict[str, dict] = {}

    def carry(ref: dict) -> dict | None:
        task = tasks.get(ref["task"])
        if task is None:
            return None
        if ref["task"] not in docs:
            old, _raw = _record(src, PHASE, ref["task"])
            docs[ref["task"]] = {r.get("key"): r for r in ((old or {}).get("doc") or {}).get("requirements") or []}
        obj = docs[ref["task"]].get(ref["key"])
        if obj is None or migrate(obj, task, ctx) != ref["obj"]:
            return None  # changed since the source run: judged again
        old_sha = sha256_bytes(canonical_json(obj))
        v = old_verdicts.get((f"{ref['task']}|{ref['key']}", old_sha))
        if not v or v.get("passed") is not True:
            return None
        return {**v, "sha": ref["sha"], "swr": ref["swr"], "at": utc_now(),
                "carried_from": {**meta, "source_sha": old_sha, "source_swr": v.get("swr")}}
    return carry
