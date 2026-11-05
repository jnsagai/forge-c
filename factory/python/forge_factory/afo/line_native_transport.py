"""Hash-bound native HTTP identity measurement, separate from role competence.

The signed line control selects this proof. It never grants model use or changes
mission limits; a new source/profile/binary requires a fresh isolated measurement.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .durable import Refused

SCHEMA = "forge-c/native-header-transport-measurement/1"
SCOPE = "TRANSPORT_ONLY_DETERMINISTIC_STUB_NO_ROLE_QUALIFICATION"
ADAPTERS = ("llm_gateway.py", "afo/product_job.py", "afo/execution_lifecycle.py", "fabro/client.py", "lrtx/stack.py")
CONTROLS = {"actual_header_and_nonce": True, "missing_header": False, "unknown_header": False,
            "foreign_nonce": False, "foreign_job": False}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ref, *, job, cfg):
    """Existing job-bound boundary; unbound callers use the explicit context API."""
    try:
        return require_context(ref, profile_id=job["profile"], expected_revision=job.get("factory_revision"), cfg=cfg)
    except (KeyError, TypeError) as exc:
        raise Refused("LINE_NATIVE_TRANSPORT_PROOF_INVALID", str(exc)) from exc


def require_context(ref, *, profile_id, expected_revision, cfg):
    """Validate measured source/profile/binary facts, without fabricating a job.

    This is evidence only. The OS-owner bootstrap separately intersects live
    guardian, canonical Store, service scope, Intent and physical locks.
    """
    from ..common import REPO_ROOT
    from ..lrtx.profile import load
    from ..workorder import factory_revision
    from .fault_observer import bound_json

    try:
        if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
                or not isinstance(ref["path"], str) or not Path(ref["path"]).is_absolute()
                or not re.fullmatch(r"[a-f0-9]{64}", str(ref["sha256"]))):
            raise ValueError("REFERENCE_INVALID")
        proof = bound_json(ref)
        profile = load(profile_id)
        revision = factory_revision()
        if (proof.get("schema") != SCHEMA or proof.get("scope") != SCOPE
                or proof.get("verdict") != "PASS" or proof.get("production_mutations") is not False
                or proof.get("source_tracked_dirty") is not False
                or proof.get("source_revision") != revision.get("commit")
                or revision.get("dirty") is not False
                or expected_revision != revision
                or proof.get("profile") != profile["id"]
                or proof.get("profile_sha256") != profile["_sha256"]
                or proof.get("binary_sha256") != _sha(cfg.fabro_bin)
                or proof.get("launch_returncode") != 0 or proof.get("terminal_status") != "SUCCEEDED"
                or proof.get("labels_match") is not True
                or proof.get("fixture_terminal_confirmed") is not True
                or proof.get("own_server_stopped") is not True
                or proof.get("all_headers_equal_actual_run_id") is not True):
            raise ValueError("IDENTITY_OR_OUTCOME_MISMATCH")
        adapters = {p: _sha(REPO_ROOT / "factory/python/forge_factory" / p) for p in ADAPTERS}
        if proof.get("adapter_sha256") != adapters:
            raise ValueError("ADAPTER_CHANGED")
        if any(not re.fullmatch(r"[a-f0-9]{64}", str(proof.get(k)))
               for k in ("harness_sha256", "settings_sha256", "graph_sha256")):
            raise ValueError("MEASUREMENT_IDENTITY_MISSING")
        native_id = proof.get("native_run_id")
        if not isinstance(native_id, str) or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", native_id):
            raise ValueError("NATIVE_ID_INVALID")
        rows = proof.get("requests")
        output = (profile.get("runtime") or {}).get("fabro_max_output_tokens", 16384)
        if (not isinstance(rows, list) or len(rows) != len(profile["models"]["allowed"])
                or proof.get("request_count") != len(rows)
                or {row.get("model") for row in rows} != set(profile["models"]["allowed"])
                or any(row.get("x_session_id") != native_id or row.get("path") != "/v1/chat/completions"
                       or row.get("stream") is not True or row.get("max_tokens") != output
                       or row.get("max_completion_tokens") is not None for row in rows)):
            raise ValueError("OBSERVED_HEADER_OR_ENVELOPE_MISMATCH")
        controls = proof.get("identity_controls")
        if (not isinstance(controls, dict) or set(controls) != set(CONTROLS)
                or any(controls[k].get("pass") is not True or controls[k].get("accepted") is not accepted
                       for k, accepted in CONTROLS.items())):
            raise ValueError("NEGATIVE_CONTROLS_NOT_PROVEN")
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise Refused("LINE_NATIVE_TRANSPORT_PROOF_INVALID", str(exc)) from exc
    return {"scope": SCOPE, "proof_sha256": ref["sha256"], "source_revision": revision["commit"],
            "profile_sha256": profile["_sha256"], "binary_sha256": proof["binary_sha256"],
            "max_tokens": output, "role_qualification": False}
