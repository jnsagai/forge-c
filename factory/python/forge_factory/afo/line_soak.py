"""M9 line-local observation adapter for the existing operational campaign/collector.

Preparation is not live authority or qualification. Starting still uses the existing
signed qualification runbook preflight. Observation never repairs a service, calls a
model, creates a queue, extends a grant or stops the factory at a campaign boundary.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, sha256_file
from ..lrtx.profile import load as load_profile
from . import line_launcher as LL
from . import line_watchdog as W
from .durable import Refused

SCHEMA = "forge-c/line-operational-runtime/1"


def _revision():
    from ..workorder import factory_revision

    return factory_revision()


def runtime_sources():
    return {"adapter_sha256": sha256_file(Path(__file__)), "watchdog_sha256": sha256_file(Path(W.__file__))}


def validate_runtime(value, plan):
    required = {"schema", "profile", "profile_sha256", "launch_dir", "fabro_host_port", "timeout_seconds", "candidate_revision",
                "adapter_sha256", "watchdog_sha256"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema") != SCHEMA:
        raise Refused("LINE_SOAK_RUNTIME_INVALID")
    if any(value.get(k) != v for k, v in runtime_sources().items()):
        raise Refused("LINE_SOAK_OBSERVER_SOURCE_CHANGED")
    actual = _revision()
    if (not isinstance(value.get("candidate_revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", value["candidate_revision"])
            or actual.get("dirty") is not False or actual.get("commit") != value["candidate_revision"]):
        raise Refused("LINE_SOAK_CANDIDATE_CHANGED_OR_DIRTY")
    profile_id = value.get("profile")
    if not isinstance(profile_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,120}", profile_id):
        raise Refused("LINE_SOAK_PROFILE_INVALID")
    profile = load_profile(profile_id)
    if (profile.get("local_only") is not True or profile.get("provider") != "ollama"
            or profile["_sha256"] != value["profile_sha256"]):
        raise Refused("LINE_SOAK_LOCAL_PROFILE_CHANGED")
    if (type(value["fabro_host_port"]) is not int or not 1 <= value["fabro_host_port"] <= 65535
            or type(value["timeout_seconds"]) is not int or not 1 <= value["timeout_seconds"] <= 30):
        raise Refused("LINE_SOAK_PROBE_BOUND_INVALID")
    launch = Path(value["launch_dir"])
    data = Path(plan["data_root"]).resolve()
    if not launch.is_absolute() or not launch.resolve().is_relative_to(data):
        raise Refused("LINE_SOAK_LAYOUT_INVALID")
    root = launch.resolve() / "lrtx/state"
    if (plan.get("unit") != W.UNIT
            or Path(plan["database"]).resolve() != root / "supervisor/line-queue.sqlite3"
            or Path(plan["heartbeat"]).resolve() != root / "supervisor/line-conductor.heartbeat"):
        raise Refused("LINE_SOAK_LAYOUT_INVALID")
    intent, evidence = Path(plan["intent"]).resolve(), Path(plan["evidence_root"]).resolve()
    if intent.is_relative_to(data) or evidence.is_relative_to(data) or data.is_relative_to(evidence):
        raise Refused("LINE_SOAK_SURVIVING_HOST_PATHS_REQUIRED")
    expected = {"fabro": f"http://127.0.0.1:{value['fabro_host_port']}/health",
                "gateway": f"http://127.0.0.1:{profile['deployment']['ports']['gateway']}/health"}
    if plan.get("health_urls") != expected:
        raise Refused("LINE_SOAK_HEALTH_ROUTE_MISMATCH")
    return profile


def observer_plan(*, data_root, launch_dir, intent, evidence_root, mount_uuid, profile,
                  fabro_host_port=32397, interval_seconds=30, max_samples=50000, minimum_free_bytes=64 * 1024 * 1024,
                  prerequisites_ref=None):
    """Build a reviewable input for qualification.freeze; no filesystem writes or service actions occur."""
    from . import fault_observer as O
    from . import operational_collection as C
    from . import operational_facts as F
    from . import operational_work, qualification_capture, queue

    selected = load_profile(profile)
    if not isinstance(mount_uuid, str) or not re.fullmatch(r"[0-9a-fA-F-]{8,64}", mount_uuid):
        raise Refused("OBSERVER_MOUNT_IDENTITY_REQUIRED")
    root = Path(launch_dir).resolve() / "lrtx/state"
    plan = {"schema": "forge-c/operational-observer-plan/1", "database": str(root / "supervisor/line-queue.sqlite3"),
            "intent": str(Path(intent).absolute()), "data_root": str(Path(data_root).absolute()),
            "evidence_root": str(Path(evidence_root).absolute()), "heartbeat": str(root / "supervisor/line-conductor.heartbeat"),
            "mount_uuid": mount_uuid, "unit": W.UNIT, "max_rows": 1000,
            "observer_source_sha256": sha256_file(Path(O.__file__)), "fact_evaluator_sha256": sha256_file(Path(F.__file__)),
            "work_verifier_sha256": sha256_file(Path(operational_work.__file__)),
            "product_observer_sha256": sha256_file(Path(qualification_capture.__file__)),
            "queue_reader_sha256": sha256_file(Path(queue.__file__)),
            "health_urls": {"fabro": f"http://127.0.0.1:{fabro_host_port}/health",
                            "gateway": f"http://127.0.0.1:{selected['deployment']['ports']['gateway']}/health"},
            "line_runtime": {"schema": SCHEMA, "profile": profile, "profile_sha256": selected["_sha256"],
                             "launch_dir": str(Path(launch_dir).absolute()), "fabro_host_port": fabro_host_port,
                             "candidate_revision": _revision().get("commit"),
                             "timeout_seconds": 15, **runtime_sources()},
            "collection": {**C.source_hashes(), "interval_seconds": interval_seconds, "max_samples": max_samples,
                           "minimum_free_bytes": minimum_free_bytes}}
    if prerequisites_ref is not None:
        from .line_soak_prerequisites import reference

        reference(prerequisites_ref)
        plan["prerequisites_ref"] = prerequisites_ref
    validate_runtime(plan["line_runtime"], plan)
    C.configuration(plan["collection"])
    return plan


def health(frozen, bound):
    """Only status/read-only health commands. The gateway is inside this line's namespace, not the host default."""
    from . import fault_observer as O

    value = frozen["line_runtime"]
    profile = validate_runtime(value, frozen)
    cfg = LL.LineConfig.from_env(launch_dir=value["launch_dir"], fabro_host_port=value["fabro_host_port"])
    try:
        result = subprocess.run([str(cfg.python), "-m", "forge_factory.lrtx.stack", "--profile", value["profile"], "status"],
                                cwd=REPO_ROOT / "factory/python", env=LL.run_env(cfg, REPO_ROOT, value["profile"]),
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=value["timeout_seconds"])
        status = LL._last_json(result.stdout) or {}
        details = status.get("health") if result.returncode == 0 and status.get("status") == "UP" else {}
        details = details if isinstance(details, dict) else {}
    except (OSError, subprocess.SubprocessError):
        details = {}
    conductor = W.check(bound, heartbeat=Path(frozen["heartbeat"]), probe=lambda: O.unit_status(W.UNIT))
    mount = subprocess.run(["findmnt", "--noheadings", "--output", "UUID", "--target", frozen["data_root"]],
                           capture_output=True, text=True, timeout=3, check=False)
    required = {"fabro", "gateway", "ollama"}
    if (profile.get("runtime") or {}).get("llama_server"):
        required.add("llama_server")
    worker_ready = all(details.get(key) is True for key in required)
    return {"conductor": conductor["ok"] is True,
            "fabro": details.get("fabro") is True and O._healthy(frozen["health_urls"]["fabro"]),
            "gateway": worker_ready,
            "data_volume": mount.returncode == 0 and mount.stdout.strip() == frozen["mount_uuid"]}


def preflight(manifest, plan_ref, *, live=False, authorization_ref=None):
    from . import fault_observer as O
    from . import qualification as Q

    plan = O.plan(manifest, plan_ref)
    if "line_runtime" not in plan:
        raise Refused("LINE_SOAK_FROZEN_RUNTIME_REQUIRED")
    validate_runtime(plan["line_runtime"], plan)
    result = Q.preflight(manifest, live=live, authorization_ref=authorization_ref)
    from .line_soak_prerequisites import check

    replay = check(manifest, plan)
    result.update(line="local", live_campaign="NOT_RUN", service_stop_at_end=False,
                  prerequisite_status=replay["status"], prerequisites=replay)
    if replay["blockers"]:
        result.setdefault("blockers", []).extend(replay["blockers"])
        result["status"] = "BLOCKED"
    return result


def start(manifest, soak_id, authorization_ref, plan_ref, *, host_plan_ref=None):
    """Explicitly authorized callers only; never called by preparation or healthy observation."""
    from .operational_campaign import start as campaign_start

    result = preflight(manifest, plan_ref, live=True, authorization_ref=authorization_ref)
    if result["blockers"]:
        return result
    return campaign_start(manifest, soak_id, authorization_ref, observer_plan_ref=plan_ref, host_plan_ref=host_plan_ref)


def collect(manifest, soak_id, plan_ref, *, host_plan_ref=None, max_samples=None):
    from . import operational_campaign

    preflight(manifest, plan_ref)  # immutable source/route checks, no grant renewal
    return operational_campaign.collect(manifest, soak_id, plan_ref, host_plan_ref=host_plan_ref, max_samples=max_samples)


def main(argv=None):
    """Preparation only. Live campaign actions retain the existing campaign entrypoint."""
    from .durable import immutable_json
    from .operational_collection import reference

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="write an immutable observer input; never start a campaign")
    for name in ("data-root", "launch-dir", "intent", "evidence-root"):
        prepare.add_argument("--" + name, type=Path, required=True)
    prepare.add_argument("--mount-uuid", required=True, help="actual independently inventoried data volume UUID")
    prepare.add_argument("--profile", required=True)
    prepare.add_argument("--fabro-host-port", type=int, default=32397)
    prepare.add_argument("--interval-seconds", type=int, default=30)
    prepare.add_argument("--max-samples", type=int, default=50000)
    prepare.add_argument("--prerequisites", type=Path,
                         help="typed evidence index; freeze it and its policy in manifest.inputs too")
    prepare.add_argument("--out", type=Path, required=True)
    check = commands.add_parser("preflight", help="validate the frozen plan/source without granting live authority")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--observer-plan", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        values = vars(args).copy()
        destination = values.pop("out")
        values.pop("command")
        prerequisites = values.pop("prerequisites")
        if prerequisites is not None:
            values["prerequisites_ref"] = reference(prerequisites.absolute())
        plan = observer_plan(**values)
        immutable_json(destination, plan)
        out = {"status": "PREPARED_NOT_RUN", "observer_plan": reference(destination.resolve()),
               "candidate_revision": plan["line_runtime"]["candidate_revision"], "service_stop_at_end": False}
    else:
        out = preflight(json.loads(args.manifest.read_text()), reference(args.observer_plan.resolve()))
    print(json.dumps(out, indent=2))
    return 2 if out.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
