"""Statistical process control for the Control Room (CR-T023; research R5). Method id: spc-v1.

* p-chart for first-pass yield: subgroup i has passes x_i of n_i runs; p-bar = sum x / sum n; limits
  p-bar +- 3*sqrt(p-bar*(1-p-bar)/n_i) clipped to [0, 1] (variable limits).
* I-MR chart for durations: x-bar +- 2.66*MR-bar, MR-bar = mean |x_i - x_(i-1)|; the lower limit is clipped at 0 (a
  negative duration is impossible) and the clipping is reported.
* Western Electric rules, configurable: WE1 one point beyond a limit; WE2 nine in a row on one side of the centre;
  WE3 six in a row steadily increasing or decreasing.
Below the configured minimum sample the chart is INSUFFICIENT_DATA and no limits are drawn.
"""
from __future__ import annotations

import math

METHOD = "spc-v1"


def _rules(values: list[float], center: float, ucl: list[float], lcl: list[float], rules: list[str]) -> list[dict]:
    out = []
    if "WE1" in rules:
        out += [{"rule": "WE1", "point_index": i} for i, v in enumerate(values) if v > ucl[i] or v < lcl[i]]
    if "WE2" in rules:
        run, side = 0, 0
        for i, v in enumerate(values):
            s = (v > center) - (v < center)
            run = run + 1 if s and s == side else (1 if s else 0)
            side = s
            if run == 9:
                out.append({"rule": "WE2", "point_index": i})
    if "WE3" in rules:
        run, d = 1, 0
        for i in range(1, len(values)):
            s = (values[i] > values[i - 1]) - (values[i] < values[i - 1])
            run = run + 1 if s and s == d else (2 if s else 1)
            d = s
            if run == 6:
                out.append({"rule": "WE3", "point_index": i})
    return sorted(out, key=lambda x: (x["point_index"], x["rule"]))


def p_chart(groups: list[dict], spc: dict) -> dict:
    """groups: [{t, passes, n, units}] in time order (n > 0)."""
    groups = [g for g in groups if g["n"] > 0]
    pts = [{"t": g["t"], "value": g["passes"] / g["n"], "n": g["n"], "units": g.get("units", [])} for g in groups]
    total = sum(g["n"] for g in groups)
    base = {"method": f"{METHOD}:p-chart", "points": pts}
    if len(groups) < spc["min_subgroups"] or total < spc["min_n"]:
        return {**base, "status": "INSUFFICIENT_DATA", "n": total, "subgroups": len(groups),
                "minimum": {"subgroups": spc["min_subgroups"], "n": spc["min_n"]},
                "center": None, "ucl": None, "lcl": None, "violations": []}
    p = sum(g["passes"] for g in groups) / total
    ucl = [min(1.0, p + 3 * math.sqrt(p * (1 - p) / g["n"])) for g in groups]
    lcl = [max(0.0, p - 3 * math.sqrt(p * (1 - p) / g["n"])) for g in groups]
    vals = [x["value"] for x in pts]
    return {**base, "status": "OK", "n": total, "subgroups": len(groups), "center": round(p, 6),
            "ucl": [round(x, 6) for x in ucl], "lcl": [round(x, 6) for x in lcl],
            "violations": _rules(vals, p, ucl, lcl, spc["rules"])}


def i_mr(points: list[dict], spc: dict) -> dict:
    """points: [{t, value, units}] in time order."""
    base = {"method": f"{METHOD}:i-mr", "points": [{**x, "n": 1} for x in points]}
    if len(points) < spc["min_points"]:
        return {**base, "status": "INSUFFICIENT_DATA", "n": len(points), "minimum": {"points": spc["min_points"]},
                "center": None, "ucl": None, "lcl": None, "violations": []}
    xs = [x["value"] for x in points]
    xbar = sum(xs) / len(xs)
    mr = sum(abs(xs[i] - xs[i - 1]) for i in range(1, len(xs))) / (len(xs) - 1)
    ucl, lcl_raw = xbar + 2.66 * mr, xbar - 2.66 * mr
    lcl = max(0.0, lcl_raw)
    return {**base, "status": "OK", "n": len(xs), "center": round(xbar, 3), "ucl": round(ucl, 3), "lcl": round(lcl, 3),
            "lcl_clipped_at_zero": lcl_raw < 0, "mr_bar": round(mr, 3),
            "violations": _rules(xs, xbar, [ucl] * len(xs), [lcl] * len(xs), spc["rules"])}
