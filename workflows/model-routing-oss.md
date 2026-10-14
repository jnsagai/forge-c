# Local-only model routing for Forge-C v0.1

Default: `Qwen3 8B Q4_K_M` through the OSS Ollama CLI/server and Fabro's built-in Ollama provider. No DeepSeek API, Codex service, online model gateway or token-based billing. On a local 8-GB GPU, disable parallel model jobs initially and shorten context as necessary.

Local Fabro invocation after provider configuration:

```bash
export OLLAMA_API_KEY=ollama
fabro run workflows/oss-local-candidate.fabro --model qwen3:8b --provider ollama
```

Fabro itself is a MIT-licensed open-source orchestrator, but its full agent execution on your workstation must be smoke tested, including tool calling, latency and context length. Each generated C file should be verified by deterministic source/test tools; **a second prompt to the same Qwen weights is not an independent ISO 26262 verification reviewer**. Independently assigned human reviewers and separate physical verification evidence are required by the project's safety plan.

The local candidate workflow intentionally fails until actual approved device and safety inputs are available. Use `workflows/oss-bootstrap.fabro` for the immediate non-safety host demonstration.
