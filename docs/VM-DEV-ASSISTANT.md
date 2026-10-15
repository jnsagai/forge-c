# Forge-C development assistant on the on-premise VM (Qwen Code)

Status: **draft, not yet tried on the VM.** Every setting below that is marked *(verify)* must be checked against the
documentation of the Qwen Code version you actually install. Record the outcome in an ADR.

This guide sets up a local AI coding assistant, similar to Claude Code today, so that Forge-C can keep evolving on the
on-premise VM. It uses the same GPU server as the factory and sends nothing outside the controlled zone. The
infrastructure context is in [`ONPREM-DEPLOYMENT.md`](ONPREM-DEPLOYMENT.md).

## 1. What runs where

| Item | Choice |
|---|---|
| Assistant | Qwen Code CLI (Apache-2.0), a terminal coding agent |
| Model | The existing vLLM server (Qwen3.6-35B-A3B), called **directly**, not through the Forge-C LLM gateway |
| Rules file | [`QWEN.md`](../QWEN.md) at the repository root, read automatically by Qwen Code |
| GPU share | At most 2 concurrent sessions, 131,072-token context each |
| Code | A separate development worktree; production runs only tagged releases of `main` |

The assistant bypasses the Forge-C gateway on purpose. The gateway turns thinking off and narrows the tool list for
factory agents, and both would hurt a coding assistant.

## 2. Prerequisites

- [ ] Node.js 20 LTS or later, installed from the internal mirror (or an offline tarball checked against its hash).
- [ ] An internal npm mirror, or an offline package of Qwen Code with a pinned version.
- [ ] A separate API key on the GPU server for development use, so its load can be told apart from the factory's.
- [ ] An internal Git server in the controlled zone (the VM cannot reach github.com).
- [ ] **Configurable service ports in Forge-C.** `scripts/forge_services.sh` currently hard-codes Ollama `:11435`,
      the gateway `:11436` and Fabro `:32290`. A development Fabro stack next to production needs these to come from
      environment variables first. This is a small code change, to be made and tested before step 4.

## 3. Install Qwen Code

```bash
# npm points at the internal mirror (set once)
npm config set registry https://<internal-npm-mirror>/

# Install a pinned version; record it in evidence/v0.4/inventory
npm install -g @qwen-code/qwen-code@<pinned-version>      # package name (verify)
qwen --version
```

## 4. Create the development worktree

```bash
cd /srv/forge-c/repo                       # production checkout, on a release tag
git worktree add ../forge-c-dev -b dev/<topic> main
cd ../forge-c-dev

# Development data root and ports: never the production ones
export FORGE_DATA_ROOT=/srv/forge-c-dev
. scripts/forge-env.sh
```

Production keeps `FORGE_DATA_ROOT=/srv/forge-c` and its own services. The assistant runs only in `forge-c-dev`.

## 5. Connect Qwen Code to the GPU server

Qwen Code accepts any OpenAI-compatible endpoint through environment variables or `~/.qwen/settings.json`.

```bash
# ~/.config/forge-dev/qwen.env  (mode 0600, never committed)
export OPENAI_BASE_URL=https://<gpu-server>:<port>/v1
export OPENAI_API_KEY=<development key>
export OPENAI_MODEL=<served model name, e.g. Qwen3.6-35B-A3B>          # variable name (verify)
```

```bash
chmod 600 ~/.config/forge-dev/qwen.env
. ~/.config/forge-dev/qwen.env
cd /srv/forge-c-dev/repo && qwen
```

If the GPU server uses an internal CA, point Node.js at it with `NODE_EXTRA_CA_CERTS=/path/to/ca.pem`.

## 6. Lock it down

| Setting | Required value |
|---|---|
| Telemetry and usage statistics | Off in `~/.qwen/settings.json` (key names: verify) |
| Remote MCP servers | None. Only local MCP servers, if any |
| Web fetch / web search tools | Disabled (there is no internet, and the tools must not be offered) |
| Session history location | Under the encrypted data volume, same retention rules as other customer data |
| Shell commands | Approval required for anything outside the development worktree |

The VM has no internet access, which enforces these settings even if one is missed. They should still be set
explicitly, so the configuration is correct on its own.

## 7. Capacity

vLLM does not limit concurrency per API key. Keep to **2 concurrent assistant sessions** by team agreement. If that
proves unreliable, add a concurrency limit for the development key in a small proxy. The factory then keeps room for 7
agents at 64k context (see `ONPREM-DEPLOYMENT.md`).

## 8. First trial task

Start with one small, low-risk task to check that the assistant actually follows `QWEN.md`. For example: "add a unit
test for an existing helper in `factory/python/forge_factory/common.py`".

Check each point and record the result:

- [ ] It stayed inside the development worktree and data root.
- [ ] It wrote the test before or with the change.
- [ ] It ran `make factory-test`, `make design-check`, `make test` and the v0.3 packager tests.
- [ ] It did not claim PASS without a test run.
- [ ] It committed only the task's files, with a clear message.
- [ ] Its report was one line, in the `QWEN.md` format.

Tighten `QWEN.md` wherever it went wrong, then try a second, slightly larger task.

## 9. What to expect

Qwen3.6-35B-A3B activates about 3B parameters per token. It is good at focused edits, test-fix loops and explaining
code. It is weaker than Claude at multi-file design changes and subtle logic such as the policy hook, the supervisor
or the release finalizer. For those changes, keep the tasks small, rely on the test suites, and review every diff
yourself.
