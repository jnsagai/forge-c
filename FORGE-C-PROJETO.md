# FORGE-C v0.1 — Dark Factory Open Source

**Objectivo:** gerar HALs e low-level drivers em C, minimizando ROM/Flash, RAM, stack e ciclos de CPU, com rastreabilidade e workproducts compatíveis com a engenharia Automotive SPICE PAM 4.0 SWE.1–SWE.6 e a preparação de evidências ISO 26262 ASIL B.

**Versão 0.1:** exclusivamente ferramentas open source, modelos Qwen locais e sem serviços comerciais ou APIs pagas. O orquestrador previsto é o **Fabro**, com Ollama (CLI/servidor) e Qwen3 8B. Para validação estão selecionados Clang/GCC, CMake/Ninja, Cppcheck (addon MISRA parcial), Clang Static Analyzer, CBMC, Frama-C, Unity/CMock e LLVM-Cov/MC/DC. Renode/HwSim e toolchain Arm serão acrescentados ao piloto em MCU real.

**Estado demonstrável:** existe um pequeno driver RCC genérico, sem endereços de hardware reais, com testes de comportamento e cobertura LLVM executáveis em Linux. Esta demonstração não é um driver STM32N6, não comprova MISRA completo, não verifica ciclos de CPU reais e **não é código certificado ASIL B**. Os gates do workflow de safety permanecem bloqueados até à introdução de HSI, alocação de safety, revisão e validação em hardware.

A documentação técnica completa é fornecida em [`docs/OSS-V0.1.md`](docs/OSS-V0.1.md), a instalação em [`docs/OSS-SETUP.md`](docs/OSS-SETUP.md), a matriz de workproducts em [`docs/COMPLIANCE-MATRIX.md`](docs/COMPLIANCE-MATRIX.md), o estado dos componentes em [`docs/OSS-STATUS.md`](docs/OSS-STATUS.md) e os exemplos em [`examples/0001-generic-rcc/WORKPRODUCTS.md`](examples/0001-generic-rcc/WORKPRODUCTS.md).

**Nota normativa:** MISRA C e ISO 26262 são normas com textos proprietários; o projecto não distribui qualquer conteúdo normativo licenciado. Ferramentas gratuitas não substituem a avaliação de confiança/qualificação exigida pelo uso definido no plano de safety.
