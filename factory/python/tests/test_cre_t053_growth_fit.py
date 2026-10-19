"""CRE-T053 (CRE-FR-022): optional Crow-AMSAA/Duane diagnostic - fit only after a goodness-of-fit check, states clock,
censoring, assumptions and uncertainty, deterministic, and never read by promotion, readiness, gates or policy."""
import random
from pathlib import Path

from forge_factory.reliability import growth_fit as G


def _nhpp(beta: float, n: int, T: float, seed: int) -> list[float]:
    rng = random.Random(seed)
    return sorted(max(1.0, round(T * rng.random() ** (1 / beta))) for _ in range(n))


def test_growth_data_is_read_as_growth_and_constant_rate_is_not():
    grow = G.fit(_nhpp(0.45, 40, 400.0, 1), 400.0)
    assert grow["status"] == "FIT_ACCEPTED_FOR_DIAGNOSTIC", grow
    assert grow["crow_amsaa"]["beta_90pct_interval"][1] < 1 and grow["crow_amsaa"]["reading"].startswith("falling")
    flat = G.fit(_nhpp(1.0, 40, 400.0, 2), 400.0)
    assert flat["status"] == "FIT_ACCEPTED_FOR_DIAGNOSTIC"
    lo, hi = flat["crow_amsaa"]["beta_90pct_interval"]
    assert lo < 1 < hi and flat["crow_amsaa"]["reading"].startswith("no trend")


def test_a_pattern_the_power_law_cannot_describe_is_rejected_not_interpreted():
    mid = [float(t) for t in range(190, 230)]                  # 40 failures packed in the middle of 400 attempts
    r = G.fit(mid, 400.0)
    assert r["status"] == "FIT_REJECTED" and r["goodness_of_fit"]["p_value"] < G.GOF_ALPHA
    assert r["crow_amsaa"]["reading"] == "not interpreted: fit rejected"
    assert r["crow_amsaa"]["current_failure_intensity_per_attempt"] is None


def test_insufficient_data_and_determinism():
    assert G.fit([1.0, 2.0, 3.0], 20.0)["status"] == "INSUFFICIENT_DATA"
    assert G.fit([1.0, 2.0, 3.0, 4.0, 5.0], 6.0)["status"] == "INSUFFICIENT_DATA"
    xs = _nhpp(0.7, 25, 120.0, 3)
    assert G.fit(xs, 120.0) == G.fit(xs, 120.0)


def test_report_states_clock_censoring_and_assumptions():
    atts = [{"attempt_id": f"a{i}", "cohort_key": "c", "finished": "x" if i % 7 else None, "completed": i % 3 == 0}
            for i in range(1, 40)]
    rep = G.report(atts)
    c = rep["cohorts"][0]
    assert rep["diagnostic_only"] and "promotion" in rep["never_used_for"] and rep["assumptions"]
    assert c["censored_unfinished"] == 5 and c["finished_attempts"] == 34 and c["failures"] == 22


def test_no_decision_path_reads_the_diagnostic():
    root = Path(G.__file__).resolve().parents[1]
    users = [p for p in root.rglob("*.py") if "growth_fit" in p.read_text() and p.name != "growth_fit.py"]
    assert users == []
