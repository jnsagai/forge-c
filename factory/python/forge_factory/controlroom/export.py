"""Export (CR-T037, FR-023): the data behind a Control Room view as JSON (as served) or CSV (one row per item,
with its evidence references). Pure transformation of the read-only projections."""
from __future__ import annotations

import csv
import io
import json


def _rows(view: str, data: dict) -> tuple[list[str], list[dict]]:
    if view == "floor":
        cols = ["work_order", "order_id", "station", "status", "reason", "station_since", "elapsed_s", "package_status",
                "authors_model", "inspectors_model"]
        return cols, [{**{k: u.get(k) for k in cols[:7]}, "package_status": (u.get("package") or {}).get("package_status"),
                       "authors_model": (u.get("models") or {}).get("authors", {}).get("model"),
                       "inspectors_model": (u.get("models") or {}).get("inspectors", {}).get("model")}
                      for u in data.get("units", [])]
    if view == "scorecard":
        cols = ["metric_id", "scope", "status", "display", "value", "unit", "sample_count", "reason", "evidence_refs"]
        rows = [{"metric_id": m["metric_id"], "scope": json.dumps(m.get("filters") or {}, sort_keys=True),
                 "status": m["status"], "display": m["display"], "value": m["value"], "unit": m["unit"],
                 "sample_count": m["sample_count"], "reason": m.get("reason"),
                 "evidence_refs": " ".join(m.get("evidence_refs") or m.get("source_event_refs") or [])}
                for m in data.get("kpis", [])]
        rows += [{"metric_id": f"COUNT:{k}", "scope": "", "status": "MEASURED", "display": "VALUE", "value": v["value"],
                  "unit": "count", "sample_count": v["n"], "reason": None, "evidence_refs": " ".join(v["evidence"])}
                 for k, v in (data.get("counts") or {}).items()]
        return cols, rows
    if view == "quality":
        cols = ["station", "kind", "reason_code", "count", "cumulative_share", "refs"]
        return cols, [{**{k: p[k] for k in cols[:5]},
                       "refs": " ".join(f"{r['work_order']}#L{r['line']}" for r in p.get("refs", []))}
                      for p in data.get("pareto", [])]
    if view == "usage":
        cols = ["work_order", "node", "station", "role", "model", "provider", "basis", "tokens_new", "cache_read"]
        return cols, [{k: r.get(k) for k in cols} for r in data.get("records", [])]
    raise ValueError(f"BAD_VIEW:{view}")


def render(view: str, data: dict, fmt: str) -> tuple[str, str]:
    """-> (body, media type)."""
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=1, default=str), "application/json"
    cols, rows = _rows(view, data)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    return buf.getvalue(), "text/csv"
