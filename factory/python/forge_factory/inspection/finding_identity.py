"""Deterministic identity of inspector findings across inspection rounds (owner change 2026-11-02).

On the cloud comparison line the strict inspector failed one checklist item in three rounds with a DIFFERENT issue
each round (the author fixed the issue, the inspector found the next one: WO-F014-CMP-SWE1-RCC-20261102-06,
-IWDG-20261102-05, -CRCL-20261102-06), and the item-only rule SAME_ITEM_FAILED_3X (CAPA-087) stopped them as STUCK.
An item is stuck only when the SAME finding persists; a different finding on the same item is progress.

Two findings are the same finding when, after `normalize`:

1. near-verbatim: the token-sequence similarity (difflib ratio, order-aware) is >= NEAR_VERBATIM (0.85), whatever
   requirement ids they cite (a verbatim repeat on renumbered requirements is still a repeat); or
2. same location and same defect wording: the SWR ids they cite (ranges expanded) intersect, or one of them cites
   none (section-level findings: SWE.2 architecture texts), AND the Dice coefficient of their token sets is
   >= SAME_DEFECT (0.42).

Calibration (27 SAME_ITEM_FAILED_3X stops of the cloud line, 2026-11-02, every consecutive-round finding pair):
reworded repeats of one issue on intersecting ids scored Dice 0.44-0.80; different issues on intersecting ids at most
0.39 (RCC-06 round 1 SWR-653 serialization vs round 2 SWR-006/007 RCC_CR preservation). Different issues of the same
kind on DISJOINT ids scored up to 0.61 (the IWDG-02 trace findings of SWR-001..004 vs SWR-005), so disjoint ids are
never matched by wording alone: only a near-verbatim repeat crosses them.

Normalization: severity labels and checklist item ids are dropped, workproduct paths and hash-named open-point ids
(OP-<hex>, regenerated with the text) are removed, the text is lower-cased and split into word tokens, and common
function words and one-character tokens are dropped. No model and no randomness: the same texts always give the
same answer.
"""
from __future__ import annotations

import difflib
import re

NEAR_VERBATIM = 0.85
SAME_DEFECT = 0.42

_STOP = frozenset(
    "the a an and or of to in on for by with is are be its it this that these those as at from not no but their they "
    "which while than then into within per each all any only also does do can cannot shall must will would critical "
    "major minor".split())
_ITEM_ID = re.compile(r"\bSWE\d-\d+\b")
_PATH = re.compile(r"\S*workproducts/\S*|\S+\.(?:md|json|csv|puml|c|h|py|yaml|robot)\b")
_OPEN_POINT = re.compile(r"\bOP-[0-9a-f]{8,}\b")


def normalize(text: str) -> list[str]:
    t = _OPEN_POINT.sub(" ", _PATH.sub(" ", _ITEM_ID.sub(" ", str(text or ""))))
    return [w for w in re.findall(r"[a-z0-9_]+", t.lower()) if len(w) > 1 and w not in _STOP]


def requirement_ids(text: str) -> set[str]:
    from ..lrtx.visit import _named_swrs  # the CAPA-108 SWR extraction (ranges expanded)

    return set(_named_swrs(str(text or "")))


def compare(a: str, b: str) -> dict:
    """The measures behind `same_finding` (recorded as evidence where a decision is made)."""
    na, nb = normalize(a), normalize(b)
    seq = difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio() if na or nb else 1.0
    sa, sb = set(na), set(nb)
    dice = 2 * len(sa & sb) / (len(sa) + len(sb)) if sa or sb else 1.0
    ia, ib = requirement_ids(a), requirement_ids(b)
    located = not ia or not ib or bool(ia & ib)
    same = seq >= NEAR_VERBATIM or (located and dice >= SAME_DEFECT)
    return {"same": same, "sequence": round(seq, 3), "dice": round(dice, 3), "location_compatible": located}


def same_finding(a: str, b: str) -> bool:
    return compare(a, b)["same"]


def item_findings(rec: dict, item: str) -> list[str]:
    """The full finding texts an inspection record holds for one checklist item: the published item findings, else
    the record's compact per-finding details (older records and fixtures)."""
    v = (rec.get("items") or {}).get(item)
    full = v.get("findings") if isinstance(v, dict) else None
    if isinstance(full, list) and full and all(isinstance(t, str) for t in full):
        return list(full)
    return [str(f.get("detail") or "") for f in rec.get("findings") or []
            if isinstance(f, dict) and (f.get("id") or f.get("item")) == item and f.get("detail")]


def persisting(rounds: list[list[str]]) -> list[str]:
    """The findings of the LAST round that continue one finding through every round (oldest first): each round's
    finding is the same finding as one persisting from the round before. A round without finding text cannot show a
    different finding and carries the persisting set unchanged (the item-only rule, fail closed); all rounds without
    text persist as [""]."""
    alive: list[str] | None = None
    for texts in rounds:
        texts = [t for t in texts if str(t or "").strip()]
        if not texts:
            continue
        alive = list(texts) if alive is None else [t for t in texts if any(same_finding(p, t) for p in alive)]
        if not alive:
            return []
    return alive if alive is not None else [""]
