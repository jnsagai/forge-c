"""CRE-T037 — reliability evidence bundle in every READY or BLOCKED package (existing deterministic finalizer).

Files under operations/reliability/ (plan §11): baseline-manifest, incident-capa-ledger, reliability-kpi-snapshot,
benchmark-report, fault-injection-report, promotion-decisions, spc-analysis, lessons-ledger-index,
readiness-assessment, plus absence-explanations and a SHA-256 index. The bundle never changes the package status
(computed before it is added), never claims approval, and records what is missing instead of omitting it.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, sha256_bytes, state_dir, utc_now

PREFIX = "operations/reliability"
SCOPE = "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def build_bundle(ws: Path, release_status: str) -> dict[str, bytes]:
    from ..events.redact import redact_text
    from .capa import CapaRegistry
    from .metrics import compute, p_chart
    from .observe import attempt_context
    from .policy import load
    from .store import CREStore
    from .taxonomy import CLASSIFIER_VERSION

    pol = load()
    files: dict[str, bytes] = {}
    absent: list[dict] = []
    store = CREStore()
    ctx = attempt_context(ws) or {"attempt_id": ws.parent.name, "order_id": None, "factory_revision": {}}
    base = _read(REPO_ROOT / "evidence/cre/baseline/baseline-latest.json") or {}
    inv = _read(REPO_ROOT / "evidence/cre/baseline/source-inventory.json") or {}
    files["baseline-manifest.json"] = pretty_json({
        "release_status": release_status, "scope": SCOPE, "policy_sha256": pol.sha256, "mode": pol.mode,
        "classifier_version": CLASSIFIER_VERSION, "cre_schema_version": store.version(),
        "attempt": ctx["attempt_id"], "order": ctx.get("order_id"), "factory_revision": ctx.get("factory_revision"),
        "tool_versions": base.get("tool_versions", "UNKNOWN"), "baseline_test_record": base.get("git_head", "UNKNOWN"),
        "source_inventory": {"git_head": inv.get("git_head"), "counts": inv.get("counts")}}).encode()
    obs = [o for o in store.observations() if o["attempt_id"] == ctx["attempt_id"]
           or (ctx.get("order_id") and o["order_id"] == ctx["order_id"])]
    reg = CapaRegistry(store, pol)
    ledger = [json.dumps({"kind": "observation", **{k: o[k] for k in ("obs_id", "fingerprint", "failure_class",
                                                                        "category", "error_code", "operation",
                                                                        "attempt_id", "ts_utc", "disposition",
                                                                        "source_ref", "evidence_sha256")},
                          "excerpt": redact_text(o["excerpt"])[0]}, sort_keys=True) for o in obs]
    ledger += [json.dumps({"kind": "capa", "record": c, "history": reg.history(c["capa_id"])}, sort_keys=True)
               for c in reg.all()]
    files["incident-capa-ledger.jsonl"] = ("\n".join(ledger) + "\n").encode()
    if not obs:
        absent.append({"item": "observations", "reason": "no CRE observations imported for this attempt yet"})
    try:
        metrics = compute(store, pol)
        files["reliability-kpi-snapshot.json"] = pretty_json(metrics).encode()
    except Exception as exc:  # noqa: BLE001 - recorded as a gap, never a guessed value
        absent.append({"item": "reliability-kpi-snapshot", "reason": f"{type(exc).__name__}: {str(exc)[:160]}"})
    with store.conn() as c:
        bench = [json.loads(r[0]) for r in c.execute("SELECT record FROM cre_benchmark_runs ORDER BY at DESC LIMIT 4")]
        decisions = [r[0] for r in c.execute("SELECT record FROM cre_promotion_decisions ORDER BY at")]
    files["benchmark-report.json"] = pretty_json({"runs": bench, "status": "MEASURED" if bench else "NOT_RUN",
                                                  "suites": ["tests/reliability/benchmark/suite.yaml",
                                                             "tests/reliability/holdout/suite.yaml"]}).encode()
    if not bench:
        absent.append({"item": "benchmark-report", "reason": "no benchmark run recorded in the CRE store"})
    fault = _read(REPO_ROOT / "evidence/cre/faults/fault-injection-latest.json")
    files["fault-injection-report.json"] = pretty_json(fault or {"status": "NOT_RUN"}).encode()
    if fault is None:
        absent.append({"item": "fault-injection-report", "reason": "campaign not executed (CRE-T039)"})
    files["promotion-decisions.jsonl"] = ("\n".join(decisions) + "\n").encode()
    if not decisions:
        absent.append({"item": "promotion-decisions", "reason": "no candidate evaluated in this store"})
    files["spc-analysis.json"] = pretty_json(p_chart(pol, [], None)).encode()
    les_ids = sorted({lid for c in reg.all() for lid in c["lesson_ids"]})
    try:
        from ..knowledge.store import LessonStore

        ls = LessonStore()
        files["lessons-ledger-index.json"] = pretty_json([{"lesson_id": lid, "state": (ls.get(lid) or {}).get("state",
                                                                                                               "UNKNOWN")}
                                                          for lid in les_ids]).encode()
    except Exception as exc:  # noqa: BLE001
        absent.append({"item": "lessons-ledger-index", "reason": f"{type(exc).__name__}"})
    ready = _read(REPO_ROOT / "evidence/cre/readiness-assessment.json")
    files["readiness-assessment.json"] = pretty_json(ready or {
        "readiness": "NOT_DEMONSTRATED", "reason": "readiness not yet assessed (CRE-T042)", "safety_signoff": None,
        "scope": SCOPE}).encode()
    if ready is None:
        absent.append({"item": "readiness-assessment", "reason": "not yet assessed"})
    files["absence-explanations.json"] = pretty_json({"generated_at": utc_now(), "items": absent}).encode()
    files["index.json"] = pretty_json({"scope": SCOPE, "release_status": release_status,
                                       "files": {k: sha256_bytes(v) for k, v in sorted(files.items())}}).encode()
    return files


def bundle_into(ws: Path, stage: Path, release_status: str) -> list[str]:
    """Called by release.finalize; any CRE failure becomes an explicit absence file, never a blocked package."""
    from ..release.finalize import _w

    try:
        files = build_bundle(ws, release_status)
    except Exception as exc:  # noqa: BLE001 - packaging must survive a CRE outage (e.g. store unavailable)
        files = {"absence-explanations.json": pretty_json({"generated_at": utc_now(), "items": [
            {"item": "reliability-bundle", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}]}).encode()}
    for name, data in files.items():
        _w(stage, f"{PREFIX}/{name}", data)
    return sorted(files)


def latest_archive_bundle(run_id: str) -> dict | None:
    import zipfile

    root = state_dir().parent / "archives" / run_id
    zips = sorted(root.glob("*.zip")) if root.is_dir() else []
    if not zips:
        return None
    with zipfile.ZipFile(zips[-1]) as z:
        names = [n for n in z.namelist() if "/reliability/" in n]
        return {"names": names, "index": json.loads(z.read(next(n for n in names if n.endswith("index.json"))))
                if any(n.endswith("index.json") for n in names) else None}
