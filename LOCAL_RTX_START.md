# Forge-C local RTX development line

**Status: specification accepted by the owner; optimized runtime NOT IMPLEMENTED / NOT QUALIFIED.**

The owner accepted the local optimization plan on 2026-10-21 with one additional requirement: preserve the
working Codex/Claude factory and develop the local optimization as a separate version.

| Line | Reference | Purpose |
|---|---|---|
| Preserved snapshot | `baseline/codex-claude-2026-10-21` at `86f1f40c030bc721e7e5125a572d69647c4ac041` | Existing code, configurations, provider integrations and recorded evidence |
| Local development | `feat/010-local-rtx-optimization` | Explicitly selected, local-only RTX 4070 Laptop 8 GB / 32 GB RAM implementation |
| Main | Existing maintenance line | Its defaults and deployed services are not switched by this feature |

The commit SHA, rather than a movable branch name, identifies the preserved source snapshot. This does not
create a backup of external archives, installed binaries, model weights, credentials or the running machine.
Those host-side preservation checks are a prerequisite to local deployment, not completed evidence.

Read in order:

1. [Version separation decision](docs/adr/ADR-0013-preserve-codex-claude-local-rtx-line.md).
2. [Feature specification](specs/010-local-rtx-optimization/spec.md).
3. [Implementation plan](specs/010-local-rtx-optimization/plan.md).
4. [Tasks and evidence status](specs/010-local-rtx-optimization/tasks.md).
5. [Source baseline record](specs/010-local-rtx-optimization/baseline.json).

Implement one tested increment at a time. Keep existing workflow selection and Codex/Claude ACP paths unchanged
when the local optimization is not explicitly selected (`scripts/lrtx_compat_check.sh` compares the workflow graphs,
ACP conversion, run configuration and model profile of 21 existing combinations with the frozen baseline fixtures).

P1 (explicit profile, isolation, local endpoints, admission and measurement) is available for experiments only:

```bash
python -m forge_factory.lrtx.stack init     # isolated root $FORGE_LRTX_ROOT (default .../forge-c-lrtx), own venv
python -m forge_factory.lrtx.stack start    # own Ollama :11445, admission gateway :11446, Fabro :32390 in a
                                            # user+network namespace without external interfaces
python -m forge_factory.lrtx.stack exec -- python -m forge_factory.workorder --example examples/0009a-iwdg-ll \
    --wo WO-...-lrtx1 --profile local-rtx-v1 --model qwen3-coder:30b
python -m forge_factory.lrtx.stack stop
```

`--profile` refuses ACP, cloud providers, shared or symlinked runtime roots, non-profile ports, an unverified network
denial and a model whose digest differs from the profile. The profile is NOT qualified; nothing here is a release.

Do not use the production checkout, state database, Fabro storage, service units or archive directory for local
experiments. Do not change the process, safety gates, inspection independence or promotion authority to obtain a
successful local run. Both lines keep the same quality criteria and offline review semantics.
