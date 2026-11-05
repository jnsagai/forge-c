"""CAPA-133 (owner decision 2026-11-03): an inspection is bound to the checklist ITEMS that apply to its work order,
not to the whole checklist file.

Incident: oracle commit a88b61a5 changed only the wording of SWE2-08 (its new clause concerns a HAL with a bounded
wait). The gate compared the inspection's `checklist_sha256` with the sha of the whole resolved checklist
(engine.py gate, `INSPECTION_ASSESSMENT_CONTEXT_CHANGED`), so every earlier SWE.2 verdict - LL orders included - had to
be re-inspected and provided_ll refused the verified ST CRC LL lineage WO-F014-SWE6-CRCL-20261103-L24.

Binding of a resolved checklist to a work order (deterministic, model-free):
* context: phase, version, policy, assessment context view and QM tailoring of the checklist. Any change re-inspects.
* items: the applicable items in checklist order, each as (id, sha256 of every field of the item except `source`
  (provenance text) and `revisions` (owner equivalence records, below)). Criterion, evidence, severity, required flag,
  deterministic check, tool, rules and applicability selectors are all inside the hash.
* applicability: `applies_when: owner_trace_profile` as before (work orders that opted in), and an optional
  `applies_to` selector {layer: [...], purpose: [...]}; an unknown selector key keeps the item applicable.
Comparison (conservative): the verdict holds only when the context is equal, the applicable item ids are the same in
the same order (an added, removed, reordered or newly (in)applicable item re-inspects), the inspection recorded a
verdict for each of them, and every item hash is equal - or the current item carries an owner revision record
`{previous_item_sha256, item_sha256, unchanged_for: {layer: [...]}}` bound to exactly the recorded and the current
item hash and listing this order's layer/purpose exactly. A later edit of the item changes its hash and voids the
record. An item edit that only changes what the item asks of OTHER orders must be declared that way by the owner:
prose is never interpreted.

Inspections recorded before CAPA-133 carry only the whole-file sha. Their bound checklist is recovered from the
repository history: the historical checklist whose resolved sha, composed with this order's current assessment
context, equals the recorded `checklist_sha256` is proven to be the one inspected (all fields, evidence included -
the order's `.forge-run/checklists` copy keeps only five fields per item and is not verifiable against that sha).
No match, or no git history, keeps the old outcome: re-inspect. New inspections also record their item binding."""
from __future__ import annotations

import functools
import subprocess
import tempfile
from pathlib import Path

import yaml

from ..afo.durable import digest
from ..common import REPO_ROOT

SCHEMA = "forge-c/inspection-item-binding/1"
FIELD = "item_binding"
NON_ASK = ("source", "revisions")
SELECTOR_KEYS = ("layer", "purpose")
CHECKLIST_DIRS = ("factory/checklists", "factory/release-manager/checklists")


def _manifest(ws: Path) -> dict:
    from ..brownfield import manifest_of

    return manifest_of(ws)


def _order(ws: Path) -> dict:
    from ..layer import layer_of

    return {"layer": layer_of(ws), "purpose": _manifest(ws).get("purpose")}


def _values(v) -> list:
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def _matches(key: str, allowed: list, order: dict, exact: bool) -> bool:
    value = order.get(key)
    if value in allowed:
        return True
    # a combined LL+HAL order contains both layers: an LL or HAL item applies to it (never the reverse)
    return not exact and key == "layer" and value == "LL+HAL" and bool({"LL", "HAL"} & set(allowed))


def applies(item: dict, ws: Path) -> bool:
    """Whether a checklist item applies to the work order (also the inspection's item set, engine.applicable)."""
    from ..layer import swtrace_enabled

    if item.get("applies_when") == "owner_trace_profile" and not swtrace_enabled(ws):
        return False
    selector = item.get("applies_to")
    if not isinstance(selector, dict):
        return True  # no (or a malformed) selector: the item applies, so its changes re-inspect
    order = _order(ws)
    return all(_matches(k, _values(v), order, exact=False) for k, v in selector.items() if k in SELECTOR_KEYS)


def item_sha256(item: dict) -> str:
    return digest({k: v for k, v in item.items() if k not in NON_ASK})


def binding(ws: Path, checklist: dict) -> dict:
    """The item binding of a resolved (assessment-context composed) checklist for this work order."""
    return {"schema": SCHEMA,
            "context_sha256": digest({k: checklist.get(k) for k in ("phase", "version", "policy",
                                                                    "assessment_context", "qm_tailoring")}),
            "items": [[c["id"], item_sha256(c)] for c in checklist["checks"] if applies(c, ws)]}


def _bridged(item: dict, old: str, new: str, ws: Path) -> bool:
    """An owner revision record declares that this exact edit does not change what the item asks of this order."""
    order = _order(ws)
    for r in item.get("revisions") or []:
        sel = r.get("unchanged_for") if isinstance(r, dict) else None
        if not isinstance(sel, dict) or not sel or any(k not in SELECTOR_KEYS for k in sel):
            continue
        if r.get("previous_item_sha256") == old and r.get("item_sha256") == new and \
                all(_matches(k, _values(v), order, exact=True) for k, v in sel.items()):
            return True
    return False


def _git(*args: str) -> bytes | None:
    try:
        p = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


@functools.lru_cache(maxsize=64)
def _history(head: str, phase: str, brownfield: bool) -> tuple[dict, ...]:
    """Every distinct resolved checklist of the phase in the history of HEAD (newest first)."""
    from .engine import BROWNFIELD_CHECKLISTS, load_checklist

    log = _git("log", "--format=%H", head, "--", *CHECKLIST_DIRS)
    out, seen = [], set()
    for commit in (log or b"").decode().split():
        with tempfile.TemporaryDirectory(prefix="forge-checklist-") as td:
            root = Path(td).resolve()
            try:
                for rel in (f"factory/checklists/v0.4/{phase}.yaml", f"{BROWNFIELD_CHECKLISTS}/{phase}.yaml"):
                    data = _git("show", f"{commit}:{rel}")
                    if data is not None:
                        (root / rel).parent.mkdir(parents=True, exist_ok=True)
                        (root / rel).write_bytes(data)
                ov = root / f"{BROWNFIELD_CHECKLISTS}/{phase}.yaml"
                if not (brownfield and ov.is_file()):
                    ov = root / f"factory/checklists/v0.4/{phase}.yaml"
                base_rel = str(yaml.safe_load(ov.read_text())["extends"]["path"])
                base = (root / base_rel).resolve()
                data = _git("show", f"{commit}:{base_rel}")
                if data is None or not base.is_relative_to(root):
                    continue
                base.parent.mkdir(parents=True, exist_ok=True)
                base.write_bytes(data)
                resolved = load_checklist(phase, root=root, brownfield=brownfield)
            except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
                continue  # noqa: S112 - an unreadable or tampered historical version is no candidate
        if resolved["sha256"] not in seen:
            seen.add(resolved["sha256"])
            out.append(resolved)
    return tuple(out)


def recorded(ws: Path, record: dict, phase: str | None = None) -> dict | None:
    """The item binding an inspection record was made under, else None (unknown: re-inspect)."""
    stored = record.get(FIELD)
    if isinstance(stored, dict) and stored.get("schema") == SCHEMA:
        return stored
    sha, phase = record.get("checklist_sha256"), phase or record.get("phase")
    if not sha or not phase:
        return None
    from ..brownfield import is_brownfield
    from .assessment_context import checklist as compose

    manifest = _manifest(ws)
    head = (_git("rev-parse", "HEAD") or b"").decode().strip()
    if not head:
        return None
    for resolved in _history(head, phase, is_brownfield(manifest)):
        try:
            composed = compose(manifest, resolved)
        except (ValueError, KeyError):
            continue
        if composed["sha256"] == sha:
            return binding(ws, composed)
    return None


def unchanged(ws: Path, record: dict, checklist: dict) -> bool:
    """True when the inspection's verdict still binds the current checklist for this work order."""
    if record.get("checklist_sha256") == checklist["sha256"]:
        return True
    old = recorded(ws, record, checklist.get("phase"))
    if old is None:
        return False
    new = binding(ws, checklist)
    if old.get("schema") != new["schema"] or old.get("context_sha256") != new["context_sha256"]:
        return False
    if [i for i, _ in old.get("items") or []] != [i for i, _ in new["items"]]:
        return False
    if any(i not in (record.get("items") or {}) for i, _ in new["items"]):
        return False
    current = {c["id"]: c for c in checklist["checks"]}
    return all(a == b or _bridged(current[i], a, b, ws) for (i, a), (_, b) in zip(old["items"], new["items"], strict=True))
