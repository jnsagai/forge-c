"""DA-T057 / DA-FR-057: the owner's end-of-run review disposition of a registered gap or inspection finding.

    python -m forge_factory.offline.disposition sign <record.json> --key <owner key or .pub with --agent>   (owner only)
    python -m forge_factory.offline.disposition route <dispositions dir> --bundle <export.zip> --out <intake.jsonl>

A disposition (contracts/review-disposition.schema.json) is bound to one export bundle by its sha256 and names one
subject of one exported run. It counts only when ALL hold: schema valid; detached OpenSSH signature by the approver in
namespace `forge-review-disposition` (distinct from AFO authorizations, so neither signature can stand in for the other);
the bundle is intact and is the one named; the run and the subject exist in it. Routing appends verified dispositions
to the learning-set intake once each, and refuses any whose work order belongs to a frozen held-out set. Nothing here
writes to a bundle or a package, and the rationale is owner data, never an instruction to a model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..common import REPO_ROOT, canonical_json
from . import export as X

NAMESPACE = "forge-review-disposition"
SCHEMA = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/review-disposition.schema.json"
TESTSET = REPO_ROOT / "evidence/v0.4/runs/F011-T046/testset.json"


@dataclass(frozen=True)
class Decision:
    ok: bool
    code: str
    reason: str = ""
    disposition_id: str | None = None


def message(rec: dict) -> bytes:
    return canonical_json({k: v for k, v in rec.items() if k != "signature_ref"})


def schema_errors(rec: dict) -> list[str]:
    import jsonschema

    v = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()), format_checker=jsonschema.FormatChecker())
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:160] for e in v.iter_errors(rec)]


def heldout_workorders(testset: Path = TESTSET) -> set[str]:
    """Work orders of the frozen F011-T046 held-out set (the calibration subset is a part of it)."""
    return {s["workorder"] for s in json.loads(testset.read_text())["selected"]} if testset.is_file() else set()


def _mentions(o, ref: str) -> bool:
    if isinstance(o, dict):
        return ref in o or any(_mentions(v, ref) for v in o.values())
    if isinstance(o, list):
        return any(_mentions(v, ref) for v in o)
    return o == ref


def _subject_found(zf: zipfile.ZipFile, run_key: str, subject: dict) -> bool:
    ph = subject["phase"]
    where = [f".forge-run/advisory/{ph}.jsonl"] if subject["kind"] == "GAP" else \
        [f".forge-run/lrtx/{ph}/", f"inspection/{ph}/"]
    for n in zf.namelist():
        rel = n.removeprefix(f"runs/{run_key}/")
        if rel == n or not any(rel == w or (w.endswith("/") and rel.startswith(w)) for w in where):
            continue
        text = zf.read(n).decode()
        docs = [json.loads(ln) for ln in text.splitlines() if ln.strip()] if n.endswith(".jsonl") else [json.loads(text)]
        if any(_mentions(d, subject["ref"]) for d in docs):
            return True
    return False


def verify(rec: dict, *, base: Path, allowed_signers: Path, bundle: Path) -> Decision:
    did = rec.get("disposition_id") if isinstance(rec, dict) else None
    errs = schema_errors(rec) if isinstance(rec, dict) else ["<root>: not an object"]
    if errs:
        return Decision(False, "DSP_SCHEMA_INVALID", errs[0], did)
    sig = (base / rec["signature_ref"]).resolve()
    if not sig.is_file() or not allowed_signers.is_file() or subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers), "-I", rec["approver"], "-n", NAMESPACE,
             "-s", str(sig)], input=message(rec), capture_output=True, timeout=30).returncode != 0:
        return Decision(False, "DSP_SIGNATURE_INVALID", f"no valid {NAMESPACE} signature by {rec['approver']}", did)
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != rec["export_sha256"]:
        return Decision(False, "DSP_EXPORT_MISMATCH", "the disposition names another export bundle", did)
    issues = X.verify(bundle)
    if issues:
        return Decision(False, "DSP_EXPORT_INVALID", issues[0], did)
    with zipfile.ZipFile(bundle) as zf:
        runs = {r["run_key"]: r for r in json.loads(zf.read("MANIFEST.json"))["runs"]}
        run = runs.get(rec["run_key"])
        if run is None or run["workorder"] != rec["workorder"]:
            return Decision(False, "DSP_RUN_UNKNOWN", rec["run_key"], did)
        if not _subject_found(zf, rec["run_key"], rec["subject"]):
            return Decision(False, "DSP_SUBJECT_UNKNOWN", f"{rec['subject']['kind']} {rec['subject']['ref']}", did)
    return Decision(True, "DSP_OK", "", did)


def route(records: Path, *, bundle: Path, out: Path, allowed_signers: Path, heldout: set[str] | None = None) -> dict:
    """Append every verified, non-held-out disposition to the learning-set intake (once per disposition id)."""
    heldout = heldout_workorders() if heldout is None else heldout
    seen = {json.loads(ln)["disposition_id"] for ln in out.read_text().splitlines() if ln.strip()} \
        if out.is_file() else set()
    decisions = []
    for p in sorted(records.glob("*.json")):
        try:
            rec = json.loads(p.read_text())
        except ValueError:
            decisions.append(Decision(False, "DSP_NOT_JSON", p.name))
            continue
        d = verify(rec, base=records, allowed_signers=allowed_signers, bundle=bundle)
        if d.ok and rec["workorder"] in heldout:
            d = Decision(False, "DSP_HELDOUT_REFUSED", f"{rec['workorder']} is in a frozen held-out set", d.disposition_id)
        if d.ok and d.disposition_id in seen:
            d = Decision(True, "DSP_ALREADY_ROUTED", "", d.disposition_id)
        elif d.ok:
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("a") as f:
                f.write(json.dumps({"disposition_id": rec["disposition_id"], "export_sha256": rec["export_sha256"],
                                    "record_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                    "workorder": rec["workorder"], "subject": rec["subject"],
                                    "verdict": rec["verdict"], "use": "LEARNING_SET_ONLY"}, sort_keys=True) + "\n")
            seen.add(d.disposition_id)
        decisions.append(d)
    return {"routed": sum(d.code == "DSP_OK" for d in decisions),
            "refused": [{"id": d.disposition_id, "code": d.code, "reason": d.reason} for d in decisions if not d.ok]}


def sign(rec_path: Path, key: Path, agent: bool = False) -> Path:
    """Owner CLI: write <record>.sig (with --agent the key file is the public key of a key held in ssh-agent)."""
    rec = json.loads(rec_path.read_text())
    with tempfile.TemporaryDirectory() as td:
        m = Path(td) / "msg"
        m.write_bytes(message(rec))
        subprocess.run(["ssh-keygen", "-Y", "sign", *(["-U"] if agent else []), "-f", str(key), "-n", NAMESPACE,
                        str(m)], check=True, capture_output=True)
        out = rec_path.with_suffix(".sig")
        out.write_bytes((Path(td) / "msg.sig").read_bytes())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.offline.disposition", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign")
    s.add_argument("record", type=Path)
    s.add_argument("--key", type=Path, required=True)
    s.add_argument("--agent", action="store_true")
    r = sub.add_parser("route")
    r.add_argument("records", type=Path)
    r.add_argument("--bundle", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--allowed-signers", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "sign":
        print(sign(a.record, a.key, a.agent))
        return 0
    res = route(a.records, bundle=a.bundle, out=a.out, allowed_signers=a.allowed_signers)
    print(json.dumps(res))
    return 1 if res["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
