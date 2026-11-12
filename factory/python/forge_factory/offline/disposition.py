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
from . import feedback as F

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


def heldout_workorders(testset: Path | None = None) -> set[str]:
    """Active frozen members after the recorded post-calibration learning transfers."""
    from .review_sets import active_workorders

    if testset is not None:
        return {s["workorder"] for s in json.loads(testset.read_text())["selected"]}
    return active_workorders(REPO_ROOT)


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
    sig = base / rec["signature_ref"]
    if sig.is_symlink() or not sig.is_file() or not allowed_signers.is_file() or subprocess.run(
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


def route(records: Path, *, bundle: Path, out: Path, allowed_signers: Path, heldout: set[str] | None = None,
          registry=None) -> dict:
    """Verify, archive and open corrective CAPAs; JSONL is an idempotent intake projection."""
    import os

    try:
        excluded = heldout_workorders() | (heldout or set())  # extra exclusions never override frozen membership
    except (OSError, ValueError, TypeError, KeyError):
        return {"routed": 0, "refused": [{"id": None, "code": "DSP_SET_REGISTRY_INVALID",
                                         "reason": "set registration unavailable or inconsistent"}], "capa_ids": []}
    paths = sorted(records.glob("*.json"))
    if len(paths) > 128:
        return {"routed": 0, "refused": [{"id": None, "code": "DSP_BATCH_TOO_LARGE", "reason": "limit 128"}],
                "capa_ids": []}
    reg = registry or F.registry()
    decisions, capas = [], set()
    with F.intake_lock(reg):
        seen = {r["disposition_id"]: r for r in (json.loads(ln) for ln in out.read_text().splitlines() if ln.strip())} \
            if out.is_file() else {}
        for p in paths:
            try:
                raw = p.read_bytes()
                rec = json.loads(raw)
                if not isinstance(rec, dict) or schema_errors(rec):
                    decisions.append(Decision(False, "DSP_SCHEMA_INVALID", p.name))
                    continue
                raw_sha = hashlib.sha256(raw).hexdigest()
                review_sha = hashlib.sha256(message(rec)).hexdigest()
                sig = records / str(rec.get("signature_ref", "")) if isinstance(rec, dict) else records
                signature = sig.read_bytes() if sig.is_file() and not sig.is_symlink() else b""
                signers = allowed_signers.read_bytes() if allowed_signers.is_file() else b""
                exported = bundle.read_bytes()
                d = verify(rec, base=records, allowed_signers=allowed_signers, bundle=bundle)
                if d.ok and rec["workorder"] in excluded:
                    d = Decision(False, "DSP_HELDOUT_REFUSED", "work order is still held out", d.disposition_id)
                if d.ok:
                    if sig.read_bytes() != signature or allowed_signers.read_bytes() != signers:
                        raise F.Refused("DSP_AUTHORITY_CHANGED")
                    prior = seen.get(d.disposition_id)
                    if prior and prior.get("review_sha256", prior.get("record_sha256")) != (
                            review_sha if "review_sha256" in prior else raw_sha):
                        raise F.Refused("DSP_ID_CONFLICT")
                    cid = F.ingest(reg, rec, review_sha256=review_sha, signature=signature, signers=signers,
                                   bundle=exported)
                    if cid:
                        capas.add(cid)
                    if prior:
                        d = Decision(True, "DSP_ALREADY_ROUTED", "", d.disposition_id)
                    else:
                        row = {"disposition_id": rec["disposition_id"], "export_sha256": rec["export_sha256"],
                               "record_sha256": raw_sha, "review_sha256": review_sha,
                               "workorder": rec["workorder"], "subject": rec["subject"],
                               "verdict": rec["verdict"], "use": "LEARNING_SET_ONLY", "capa_id": cid}
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with out.open("a") as stream:
                            stream.write(json.dumps(row, sort_keys=True) + "\n")
                            stream.flush()
                            os.fsync(stream.fileno())
                        seen[d.disposition_id] = row
            except F.Refused as exc:
                d = Decision(False, exc.code, "verified intake refused", rec.get("disposition_id"))
            except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile):
                d = Decision(False, "DSP_INPUT_INVALID", p.name)
            decisions.append(d)
    return {"routed": sum(d.code == "DSP_OK" for d in decisions),
            "refused": [{"id": d.disposition_id, "code": d.code, "reason": d.reason} for d in decisions if not d.ok],
            "capa_ids": sorted(capas)}


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
    learn = sub.add_parser("publish-lesson", help="curate a frozen remedy after causal, prevention and CRE proof")
    learn.add_argument("--capa", required=True)
    learn.add_argument("--workspace", type=Path, required=True)
    learn.add_argument("--role", required=True)
    qualify = sub.add_parser("qualify-capa", help="bind an existing independent FIX decision and its runner evidence")
    qualify.add_argument("--capa", required=True)
    qualify.add_argument("--decision", required=True)
    qualify.add_argument("--reproducer")
    qualify.add_argument("--staged-manifest", type=Path)
    qualify.add_argument("--lesson-description", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "sign":
        print(sign(a.record, a.key, a.agent))
        return 0
    if a.cmd in ("publish-lesson", "qualify-capa"):
        try:
            reg = F.registry()
            with F.intake_lock(reg):
                if a.cmd == "publish-lesson":
                    res = F.publish(reg, a.capa, workspace=a.workspace, role=a.role)
                else:
                    description = json.loads(a.lesson_description.read_text()) if a.lesson_description else None
                    res = F.qualify(reg, a.capa, a.decision, reproducer=a.reproducer,
                                    staged_manifest=a.staged_manifest, description=description)
        except (F.Refused, ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            print(json.dumps({"status": "REFUSED", "code": getattr(exc, "code", "DSP_CAPA_INVALID")}))
            return 1
        print(json.dumps(res))
        return 0 if res["state"] in ("VALIDATED", "PREVENTION_TESTED", "EFFECTIVENESS_OBSERVING", "EFFECTIVE") else 1
    res = route(a.records, bundle=a.bundle, out=a.out, allowed_signers=a.allowed_signers)
    print(json.dumps(res))
    return 1 if res["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
