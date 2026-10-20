"""RPR-058 (h002): an author skill names an output the role's write policy denies (swe4-author:
verification/unit/unit_verification_summary.json); the author was refused and escalated DEF-001 (FACTORY)."""
import sys

SIG = "author skill output outside the role's write scope"


def main() -> int:
    import yaml

    from forge_factory.common import REPO_ROOT
    from forge_factory.policy.authz import ROLE_WRITE_PREFIXES
    from forge_factory.registry import skillgen

    roles = yaml.safe_load((REPO_ROOT / "config/factory/agents.yaml").read_text())["agents"]
    bad = [f"{r['id']}:{o}" for r in roles if r.get("phase") and r["id"].endswith("-author")
           for o in skillgen._outputs(r) if not any(o.startswith(p) for p in ROLE_WRITE_PREFIXES.get(r["id"], []))]
    if bad:
        print("outside: " + ", ".join(bad))
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
