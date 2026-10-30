"""Feature 016 slice F (OB-T024, OB-T025): the owner's approval of an onboarding package.

`summary` writes the review page (onboarding/summary.md) and an approval template prefilled with the package hash,
the CONFLICT facts, the test-environment assumptions and the non-blocking gaps. The owner fills it, saves it as
onboarding/approval.json and signs it in their own terminal:

    ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n forge-onboarding-approval onboarding/approval.json

`verify` accepts it only when: the schema is valid; the signature verifies for the `decided_by` principal in the
factory's allowed-signers file (the AFO one); the package hash is the current one; every CONFLICT has a resolution,
every assumption a confirmed value and every non-blocking gap is listed as accepted. The factory never signs. A
re-derivation with any changed input voids an earlier approval (moved to onboarding/void/ with the reason)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, utc_now
from . import facts as F

NAMESPACE = "forge-onboarding-approval"
ALLOWED_SIGNERS = REPO_ROOT / "config/factory/afo-allowed-signers"
CONTRACT = REPO_ROOT / "specs/016-peripheral-onboarding/contracts/onboarding-approval.schema.json"
APPROVAL = "onboarding/approval.json"
TEMPLATE = "onboarding/approval.template.json"
SUMMARY = "onboarding/summary.md"


def _fmt(v) -> str:
    s = json.dumps(v, sort_keys=True) if not isinstance(v, str) else v
    return s if len(s) <= 90 else s[:87] + "..."


def _src(s: dict) -> str:
    where = s["ref"] + (f":{s['line']}" if s.get("line") else "") + (f" p.{s['page']}" if s.get("page") else "")
    return where + (f" = {_fmt(s['value'])}" if "value" in s and s["value"] is not None else "")


def template(pkg: dict) -> dict:
    return {"schema": "forge-c/onboarding-approval/0.1", "approval_id": "OA-YYYY-MM-DD-01",
            "work_order": pkg["work_order"], "package_sha256": pkg["sha256"], "decision": "APPROVED",
            "conflict_resolutions": [{"fact": f["name"], "chosen_value": None, "reason": ""}
                                     for f in pkg["facts"] if f["status"] == "CONFLICT"],
            "assumption_confirmations": [{"id": a["id"], "value": a.get("proposed_value")}
                                         for a in pkg["assumptions"]],
            "accepted_gaps": [g["id"] for g in pkg["gaps"] if not g["blocks_approval"]],
            "decided_by": "<your allowed-signers principal>", "decided_on": "YYYY-MM-DD"}


def summary(root: Path) -> Path:
    """The owner review page for the package under `root` (state/workorders/<WO>)."""
    root = Path(root)
    pkg = F.read_package(root)
    if pkg is None:
        raise FileNotFoundError(F.PACKAGE)
    lines = [f"# Onboarding package {pkg['work_order']}", "",
             f"Package `{pkg['sha256']}` · status **{pkg['status']}** · driver style {pkg['driver_style']} · "
             f"factory {pkg['factory_revision']}", "",
             "Facts were derived by the factory without any model call. Each one names its source; NOT_DERIVED and "
             "CONFLICT facts need your answer. Approving accepts these facts and assumptions as the basis of the "
             "SWE.1-SWE.6 work; it is not a safety approval.", "", "## Facts", "",
             "| Fact | Status | Value | Sources |", "|---|---|---|---|"]
    for f in pkg["facts"]:
        v = f"{len(f['value'])} registers" if f["name"] == "register_index" and f["value"] else _fmt(f["value"])
        srcs = "<br>".join(_src(s) for s in f["sources"][:4]) + (" …" if len(f["sources"]) > 4 else "")
        q = f"<br>**Question:** {f['owner_question']}" if f.get("owner_question") else ""
        lines.append(f"| {f['name']} | {f['status']} | {v.replace('|', '/')} | {srcs}{q} |")
    lines += ["", "## Authored items", ""]
    lines += [f"- {a['id']}: {a['status']} (gate {a['gate']['verdict']}, inspection {a['inspection']['verdict']}); "
              f"limits: {'; '.join(a['limits']) or 'none'}" for a in pkg["authored"]] or ["- none"]
    lines += ["", "## Test-environment assumptions (your value is required)", ""]
    lines += [f"- **{a['id']}** `{a['symbol']}`: {a['reason']}. Affects: {', '.join(a['affects'])}."
              + (f" Proposed by the inputs: {a['proposed_value']}." if a.get("proposed_value") is not None else
                 " The inputs state no value.") for a in pkg["assumptions"]] or ["- none"]
    lines += ["", "## Gaps", ""]
    lines += [f"- {g['id']} {g['kind']} `{g['ref']}`{' (blocks approval)' if g['blocks_approval'] else ''}: "
              f"{g['effect']}" for g in pkg["gaps"]] or ["- none"]
    lines += ["", "## How to approve", "",
              f"1. Copy `{TEMPLATE}` to `{APPROVAL}` and fill it: a resolution for every CONFLICT, a value for "
              "every assumption, your principal in `decided_by`, the date, and an id `OA-YYYY-MM-DD-nn`. Remove a "
              "gap from `accepted_gaps` only if you reject the package (then set `decision` REJECTED with a reason).",
              "2. Sign it in your own terminal:", "",
              f"       ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n {NAMESPACE} {root / APPROVAL}", "",
              f"3. The factory verifies it (`python -m forge_factory.onboarding verify {pkg['work_order']}`).", ""]
    (root / SUMMARY).write_text("\n".join(lines))
    (root / TEMPLATE).write_text(pretty_json(template(pkg)))
    return root / SUMMARY


def _schema_errors(a: dict) -> list[str]:
    import jsonschema

    v = jsonschema.Draft202012Validator(json.loads(CONTRACT.read_text()), format_checker=jsonschema.FormatChecker())
    return [f"{'/'.join(map(str, e.path)) or '-'}:{e.message[:120]}" for e in v.iter_errors(a)]


def signature_valid(path: Path, principal: str, allowed_signers: Path) -> bool:
    sig = Path(f"{path}.sig")
    if not sig.is_file() or not allowed_signers.is_file():
        return False
    r = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers), "-I", principal, "-n", NAMESPACE,
                        "-s", str(sig)], input=path.read_bytes(), capture_output=True, timeout=30)
    return r.returncode == 0


def verify(root: Path, allowed_signers: Path | None = None) -> dict:
    """{code, reason, approval} with code APPROVAL_OK | APPROVAL_MISSING | APPROVAL_SCHEMA | APPROVAL_BAD_SIGNATURE |
    APPROVAL_STALE | APPROVAL_INCOMPLETE:<what> | APPROVAL_REJECTED."""
    root = Path(root)
    pkg = F.read_package(root)
    p = root / APPROVAL
    if pkg is None or not p.is_file():
        return {"code": "APPROVAL_MISSING", "reason": "no onboarding package or no approval.json", "approval": None}
    try:
        a = json.loads(p.read_text())
    except ValueError as e:
        return {"code": "APPROVAL_SCHEMA", "reason": str(e)[:160], "approval": None}
    errs = _schema_errors(a)
    if errs:
        return {"code": "APPROVAL_SCHEMA", "reason": errs[0], "approval": a}
    if not signature_valid(p, a["decided_by"], allowed_signers or ALLOWED_SIGNERS):
        return {"code": "APPROVAL_BAD_SIGNATURE", "reason": f"no valid {NAMESPACE} signature by {a['decided_by']}",
                "approval": a}
    if a["work_order"] != pkg["work_order"] or a["package_sha256"] != pkg["sha256"] or \
            F.canonical_hash(pkg) != pkg["sha256"]:
        return {"code": "APPROVAL_STALE", "reason": "the approval names another package hash", "approval": a}
    try:
        from .authoring import artifact_paths

        artifact_paths(pkg)
    except (OSError, ValueError, KeyError) as exc:
        return {"code": "APPROVAL_STALE", "reason": str(exc)[:160], "approval": a}
    if a["decision"] == "REJECTED":
        return {"code": "APPROVAL_REJECTED", "reason": a.get("reason", ""), "approval": a}
    conflicts = {f["name"] for f in pkg["facts"] if f["status"] == "CONFLICT"}
    resolved = {r["fact"] for r in a["conflict_resolutions"] if r.get("chosen_value") is not None}
    if conflicts - resolved:
        return {"code": "APPROVAL_INCOMPLETE:conflict", "reason": ",".join(sorted(conflicts - resolved)), "approval": a}
    asm = {x["id"] for x in pkg["assumptions"]}
    conf = {c["id"] for c in a["assumption_confirmations"] if c.get("value") is not None}
    if asm - conf:
        return {"code": "APPROVAL_INCOMPLETE:assumption", "reason": ",".join(sorted(asm - conf)), "approval": a}
    blocking = {g["id"] for g in pkg["gaps"] if g["blocks_approval"] and g["kind"] not in
                ("CONFLICT", "ASSUMPTION_UNCONFIRMED")}
    if blocking:
        return {"code": "APPROVAL_INCOMPLETE:blocking_gap", "reason": ",".join(sorted(blocking)), "approval": a}
    open_gaps = {g["id"] for g in pkg["gaps"] if not g["blocks_approval"]} - set(a["accepted_gaps"])
    if open_gaps:
        return {"code": "APPROVAL_INCOMPLETE:gap_not_accepted", "reason": ",".join(sorted(open_gaps)), "approval": a}
    return {"code": "APPROVAL_OK", "reason": pkg["sha256"], "approval": a}


def invalidate(root: Path, reason: str) -> bool:
    """OB-T025: move an approval that no longer matches the package aside, with the reason (never deleted)."""
    root = Path(root)
    p = root / APPROVAL
    if not p.is_file():
        return False
    void = root / "onboarding/void" / utc_now().replace(":", "")
    void.mkdir(parents=True)
    for f in (p, Path(f"{p}.sig")):
        if f.is_file():
            shutil.move(str(f), void / f.name)
    (void / "reason.txt").write_text(reason + "\n")
    return True
