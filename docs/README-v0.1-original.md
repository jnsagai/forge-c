# Forge-C v0.1 — Open-Source HAL/LLD Safety Factory

**Status: OSS starter kit with an executed host demonstration; NOT ISO 26262/ASIL B qualified.**

An open-source dark software factory architecture for memory-efficient **freestanding C HAL and low-level drivers**, with documentation and gated verification designed for ASPICE 4.0 SWE.1–SWE.6 and ISO 26262 ASIL B projects.

**Start here:** [`docs/OSS-V0.1.md`](docs/OSS-V0.1.md) (technical design), [`docs/OSS-SETUP.md`](docs/OSS-SETUP.md) (installation), [`docs/OSS-STATUS.md`](docs/OSS-STATUS.md) (actual vs planned execution), [`docs/COMPLIANCE-MATRIX.md`](docs/COMPLIANCE-MATRIX.md) (workproduct mapping).

## What actually runs now

```bash
python3 tools/check_oss_policy.py
python3 scripts/oss_preflight.py --strict-demo
./scripts/run_oss_demo.sh
./scripts/run_oss_clang_analyzer.sh
python3 tools/verify_oss_demo.py
python3 -m unittest discover -s tests -v
```

The demo compiles a **generic, invented** RCC-style C driver on Linux, runs host C tests and generates LLVM coverage including MC/DC, storing raw logs and SHA-256 manifest. It is not silicon-specific, does not establish real MCU coverage, and is **not** MISRA or ASIL B evidence.

Run optional OSS static-analysis adapters **after installing the tools**:

```bash
./scripts/run_oss_static.sh
./scripts/run_oss_misra_subset.sh
```

## Full local AI factory

- Fabro (MIT) with Ollama CLI/server (MIT-source component) and Qwen3 8B (Apache-2.0 weights).
- No paid model APIs, commercial analyzers, proprietary ALM tools or vendor-locked MCP services.
- Native test C standard `assert` is bootstrap-only; Unity/CMock intended for production unit campaigns.
- Existing strict `tools/quality_gate.py` and `workflows/forge-c.fabro` protect the real safety-oriented candidate/release workflow.

```bash
# Install/configure Fabro, Ollama and Qwen first; see docs/OSS-SETUP.md.
export OLLAMA_API_KEY=ollama
fabro run workflows/oss-bootstrap.fabro --model qwen3:8b --provider ollama
```

**Source project:** [`FORGE-C-PROJETO.md`](FORGE-C-PROJETO.md) (original project charter and architecture, now modified for OSS v0.1). It is superseded by `docs/OSS-V0.1.md` for all tool choices.

**Critical boundaries:** MISRA C and ISO 26262 standard publications are proprietary, and the open-source Cppcheck MISRA checker has incomplete rule coverage. Real ISO 26262 evidence requires risk-based tool-confidence assessment, allocated upstream safety requirements, approved HSI, target-level verification, independent review and authorized safety release. **No auto-merge or auto-release.**

**Evidence integrity limitation:** hashes detect log changes, but do not authenticate who produced them. Production evidence needs an isolated trusted runner, protected artifact storage, independent safety review and source/run attestation.
