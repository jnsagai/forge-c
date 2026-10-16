"""CRE-T017..T023 on real history: CAPA records for the loopback defects analysed in ADR-0008 (r72-r76).

Each CAPA iteration = one frozen reproducer (tests/reliability/reproducers/manifest.yaml) with the real pre-fix and
fix revisions. The driver is idempotent and evidence-driven: the runner executes every reproducer on the baseline,
candidate and current revisions; the registry advances only through guarded transitions; effectiveness is evaluated
on the real failure registry and attempt exposures. A recurrence reopens the CAPA; the next iteration re-triages it.
"""
from __future__ import annotations

from ..common import REPO_ROOT
from . import reproduce as RR
from .capa import CapaError, CapaRegistry
from .observe import attempt_exposures
from .policy import Policy
from .store import CREStore

# capa_id -> ordered iterations (reproducer ids); the grouping is CAPA data (ADR-0008 r72..r76), not oracle data
HISTORICAL_CAPAS: dict[str, list[str]] = {
    "CAPA-001": ["RPR-001", "RPR-003"],  # TEST_CHANGED_AFTER_FAIL: declaration coverage (r72), tool-time notice (r74)
    "CAPA-002": ["RPR-002", "RPR-004"],  # DEFECT_TEST_CHANGED: no-op fix (r73), extended cited test (r75)
    "CAPA-003": ["RPR-005"],             # blind host-test debugging -> rework budget exhausted (r74)
}


def _incidents(store: CREStore, rep: dict) -> tuple[list[str], list[str]]:
    obs = [o for o in store.observations() if o["error_code"] in rep["error_codes"]
           and o["operation"] in rep["operations"] and o["disposition"] == "ACTIVE"]
    origin = [o for o in obs if rep["observed_in"] in o["attempt_id"]] or obs
    return sorted({o["obs_id"] for o in origin})[:20], sorted({o["fingerprint"] for o in obs})


def run_historical(store: CREStore, policy: Policy, lessons=None, head: str = "HEAD", log=print) -> list[dict]:
    from ..knowledge.store import LessonStore

    reps, issues = RR.load_manifest()
    if issues:
        raise CapaError(f"MANIFEST_NOT_FROZEN:{issues}")
    reg = CapaRegistry(store, policy)
    reg.lessons = lessons or LessonStore(incidents=reg.lesson_source())
    lessons = reg.lessons
    exposures = attempt_exposures()
    out = []
    with RR.WorktreePool(REPO_ROOT) as pool:
        for capa_id, iterations in HISTORICAL_CAPAS.items():
            for i, rid in enumerate(iterations):
                rep = reps[rid]
                inc, fps = _incidents(store, rep)
                rec = reg.get(capa_id)
                if rec is None:
                    rec = reg.open(capa_id, inc or [f"{rep['observed_in']}:{rid}"], fps,
                                   f"significant recurring failure ({rep['observed_in']}); {len(inc)} observations")
                done = rid in reg.links(capa_id, "REPRODUCER_DONE")
                if done:
                    continue
                if rec["state"] == "OPEN" or (rec["state"] in ("REOPENED", "UNRESOLVED") and i > 0):
                    rec = reg.triage(capa_id, rep["root_cause"], rid, source="RULE:frozen-manifest")
                elif rec["state"] != "REPRODUCER_PENDING":
                    log(f"  {capa_id} {rid}: skipped (state {rec['state']}, iteration {i})")
                    break
                base = RR.run(store, policy, rid, rep["baseline_revision"], "BASELINE", pool, reps)
                cand = RR.run(store, policy, rid, rep["fix_revision"], "CANDIDATE", pool, reps)
                rec = reg.verify_cause(capa_id, base, cand)
                log(f"  {capa_id} {rid}: baseline {base['verdict']} candidate {cand['verdict']} -> {rec['state']}")
                if rec["state"] != "CAUSE_VERIFIED":
                    break
                reg.register_fix(capa_id)
                regr = RR.run(store, policy, rid, head, "REGRESSION", pool, reps)
                rec = reg.register_prevention(capa_id, regr)
                if rec["state"] == "EFFECTIVENESS_OBSERVING":
                    les = reg.propose_lesson(capa_id, lessons, rep["symptom_signature"], rep["remedy"])
                    log(f"  {capa_id} {rid}: lesson {les['lesson_id']} {les['state']}")
                reg.link(capa_id, "REPRODUCER_DONE", rid)
                rec = reg.evaluate_effectiveness(capa_id, exposures, store.observations(), rep["error_codes"],
                                                 rep["operations"])
                log(f"  {capa_id} {rid}: effectiveness -> {rec['state']}")
                if rec["state"] != "REOPENED":
                    break
            rec = reg.must(capa_id)
            if rec["state"] in ("EFFECTIVENESS_OBSERVING", "EFFECTIVE"):  # periodic re-evaluation of the latest fix
                last = reps[[r for r in iterations if r in reg.links(capa_id, "REPRODUCER_DONE")][-1]]
                rec = reg.evaluate_effectiveness(capa_id, exposures, store.observations(), last["error_codes"],
                                                 last["operations"])
            out.append(rec)
    return out


def main(argv: list[str] | None = None) -> int:
    from .policy import load

    pol = load()
    recs = run_historical(CREStore(), pol)
    for r in recs:
        print(f"{r['capa_id']} {r['state']} root_cause={r['root_cause_status']} reproducer={r['reproducer_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
