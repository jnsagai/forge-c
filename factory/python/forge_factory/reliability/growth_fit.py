"""CRE-T053 (CRE-FR-022, plan section 7): OPTIONAL reliability-growth diagnostic - Crow-AMSAA (power-law NHPP) and Duane.

Diagnostic only: the result is never read by promotion, readiness, a gate or a policy (plan: "never auto-promote
based on a fitted trend"). Every report states its observation clock, censoring, assumptions and uncertainty:

* clock      the cumulative number of FINISHED attempts of ONE cohort in start order (discrete, time-terminated at T =
             number of finished attempts); a failure is a finished attempt that did not pass SWE.6. Unfinished attempts
             (no package) are censored: excluded and counted.
* Crow-AMSAA MLE beta_hat = n / sum(ln(T / t_i)), bias-corrected beta_bar = (n - 1) / n * beta_hat (time-terminated),
             lambda = n / T^beta_bar; beta < 1 means a falling failure intensity (growth). Interval for beta from the
             chi-square pivot 2 n beta / beta_hat ~ chi2(2n) (Wilson-Hilferty quantiles, approximate).
* fit check  Cramer-von Mises statistic on u_i = (t_i / T)^beta_bar with a seeded parametric-bootstrap p-value
             (deterministic); the fit is REJECTED for p < 0.10. Laplace trend test (normal approximation) is reported
             as an independent trend check.
* Duane      least squares of ln(N(t)/t) on ln(t) at the failure points; slope = beta - 1, with R^2 (descriptive only).
* minimum    fewer than 5 failures or fewer than 10 finished attempts -> INSUFFICIENT_DATA, no fit reported.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

MIN_FAILURES, MIN_ATTEMPTS, GOF_ALPHA, BOOT = 5, 10, 0.10, 2000
ASSUMPTIONS = [
    "attempts of one cohort are the observation clock; real elapsed time and effort per attempt are ignored",
    "failures follow a power-law non-homogeneous Poisson process in that clock (checked, not assumed, by Cramer-von Mises)",
    "factory revisions, prompts and models changed between attempts; the trend mixes all changes and attributes nothing",
    "attempts are treated as independent; concurrent attempts on one revision are ordered by start time",
    "beta interval uses the failure-count chi-square pivot and Wilson-Hilferty quantiles: approximate",
]


def _z(p: float) -> float:
    """Standard normal quantile (Acklam's rational approximation; |error| < 1.2e-9)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - 0.02425:
        return -_z(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def _chi2(p: float, k: int) -> float:
    """Chi-square quantile, Wilson-Hilferty approximation."""
    return k * (1 - 2 / (9 * k) + _z(p) * math.sqrt(2 / (9 * k))) ** 3


def _beta_hat(times: list[float], T: float) -> float:
    s = sum(math.log(T / t) for t in times)
    return len(times) / s if s > 0 else float("inf")


def _cvm(times: list[float], T: float, beta: float) -> float:
    m = len(times)
    u = sorted((t / T) ** beta for t in times)
    return 1 / (12 * m) + sum((ui - (2 * i - 1) / (2 * m)) ** 2 for i, ui in enumerate(u, 1))


def fit(failure_times: list[float], T: float, conf: float = 0.90, seed: int = 20261019) -> dict:
    """Crow-AMSAA + Duane on failure times in (0, T]."""
    times = sorted(float(t) for t in failure_times)
    n = len(times)
    if n < MIN_FAILURES or T < MIN_ATTEMPTS:
        return {"status": "INSUFFICIENT_DATA", "failures": n, "T": T,
                "reason": f"need >= {MIN_FAILURES} failures and >= {MIN_ATTEMPTS} finished attempts"}
    if any(t <= 0 or t > T for t in times):
        raise ValueError("failure times must lie in (0, T]")
    bh = _beta_hat(times, T)
    if not math.isfinite(bh):
        return {"status": "NOT_COMPUTABLE", "failures": n, "T": T, "reason": "every failure at T"}
    bb = (n - 1) / n * bh
    lam = n / T ** bb
    lo, hi = bh * _chi2((1 - conf) / 2, 2 * n) / (2 * n), bh * _chi2((1 + conf) / 2, 2 * n) / (2 * n)
    c_obs = _cvm(times, T, bb)
    rng = random.Random(seed)  # parametric bootstrap under the fitted power law, conditional on n (deterministic)
    worse = 0
    for _ in range(BOOT):
        sim = sorted(T * rng.random() ** (1 / bb) for _ in range(n))
        sim = [max(s, 1e-9) for s in sim]
        b_sim = (n - 1) / n * _beta_hat(sim, T)
        worse += _cvm(sim, T, b_sim) >= c_obs
    p_gof = (worse + 1) / (BOOT + 1)
    laplace = (sum(times) / n - T / 2) / (T * math.sqrt(1 / (12 * n)))  # < 0: failures earlier = improving
    xs = [math.log(t) for t in times]
    ys = [math.log((i + 1) / t) for i, t in enumerate(times)]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx if sxx else float("nan")
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (my + slope * (x - mx))) ** 2 for x, y in zip(xs, ys, strict=True))
    accepted = p_gof >= GOF_ALPHA
    return {"status": "FIT_ACCEPTED_FOR_DIAGNOSTIC" if accepted else "FIT_REJECTED",
            "failures": n, "T": T,
            "crow_amsaa": {"beta_hat_mle": round(bh, 4), "beta_bias_corrected": round(bb, 4), "lambda": round(lam, 6),
                           f"beta_{int(conf * 100)}pct_interval": [round(lo, 4), round(hi, 4)],
                           "current_failure_intensity_per_attempt": round(lam * bb * T ** (bb - 1), 4)
                           if accepted else None,
                           "reading": ("falling failure intensity (growth)" if hi < 1 else
                                       "rising failure intensity" if lo > 1 else "no trend distinguishable from constant")
                           if accepted else "not interpreted: fit rejected"},
            "goodness_of_fit": {"test": "Cramer-von Mises, parametric bootstrap", "statistic": round(c_obs, 5),
                                "p_value": round(p_gof, 4), "bootstrap_samples": BOOT, "seed": seed,
                                "reject_below": GOF_ALPHA},
            "laplace_trend": {"u": round(laplace, 3), "two_sided_5pct_significant": abs(laplace) > 1.96},
            "duane": {"slope_ln_cum_intensity_vs_ln_t": round(slope, 4), "implied_beta": round(slope + 1, 4),
                      "r_squared": round(1 - ss_res / ss_tot, 4) if ss_tot else None, "use": "descriptive only"}}


def cohort_series(atts: list[dict], cohort_key: str) -> dict:
    """Failure times on the attempt clock for one cohort; unfinished attempts censored."""
    members = [a for a in atts if a["cohort_key"] == cohort_key]
    finished = [a for a in members if a.get("finished")]
    times = [i for i, a in enumerate(finished, 1) if not a["completed"]]
    return {"cohort_key": cohort_key, "finished_attempts": len(finished), "failure_times": times,
            "censored_unfinished": len(members) - len(finished),
            "attempt_ids": [a["attempt_id"] for a in finished]}


def report(atts: list[dict], conf: float = 0.90) -> dict:
    out = []
    for key in sorted({a["cohort_key"] for a in atts}):
        s = cohort_series(atts, key)
        r = fit(s["failure_times"], float(s["finished_attempts"]), conf) if s["finished_attempts"] else \
            {"status": "INSUFFICIENT_DATA", "failures": 0, "T": 0}
        out.append({**{k: v for k, v in s.items() if k != "failure_times"}, "failures": len(s["failure_times"]),
                    "fit": r})
    return {"schema": "forge-c/cre-growth-diagnostic/0.1", "diagnostic_only": True,
            "never_used_for": ["promotion", "readiness", "gates", "policy", "SLO claims"],
            "observation_clock": "cumulative finished attempts per cohort (discrete, time-terminated)",
            "failure_definition": "finished attempt that did not pass SWE.6",
            "assumptions": ASSUMPTIONS, "confidence": conf, "cohorts": out}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from ..common import REPO_ROOT
    from .metrics import attempts

    ap = argparse.ArgumentParser(prog="forge_factory.reliability.growth_fit")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evidence/cre/metrics/growth-diagnostic.json")
    a = ap.parse_args(argv)
    rep = report(attempts())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for c in rep["cohorts"]:
        f = c["fit"]
        ca = f.get("crow_amsaa", {})
        print(f"{c['cohort_key'][:70]:70s} T={c['finished_attempts']:3d} fail={c['failures']:3d} {f['status']:28s} "
              f"beta={ca.get('beta_bias_corrected', '-')} gof_p={f.get('goodness_of_fit', {}).get('p_value', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
