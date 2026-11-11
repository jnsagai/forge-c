---
title: "Installation"
description: "## Choose your starting point"
---

## Choose your starting point

The host demonstration exercises a generic RCC-style driver using local tools. The full factory also needs Python, a compatible model endpoint, Fabro, role-specific MCP services, and approved input documents.

The reference setup uses Ubuntu. The recorded factory baseline uses Python 3.13 (the package requires at least 3.12), LLVM/Clang 19.1.7, GNU Arm Embedded 10.3, Cppcheck 2.7, CMake, Ninja, and coverage tools. These are **recorded baseline versions**, not a recommendation to upgrade an active run in place.

## Get the source

```sh
git clone https://github.com/jnsagai/forge-c.git
cd forge-c
```

## Try the host demonstration

Install Git, Python 3, CMake, Ninja, Clang/LLVM and Cppcheck through your operating system. Review the [OSS setup guide](https://github.com/jnsagai/forge-c/blob/main/docs/OSS-SETUP.md) for the complete baseline and optional tools.

From the repository root:

```sh
python3 tools/check_oss_policy.py
python3 scripts/oss_preflight.py --strict-demo
./scripts/run_oss_demo.sh
./scripts/run_oss_clang_analyzer.sh
python3 tools/verify_oss_demo.py
```

The preflight reports missing or incompatible tools. The outputs under `evidence/oss-demo/` are host-level demonstration evidence. They do not validate a specific MCU or linked target firmware.

## Set up the full factory

Choose an existing, writable data directory for models, state, archives, and the virtual environment. Set the override **before** loading the environment, because the script's default points to the reference operator's data volume.

```sh
export FORGE_DATA_ROOT="$PWD/.factory-data"
mkdir -p "$FORGE_DATA_ROOT"
. scripts/forge-env.sh
make factory-bootstrap
```

The bootstrap installs from the hash-pinned Python lock file. Keep `.factory-data/` out of version control. For an operational installation, use a dedicated volume and review the [on-premise deployment guide](https://github.com/jnsagai/forge-c/blob/main/docs/ONPREM-DEPLOYMENT.md).

## Configure model and orchestration

The local path uses an OpenAI-compatible tool-calling endpoint, typically Ollama with `qwen3:8b`, through the Forge-C gateway and a separate Fabro server. The example provider configuration is [config/fabro-settings.oss.example.toml](https://github.com/jnsagai/forge-c/blob/main/config/fabro-settings.oss.example.toml).

```sh
./scripts/forge_services.sh start
./scripts/forge_services.sh status
./scripts/install_supervisor.sh
```

Install the pinned runtime tools first; the service script does not install the model server or all verification tools. Read the [operations guide](https://github.com/jnsagai/forge-c/blob/main/docs/OPERATIONS-v0.4.md) and the [local-model findings](https://github.com/jnsagai/forge-c/blob/main/docs/adr/ADR-0005-local-model-runtime-findings.md) before launching work.

The factory supports an open-source local runtime. Later recorded campaigns also used explicitly configured Codex and Claude adapters; their service requirements are separate from the local path.

## Verify the environment

```sh
make design-check
make factory-test
```

These checks validate the factory, not a new target driver. Continue with [your first work order](/docs/getting-started/first-work-order/) after your tools, permissions, and approved inputs are available.
