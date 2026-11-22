# M0 tool and licence inventory (T004)

Host: loop10 (owner workstation). Recorded 2026-11-22. Omniverse2 was not used.

| Tool | Version | Licence | Role in feature 023 | How obtained |
|---|---|---|---|---|
| apm-cli | 0.37.0 | MIT | package install, audit, pack | `uv venv` + `uv pip install apm-cli` (user space, no sudo) |
| Python (tests) | 3.10.12 | PSF | minimum supported runtime; test venv | `uv venv --python /usr/bin/python3.10` + pytest, jsonschema |
| Python (host) | 3.13.13 | PSF | development | system |
| pytest | 9.x (venv) | MIT | package tests | venv |
| jsonschema | venv | MIT | metaschema check (test only, never at runtime) | venv |
| Claude Code | 2.1.330 | proprietary client | reference **author** harness (owner account) | installed |
| Codex CLI | 0.171.0 | Apache-2.0 | reference **inspector** harness (ChatGPT login) | installed |
| uv | 0.12.17 | MIT/Apache-2.0 | venvs | installed |
| poppler (pdftotext/pdfinfo) | 22.02.0 | GPL-2.0 (used as external tool) | optional, driver doc index | system |
| gcc | 11.4.0 | GPL-3.0 (external tool) | optional, build gate | system |
| cppcheck | 2.7 | GPL-3.0 (external tool) | optional, static-analysis gate | system |
| gcovr | 5.0 | BSD-3 | optional, coverage gate | system |
| git | 2.34.1 | GPL-2.0 (external tool) | scope backstop | system |

The package itself (`packages/forge-c-hi`) is Apache-2.0. At runtime it depends only on the Python standard library.
The GPL tools are invoked as separate processes and are never linked or redistributed.

## Commands

```sh
uv venv apm-venv --python 3.13 && VIRTUAL_ENV=apm-venv uv pip install apm-cli
uv venv ~/.local/share/forge-c-hi/venv310 --python /usr/bin/python3.10 && VIRTUAL_ENV=... uv pip install pytest jsonschema
HI_APM=<apm> FORGE_HI_PY=<venv310>/bin/python packages/forge-c-hi/tools/run_tests.sh -rxXs -v
```
