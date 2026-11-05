"""RPR-138 (local run WO-F014-SWE1-WWDGHAL-20261103-L32B, Omniverse2, gen13 f02766d9, Fabro run
01M6HGSX8NHGSFCVXJ2EHYXPW0, 2026-11-03): the SWE.1 author's first writes were `write_file <ws>/workproducts/SWE.1`
and `write_file <ws>/traceability` - the directory paths themselves. policy/authz.py admitted a write when
`rel == p.rstrip("/") or rel.startswith(p)`, so for the swe1-author's directory prefixes "workproducts/SWE.1/" and
"traceability/" the directory path itself was ALLOWED and Fabro's write_file created two empty REGULAR files with
those names. Every later write below them failed ("File exists"), the author has no shell to undo it, and SWE.1 was
STUCK twice on MISSING_REQUIRED_OUTPUT (all outputs missing) until the turn budget ran out.

Scenario (synthetic workspace in a scratch dir, the revision's own Authorizer): the swe1-author asks to write
"workproducts/SWE.1" and "traceability" (directory prefixes of its role) and an already existing directory.
Symptom: any of them is allowed. Controls (a loosened or broken check is an error, not ABSENT): a file inside a
directory prefix is allowed; a path outside the role's scope is still WRITE_SCOPE_DENIED; the file prefix
"safety/software_safety_requirements.md" is still allowed by equality."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the write scope admits a role's directory prefix path itself, so the output directory is written as a file"


def main() -> int:
    from forge_factory.policy.authz import Authorizer, Binding

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "workspace"
        (ws / ".forge-run").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"purpose": "QM"}))
        (ws / "workproducts/SWE.1/notes").mkdir(parents=True)  # an existing directory inside the scope
        auth = Authorizer(Binding("rpr138", str(ws), {"swe1_author": {"role": "swe1-author", "phase": "SWE.1"}}))

        def decide(rel: str):
            return auth.decide("swe1_author", "write_file", {"file_path": str(ws / rel), "content": ""})

        controls = {"workproducts/SWE.1/software_requirements.md": True, "traceability/requirements_to_tests.csv": True,
                    "safety/software_safety_requirements.md": True, "software/src/x.c": False}
        for rel, allow in controls.items():
            r = decide(rel)
            if r.allow != allow or (not allow and r.code != "WRITE_SCOPE_DENIED"):
                print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:control {rel} allow={r.allow} code={r.code}")
                return 2
        bad = [(rel, decide(rel)) for rel in ("workproducts/SWE.1", "traceability", "workproducts/SWE.1/notes")]
        allowed = [f"{rel} -> {r.code}" for rel, r in bad if r.allow]
    if allowed:
        print("observed: " + "; ".join(allowed))
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
