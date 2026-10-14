# OSS-only local setup — Ubuntu workstation

The following are example Linux commands, not evidence that the tools have been installed on the user's machine. Verify license notices when selecting binaries/packages, especially the local model server distribution and transitive dependencies.

## 1. Install development prerequisites

```bash
sudo apt update
sudo apt install -y git cmake ninja-build clang llvm cppcheck \
  gcc-arm-none-eabi binutils-arm-none-eabi python3 python3-venv graphviz
```

Additional open-source tools can be added independently: Cppcheck MISRA addon (normally provided with Cppcheck), CBMC, Frama-C Eva/WP, Unity/CMock and Renode. Frama-C extra plugins have varying licenses; the first version uses **only the open-source distribution**. An MCU vendor SDK must be separately audited for license and binary restrictions.

## 2. Run native demo (no AI or MCU needed)

```bash
python3 tools/check_oss_policy.py
python3 scripts/oss_preflight.py --strict-demo
./scripts/run_oss_demo.sh
./scripts/run_oss_clang_analyzer.sh
python3 tools/verify_oss_demo.py
python3 -m unittest discover -s tests -v
```

Outputs: `evidence/oss-demo/llvm-host.log`, `evidence/oss-demo/manifest.json`, `build/oss-demo/test.profdata`. The generated host `.su` stack-usage files are illustrative only.

## 3. Run static analysis / partial MISRA addon

```bash
./scripts/run_oss_static.sh
# The official Cppcheck addon only checks a subset of MISRA C 2012:
./scripts/run_oss_misra_subset.sh
```

You must install both Cppcheck and the appropriate add-on. If the latter is installed at a nonstandard path, set `CPPCHECK_MISRA_ADDON` to its `misra.py` path. All unsupported rules, deviations, code generation assumptions and false positives must be recorded and assessed by the project team.

## 4. Configure Fabro and local Qwen (no cloud API)

Install Fabro from https://github.com/fabro-sh/fabro following the project's installation instructions. Install the open-source Ollama **CLI/server**, not an unverified proprietary GUI application. Start the service then pull an Apache-2.0 Qwen model:

```bash
ollama serve                # separate terminal/service if not already running
ollama pull qwen3:8b
ollama list
```

Fabro settings fragment (also provided as `config/fabro-settings.oss.example.toml`; merge into the actual settings file for your installed release):

```toml
[llm.providers.ollama]
enabled = true
default_model = "qwen3:8b"

[llm.providers.ollama.models."qwen3:8b"]
display_name = "Qwen3 8B Local"
api_model = "qwen3:8b"
limits = { context_tokens = 32768, max_output_tokens = 4096 }
capabilities = { text = true, tools = true }
```

Configure the `OLLAMA_API_KEY=ollama` dummy token as described by Fabro. No paid API keys are needed. Confirm installed catalog:

```bash
export OLLAMA_API_KEY=ollama
fabro model list --provider ollama
fabro model test --model qwen3:8b --provider ollama
fabro run workflows/oss-bootstrap.fabro --model qwen3:8b --provider ollama
```

The reference Fabro files are **not execution-tested in this scaffold** because Fabro and Ollama are not installed in the build/test environment. Verify exact syntax against your pinned Fabro version. With RTX 4070 8 GB, `qwen3:8b` quantized is feasible but context/cache consume additional VRAM; throttle concurrency and context for unattended runs.

## 5. Real target workflow

To run `workflows/forge-c.fabro`, first provide an approved MCU/HSI, safety allocation, toolchain versions, target budgets, tool-confidence assessment and review procedures. The default `profiles/stm32n6-rcc-pilot.json` is intentionally `draft` and **must fail** validation. Do not change its status to bypass safety checks. Real MCU verification requires cross-compilation and board testing, not host assertions.

## Open-source requirements policy

The code/tooling stack can be completely OSS. MISRA C and ISO 26262 **normative standard texts are licensed, not open-source**; they cannot be redistributed as part of the factory. Access, edition applicability, tailoring and independent safety approval remain required even when the analysis tooling is free.

## 6. Optional verification and footprint experiments

```bash
./scripts/compare_host_size.sh     # Clang -Os / -O2 / -Oz + host regression checks
./scripts/run_oss_cbmc.sh          # Requires CBMC; validates an illustrative clock-bit property
```

Results are **host-only** and cannot be substituted for MCU ELF/map/stack/cycle measurements or tool validation. A CBMC bound holds only under the tool's modeled assumptions.
