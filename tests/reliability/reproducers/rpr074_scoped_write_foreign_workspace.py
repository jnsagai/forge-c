"""RPR-074 (standalone Ornith SWE.1 run on Omniverse2, 2026-10-31,
evidence/014-durable-local-autonomy/swe1-ornith-standalone-20261031): a workspace COPY keeps the source's
.forge-run/binding.json, whose `workspace` is the source's absolute path. visit.write_scoped builds its Authorizer
from that binding; Authorizer.decide -> development_execution.mutation_allowed(self.workspace, ...) ->
phase_state() then reads and rewrites .forge-run/lrtx/<phase>/development-execution.json in the SOURCE workspace,
while the file itself is written into the copy (lrtx/modelcmp, lrtx/seeded and lrtx/campaign copy workspaces)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "scoped write in a workspace copy touched development-execution state of the source workspace"


def main() -> int:
    from forge_factory import development_execution as D
    from forge_factory.lrtx import visit as V

    with tempfile.TemporaryDirectory() as d:
        src, copy = Path(d) / "source" / "workspace", Path(d) / "copy" / "workspace"
        (src / ".forge-run").mkdir(parents=True)
        (src / ".forge-run/manifest.json").write_text(json.dumps(
            {"purpose": "QM", "development_execution": D.binding(D.DEMO, "QM")}))
        (src / ".forge-run/binding.json").write_text(json.dumps(
            {"binding_id": "rpr074", "workspace": str(src),
             "nodes": {"swe1_author": {"role": "swe1-author", "phase": "SWE.1"}}}))
        shutil.copytree(src, copy, symlinks=True)  # the way modelcmp._fresh_copy / seeded / campaign copy
        V.write_scoped(copy, {"workproducts/SWE.1/software_requirements.md": "# copy\n"}, "swe1_author")
        if not (copy / "workproducts/SWE.1/software_requirements.md").is_file():
            print("REPRODUCER_ERROR:WRITE_NOT_IN_COPY")
            return 2
        touched = (src / ".forge-run/lrtx/SWE.1/development-execution.json").exists()
        own = (copy / ".forge-run/lrtx/SWE.1/development-execution.json").exists()
    if touched:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if not own:
        print("REPRODUCER_ERROR:NO_DEVELOPMENT_STATE_IN_COPY")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
