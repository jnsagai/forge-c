"""Prepare bounded phase examples from verified packages for the existing lesson lane.

Preparation does not promote memory, expose context or establish learning benefit.
The existing independent qualification, curator, retrieval and transfer APIs remain
the only delivery path. No model call, fabricated repair or secondary store.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from ..afo.durable import Refused, digest, immutable_json
from ..common import sha256_file
from ..events.redact import redact_text
from ..inspection.engine import Store
from ..release.finalize import verify_archive
from . import experience
from .context import applicability
from .qualification import historical_holdout_refs
from .store import INJECTION, WEAKENING, LessonStore

ARTIFACTS = {
    "SWE.2": {"software_architecture.md", "architecture_static.puml", "architecture_dynamic.puml"},
    "SWE.3": {"detailed_design.md", "unit_specifications.md"},
    "SWE.4": {"unit_verification_report.md"},
    "SWE.5": {"integration_verification_report.md"},
    "SWE.6": {"software_verification_report.md"},
}


def excerpt(text, section=None):
    """One whole example or Markdown section; never truncate a coherent obligation."""
    if section is not None:
        lines = text.splitlines(keepends=True)
        starts = [i for i, line in enumerate(lines) if line.rstrip() == section]
        if len(starts) != 1 or not re.fullmatch(r"#{1,6} .+", section):
            raise Refused("REFERENCE_SECTION_NOT_UNIQUE")
        start = starts[0]
        level = len(section.split(" ", 1)[0])
        end = next((i for i in range(start + 1, len(lines))
                    if (m := re.match(r"^(#{1,6}) ", lines[i])) and len(m[1]) <= level), len(lines))
        text = "".join(lines[start:end])
    text = text.strip()
    if not text or len(text) > 700:
        raise Refused("REFERENCE_EXCERPT_UNFIT_SELECT_SMALLER_SECTION")
    if redact_text(text)[1] or INJECTION.search(text) or WEAKENING.search(text):
        raise Refused("REFERENCE_UNSAFE_TEXT")
    return text


def prepare(store, workspace, selection):
    """Return an unpromoted v2 ordinary-outcome lesson candidate and provenance.

    Selection is an explicit engineering input, never model/curator authority to
    reclassify a held-out execution. Unknown cohort classification fails closed.
    """
    ws = Path(workspace)
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    phase = selection["phase"]
    if phase not in ARTIFACTS:
        raise Refused("REFERENCE_AUTHOR_PHASE_ONLY_NO_REQUIREMENTS_OR_INSPECTOR")
    role = f"swe{phase[-1]}-author"
    if selection.get("role") != role:
        raise Refused("REFERENCE_AUTHOR_PHASE_ONLY_NO_REQUIREMENTS_OR_INSPECTOR")
    classification = selection.get("classification", {})
    if (man.get("evaluation_holdout") or classification.get("evaluation_holdout") is not False
            or classification.get("intended_use") != "TRAINING_REFERENCE"
            or not classification.get("record_ref")):
        raise Refused("REFERENCE_NON_HOLDOUT_CLASSIFICATION_REQUIRED")
    if historical_holdout_refs(man["work_order"]):
        raise Refused("HELDOUT_ACCEPTANCE_SOURCE_CANNOT_BE_DISTILLED")
    pkg = json.loads((ws / ".forge-run/package.json").read_text())
    archive = Path(pkg["archive"])
    archive_sha = sha256_file(archive)
    if (pkg.get("package_status") != "READY_FOR_OFFLINE_REVIEW" or pkg.get("gap_count") != 0
            or archive_sha != pkg.get("archive_sha256") or archive_sha != selection.get("archive_sha256")
            or verify_archive(archive)["integrity"] != "PASS"):
        raise Refused("REFERENCE_VERIFIED_READY_PACKAGE_REQUIRED")
    if Store(ws).gate(phase)["decision"] != "PASS":
        raise Refused("REFERENCE_CURRENT_INDEPENDENT_PHASE_GATE_REQUIRED")
    rel = selection["artifact"]
    if rel not in {f"workproducts/{phase}/{name}" for name in ARTIFACTS[phase]}:
        raise Refused("REFERENCE_ARTIFACT_OUTSIDE_PHASE_ALLOWLIST")
    artifact = ws / rel
    if artifact.is_symlink() or not artifact.is_file():
        raise Refused("REFERENCE_ARTIFACT_UNRESOLVED")
    raw = artifact.read_bytes()
    baseline = Store(ws).latest_baseline(phase)
    artifact_sha = sha256_file(artifact)
    if baseline["files"].get(rel) != artifact_sha:
        raise Refused("REFERENCE_ARTIFACT_NOT_FROZEN")
    with zipfile.ZipFile(archive) as z:
        if z.read("evidence/" + rel) != raw:
            raise Refused("REFERENCE_ARCHIVED_ARTIFACT_CHANGED")
    text = excerpt(raw.decode(), selection.get("section"))
    scope = selection["applicability"]
    if (scope.get("phases") != [phase] or scope.get("roles") != [role]
            or any(not isinstance(scope.get(k), list) or not scope[k]
                   or any(not isinstance(v, str) or not v for v in scope[k])
                   for k in ("targets", "source_versions"))):
        raise Refused("REFERENCE_EXPLICIT_DESTINATION_SCOPE_REQUIRED")
    execution = (ws / ".forge-run/fabro_run_id").read_text().strip()
    if not execution or execution != selection.get("execution_id"):
        raise Refused("REFERENCE_NATIVE_IDENTITY_CHANGED")
    # Historical held-out classification applies across every observation/revision.
    with store._conn() as c:
        if c.execute("SELECT 1 FROM job_experience WHERE execution_id=? AND "
                     "json_extract(record,'$.cohort.evaluation_holdout')=1", (execution,)).fetchone():
            raise Refused("HELDOUT_ACCEPTANCE_SOURCE_CANNOT_BE_DISTILLED")
    provenance = {
        "work_order": man["work_order"], "execution_id": execution,
        "factory_revision": man.get("factory_revision"), "archive_sha256": archive_sha,
        "artifact": rel, "artifact_sha256": artifact_sha, "excerpt_sha256": digest(text),
        "phase": phase, "baseline_hash": baseline["baseline_hash"],
        "selection_sha256": digest(selection), "classification": classification,
        "source_applicability": applicability(ws),
    }
    evidence_refs = [f"archive:sha256:{archive_sha}", f"artifact:sha256:{artifact_sha}",
                     f"reference-selection:sha256:{digest(selection)}"]
    eid = experience.capture(
        store, execution, phase, "PASS", facts={"phase_reference_provenance": provenance},
        source_refs=evidence_refs,
        cohort={"evaluation_holdout": False, "training_reference": True,
                "classification_ref": classification["record_ref"]})
    candidate = {
        "contract_version": "2.0", "source_kind": "ORDINARY_OUTCOME", "version": 1,
        "experience_ref": eid, "symptoms": selection["query"],
        "root_cause": "A completed phase artifact illustrates its declared structure; source success does not "
                      "establish correctness for another job.",
        "remedy": "Phase reference data; current primary inputs remain authoritative.\n" + text,
        "constraints": "Only the declared phase, author, source versions, target and tools. No requirements-author "
                       "or inspector exposure. No inherited PASS verdict or correctness authority.",
        "applicability": scope, "tool_versions": selection["tool_versions"],
        "evidence_refs": evidence_refs,
        "validation_tests": [{"id": "independent-transfer-qualification", "status": "NOT_RUN",
                              "evidence_ref": "qualification:REQUIRED"}],
    }
    return {"schema": "forge-c/phase-reference-candidate/1", "status": "PENDING_INDEPENDENT_QUALIFICATION",
            "candidate": candidate, "provenance": provenance, "exposed": False,
            "next": "knowledge.qualification.record; LessonStore.propose/validate; existing scoped retrieval"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--selection", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    result = prepare(LessonStore(), args.workspace, json.loads(args.selection.read_text()))
    immutable_json(args.out, result)
    print(json.dumps({"status": result["status"], "exposed": False, "output": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
