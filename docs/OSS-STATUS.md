# Implementation status — Forge-C v0.1

| Capability | Status | Evidence / next action |
|---|---|---|
| Cloneable project scaffold with ASPICE/ISO templates | **Included** | `templates/`, `docs/COMPLIANCE-MATRIX.md` |
| Host generic RCC C driver | **Implemented** | `drivers/demo_rcc/` |
| Native Clang build / CTest | **Executed** | `evidence/oss-demo/llvm-host.log` |
| Host branch, region and MC/DC coverage | **Executed** | LLVM report in host log + `.profdata` hash |
| Integrity evidence manifest | **Executed** | `evidence/oss-demo/manifest.json` |
| OSS policy declaration / demo hash verification | **Tested** | `tools/check_oss_policy.py`, `tools/verify_oss_demo.py` |
| Safety/evidence fail-closed Python gates | **Tested** | `python3 -m unittest discover -s tests -v` |
| Fabro CLI execution with Ollama/Qwen | **Not executed** | No local Fabro/Ollama in build environment |
| Clang Static Analyzer | **Executed** | `evidence/oss-demo/clang-analyzer.log` |
| Cppcheck MISRA subset and combined static check | **Not executed** | Cppcheck not installed in build environment |
| CBMC / Frama-C proof runs | **Not executed** | Install and constrain C harnesses |
| Unity/CMock native campaign | **Not executed** | Pull and pin open-source dependency release |
| Renode/HwSim MCU simulation | **Not executed** | Confirm peripheral model and HSI |
| Arm target compile / real target resource budget | **Not executed** | Select and validate target CPU/part/toolchain |
| Hardware trace, timing, fault injection | **Not executed** | Board and approved bench required |
| Safety manager's tool-confidence/release approval | **Not executed** | Mandatory human safety lifecycle step |

None of the `NOT EXECUTED` categories can be filled with AI-generated PASS values. Generated evidence files under `evidence/oss-demo/` are **only host demonstrations**; they are excluded from target quality gates.
