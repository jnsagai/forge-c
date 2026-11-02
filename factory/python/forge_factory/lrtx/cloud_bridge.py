"""Cloud comparison bridge (owner 2026-11-02): the Claude/Codex line answers the SAME structured tasks as the local
Ornith/Qwen line - same runner, packets, validators, gates, time box, revision and phase-by-phase resume - so that only
the model differs ("following exactly the same configuration ... for a fair comparison").

The stack's gateway (inside the profile's loopback-only network namespace) forwards a model's chat requests to this
bridge over a unix socket (a path on the shared filesystem; it crosses the network namespace without opening any
network to the factory). The bridge runs outside the namespace and answers OpenAI-style streamed
`/v1/chat/completions` by model name:

- backend `anthropic`: the owner's Anthropic API (authorized 2026-11-02) through the official SDK; the runner's JSON
  schema becomes `output_config.format`; Claude Opus 5.5 always thinks, so `extra_output_tokens` is added to the
  runner's answer reserve (as the gateway does for the local thinking models);
- backend `openai`: the owner's OpenAI API (authorized 2026-11-02) through the official SDK (the inspector);
- backend `claude-cli` (owner 2026-11-02, "Claude API/Account mode"): the same Claude model through the owner's
  Claude account (Claude Code `claude -p`, claude.ai login, no API key in its environment): no tools, no MCP server, no
  settings, no session kept, an empty working directory; the schema is passed as `--json-schema`. The account mode is
  chosen per call from a mode file (`api` | `account`) the floor's control writes; a call with tools (Fabro's native
  agent nodes) cannot be answered without tools, so it stays on the API and the meter says so;
- backend `codex`: the Codex CLI (`codex exec`, ephemeral, read-only sandbox, empty working directory, no tools needed:
  the packet holds every input), `--output-schema` when the schema meets the strict rules.

Every call is metered (model, backend, wall time, usage, finish reason, schema mode) to a JSONL file. Prompts and answers
are never logged (trace policy: raw prompts/responses OFF by default); the API key is read from the owner's file and
never logged or returned."""
from __future__ import annotations

import argparse
import json
import os
import re
import socketserver
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

SCHEMA = "forge-c/cloud-bridge-call/1"
MODES = ("api", "account")


def read_mode(path: Path | None) -> str:
    """The Claude mode the floor control last set; anything unreadable or unknown is `api` (the authorized default)."""
    if path is None:
        return "api"
    try:
        mode = json.loads(Path(path).read_text()).get("mode")
    except (OSError, ValueError, AttributeError):
        return "api"
    return mode if mode in MODES else "api"


def read_key(path: Path, name: str = "ANTHROPIC_API_KEY") -> str:
    for line in Path(path).read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise ValueError(f"BRIDGE_KEY_MISSING:{name}")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def _schema(body: dict) -> dict | None:
    rf = body.get("response_format") or {}
    if rf.get("type") == "json_schema":
        return (rf.get("json_schema") or {}).get("schema")
    return None


def strict_ok(schema) -> bool:
    """OpenAI strict structured outputs: every object lists all its properties as required and forbids others."""
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            props = schema.get("properties") or {}
            if schema.get("additionalProperties") is not False or set(schema.get("required") or []) != set(props):
                return False
        return all(strict_ok(v) for k, v in schema.items() if k not in ("enum", "const", "required"))
    if isinstance(schema, list):
        return all(strict_ok(v) for v in schema)
    return True


def json_instruction(schema: dict | None) -> str:
    if schema is None:
        return "Answer with ONLY one JSON object."
    return "Answer with ONLY one JSON object that matches this JSON schema:\n" + json.dumps(schema, sort_keys=True)


def anthropic_messages(msgs: list[dict]) -> tuple[str, list[dict]]:
    """OpenAI chat history -> (system, Anthropic messages). Fabro's native agent nodes send tool calls and tool results.
    No thinking block is ever replayed (the history carries none): a history without thinking blocks is always valid
    under the preserved-thinking check, the model answers each turn without the earlier reasoning."""
    system = "\n\n".join(_text(m.get("content")) for m in msgs if m.get("role") == "system")
    out: list[dict] = []

    def add(role: str, blocks: list[dict]) -> None:
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for m in msgs:
        role = m.get("role")
        if role == "user":
            add("user", [{"type": "text", "text": _text(m.get("content"))}])
        elif role == "assistant":
            blocks = [{"type": "text", "text": _text(m.get("content"))}] if _text(m.get("content")) else []
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {"_unparsed_arguments": fn.get("arguments")}
                blocks.append({"type": "tool_use", "id": tc.get("id"), "name": fn.get("name"), "input": args})
            add("assistant", blocks)
        elif role == "tool":
            add("user", [{"type": "tool_result", "tool_use_id": m.get("tool_call_id"), "content": _text(m.get("content"))}])
    return system, out


def anthropic_tools(tools: list[dict] | None) -> list[dict]:
    return [{"name": (t.get("function") or {}).get("name"), "description": (t.get("function") or {}).get("description", ""),
             "input_schema": (t.get("function") or {}).get("parameters") or {"type": "object", "properties": {}}}
            for t in tools or [] if t.get("type") == "function"]


class AnthropicBackend:
    def __init__(self, key: str, client=None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=key, max_retries=2)
        self.client = client

    def answer(self, body: dict, cfg: dict) -> dict:
        system, conv = anthropic_messages(body.get("messages") or [])
        schema = _schema(body)
        want = int(body.get("max_tokens") or body.get("max_completion_tokens") or 4096) + int(cfg.get("extra_output_tokens", 0))
        kwargs = {"model": cfg.get("model") or body["model"], "messages": conv,
                  "max_tokens": min(want, int(cfg.get("max_output_tokens", want)))}  # the model's output limit
        tools = anthropic_tools(body.get("tools"))
        if tools and body.get("tool_choice") != "none":  # forced tool_choice 400s on Opus 5.5: only auto is sent
            kwargs["tools"] = tools
        oc = {"effort": cfg.get("effort", "medium")}
        mode = "json_schema" if schema is not None else "none"
        if schema is not None:
            oc["format"] = {"type": "json_schema", "schema": schema}
        try:
            msg = self._send(kwargs, oc, system)
        except Exception as exc:  # noqa: BLE001 - a rejected schema keyword: plain JSON, the runner validates anyway
            if schema is None or getattr(exc, "status_code", None) != 400:
                raise
            oc.pop("format")
            mode = "prompt_schema_fallback"
            msg = self._send(kwargs, oc, (system + "\n\n" if system else "") + json_instruction(schema))
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        calls = [{"id": b.id, "type": "function", "function": {"name": b.name, "arguments": json.dumps(b.input)}}
                 for b in msg.content if getattr(b, "type", None) == "tool_use"]
        u = msg.usage
        read, write = (getattr(u, "cache_read_input_tokens", 0) or 0), (getattr(u, "cache_creation_input_tokens", 0) or 0)
        prompt = (u.input_tokens or 0) + read + write
        price = cfg.get("usd_per_mtok") or {}
        cost = None
        if price:
            cost = round(((u.input_tokens or 0) * price.get("input", 0) + read * price.get("cache_read", 0)
                          + write * price.get("cache_write", 0) + (u.output_tokens or 0) * price.get("output", 0)) / 1e6, 6)
        finish = "length" if msg.stop_reason == "max_tokens" else "tool_calls" if calls else "stop"
        return {"text": text, "finish": finish, "tool_calls": calls,
                "usage": {"prompt_tokens": prompt, "completion_tokens": u.output_tokens or 0,
                          "total_tokens": prompt + (u.output_tokens or 0), "cache_read_tokens": read,
                          "cache_write_tokens": write, **({"cost_usd": cost} if cost is not None else {})},
                "schema_mode": mode, "stop_reason": msg.stop_reason}

    def _send(self, kwargs: dict, oc: dict, system: str):
        extra = {"system": system} if system else {}
        with self.client.messages.stream(**kwargs, output_config=oc, **extra) as stream:
            return stream.get_final_message()


class OpenAIBackend:
    """Owner 2026-11-02 ("use also openai API"): the inspector through the OpenAI API (official SDK). The runner's
    request is already OpenAI-shaped: messages and tools pass through; the schema is strict only when it qualifies."""

    def __init__(self, key: str, client=None):
        if client is None:
            import openai

            client = openai.OpenAI(api_key=key, max_retries=2)
        self.client = client

    def answer(self, body: dict, cfg: dict) -> dict:
        schema = _schema(body)
        want = int(body.get("max_tokens") or body.get("max_completion_tokens") or 4096) + int(cfg.get("extra_output_tokens", 0))
        kw = {"model": cfg.get("model") or body["model"], "messages": body.get("messages") or [],
              "max_completion_tokens": min(want, int(cfg.get("max_output_tokens", want)))}
        if cfg.get("reasoning_effort"):
            kw["reasoning_effort"] = cfg["reasoning_effort"]
        if body.get("tools"):
            kw["tools"] = body["tools"]
            if body.get("tool_choice"):
                kw["tool_choice"] = body["tool_choice"]
        mode = "none"
        if schema is not None:
            kw["response_format"] = {"type": "json_schema", "json_schema": {"name": "packet_output", "strict": strict_ok(schema),
                                                                            "schema": schema}}
            mode = "json_schema_strict" if strict_ok(schema) else "json_schema"
        try:
            r = self.client.chat.completions.create(**kw)
        except Exception as exc:  # noqa: BLE001 - a rejected schema: JSON object with the schema in the prompt
            if schema is None or getattr(exc, "status_code", None) != 400:
                raise
            kw["response_format"] = {"type": "json_object"}
            kw["messages"] = list(kw["messages"]) + [{"role": "system", "content": json_instruction(schema)}]
            mode = "prompt_schema_fallback"
            r = self.client.chat.completions.create(**kw)
        ch = r.choices[0]
        calls = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                 for tc in (ch.message.tool_calls or [])]
        u = r.usage
        cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", None)
        reasoning = getattr(getattr(u, "completion_tokens_details", None), "reasoning_tokens", None)
        usage = {"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens, "total_tokens": u.total_tokens,
                 "cached_prompt_tokens": cached, "reasoning_tokens": reasoning}
        price = cfg.get("usd_per_mtok") or {}
        if price:
            usage["cost_usd"] = round(((u.prompt_tokens - (cached or 0)) * price.get("input", 0) + (cached or 0)
                                       * price.get("cache_read", 0) + u.completion_tokens * price.get("output", 0)) / 1e6, 6)
        finish = ch.finish_reason if ch.finish_reason in ("stop", "length", "tool_calls") else "stop"
        return {"text": ch.message.content or "", "finish": finish, "tool_calls": calls, "schema_mode": mode, "usage": usage}


class ClaudeCliBackend:
    """Claude through the owner's Claude account: `claude -p` (print mode), structured output, nothing else. The
    API key is removed from the CLI's environment so the account login is what answers (`--bare` would require a key).
    The CLI's `total_cost_usd` is a list-price equivalent, not an API charge: it is metered as `list_cost_usd`."""

    def __init__(self, run=subprocess.run, exe: str = "claude"):
        self.run, self.exe = run, exe

    def answer(self, body: dict, cfg: dict) -> dict:
        if body.get("tools"):
            raise ValueError("CLAUDE_CLI_NO_TOOLS")  # the bridge keeps tool calls on the API
        schema = _schema(body)
        msgs = body.get("messages") or []
        system = "\n\n".join(_text(m.get("content")) for m in msgs if m.get("role") == "system")
        turns = [m for m in msgs if m.get("role") != "system"]
        if len(turns) == 1 and turns[0].get("role") == "user":
            prompt = _text(turns[0].get("content"))
        else:
            prompt = "\n\n".join(f"[{m.get('role')}]\n{_text(m.get('content'))}" for m in turns)
        mode = "json_schema" if schema is not None else "none"
        if schema is None and (body.get("response_format") or {}).get("type") == "json_object":
            prompt += "\n\n" + json_instruction(None)
        with tempfile.TemporaryDirectory(prefix="forge-claude-") as td:
            sp = Path(td) / "system.txt"
            sp.write_text(system or "Answer the task.")
            argv = [self.exe, "-p", "--model", cfg.get("model") or body["model"], "--output-format", "json",
                    "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
                    "--no-session-persistence", "--effort", cfg.get("effort", "medium"), "--system-prompt-file", str(sp)]
            if schema is not None:
                argv += ["--json-schema", json.dumps(schema)]
            env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
            p = self.run(argv, input=prompt, text=True, capture_output=True, env=env, cwd=td,
                         timeout=int(cfg.get("timeout_s", 3600)))
        try:
            out = json.loads(p.stdout or "{}")
        except ValueError:
            out = {}
        if p.returncode != 0 or out.get("is_error") or out.get("type") != "result":
            raise RuntimeError(f"CLAUDE_CLI_FAILED:rc{p.returncode}:{str(out.get('subtype') or out.get('api_error_status'))[:40]}")
        so = out.get("structured_output")
        text = json.dumps(so) if schema is not None and so is not None else str(out.get("result") or "")
        u = out.get("usage") or {}
        read, write = int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0)
        prompt_t = int(u.get("input_tokens") or 0) + read + write
        done = int(u.get("output_tokens") or 0)
        usage = {"prompt_tokens": prompt_t, "completion_tokens": done, "total_tokens": prompt_t + done,
                 "cache_read_tokens": read, "cache_write_tokens": write,
                 "reasoning_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
                 "list_cost_usd": out.get("total_cost_usd"), "billing": "account"}
        finish = "length" if out.get("stop_reason") == "max_tokens" else "stop"
        return {"text": text, "finish": finish, "tool_calls": [], "schema_mode": mode, "usage": usage,
                "stop_reason": out.get("stop_reason")}


class CodexBackend:
    def __init__(self, codex_home: str | None = None, run=subprocess.run):
        self.codex_home, self.run = codex_home, run

    def answer(self, body: dict, cfg: dict) -> dict:
        schema = _schema(body)
        parts = [f"[{m.get('role')}]\n{_text(m.get('content'))}" for m in body.get("messages") or []]
        prompt = "\n\n".join(parts) + "\n\n" + json_instruction(schema)
        with tempfile.TemporaryDirectory(prefix="forge-codex-") as td:
            out, sch = Path(td) / "last-message.txt", Path(td) / "schema.json"
            argv = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
                    "--json", "-C", td, "-o", str(out)]
            if cfg.get("model"):
                argv += ["-m", cfg["model"]]
            mode = "prompt_schema"
            if schema is not None and strict_ok(schema):
                sch.write_text(json.dumps(schema))
                argv += ["--output-schema", str(sch)]
                mode = "output_schema"
            env = {**os.environ, **({"CODEX_HOME": self.codex_home} if self.codex_home else {})}
            p = self.run(argv + ["-"], input=prompt, text=True, capture_output=True, env=env,
                         timeout=int(cfg.get("timeout_s", 1800)))
            text = out.read_text() if out.is_file() else ""
        usage = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        for line in (p.stdout or "").splitlines():  # --json events: usage on turn.completed (includes Codex's own prompt)
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict) and ev.get("type") == "turn.completed" and isinstance(ev.get("usage"), dict):
                u = ev["usage"]
                usage = {"prompt_tokens": u.get("input_tokens"), "completion_tokens": u.get("output_tokens"),
                         "cached_prompt_tokens": u.get("cached_input_tokens"),
                         "reasoning_tokens": u.get("reasoning_output_tokens")}
                usage["total_tokens"] = (usage["prompt_tokens"] or 0) + (usage["completion_tokens"] or 0)
        if p.returncode != 0 and not text:
            raise RuntimeError(f"CODEX_EXEC_FAILED:rc{p.returncode}")
        return {"text": text, "finish": "stop", "schema_mode": mode, "usage": usage}


class Bridge:
    def __init__(self, models: dict, backends: dict, meter: Path, mode_file: Path | None = None):
        self.models, self.backends, self.meter = models, backends, Path(meter)
        self.mode_file = Path(mode_file) if mode_file else None
        self.lock = threading.Lock()

    def route(self, body: dict, cfg: dict) -> tuple[str, dict]:
        """Backend for this call. An `anthropic` model goes to `claude-cli` while the mode file says `account`, except a
        call with tools (kept on the API, recorded as `account_fallback`)."""
        backend = cfg["backend"]
        note: dict = {}
        if backend == "anthropic" and "claude-cli" in self.backends:
            mode = read_mode(self.mode_file)
            note["claude_mode"] = mode
            if mode == "account":
                if body.get("tools"):
                    note["account_fallback"] = "tool_calls_on_api"
                else:
                    backend = "claude-cli"
        return backend, note

    def complete(self, body: dict) -> dict:
        name = body.get("model")
        cfg = self.models.get(name) or {}
        t0 = time.monotonic()
        rec = {"schema": SCHEMA, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": name,
               "backend": cfg.get("backend")}
        try:
            if not cfg:
                raise KeyError(f"BRIDGE_MODEL_UNKNOWN:{name}")
            backend, note = self.route(body, cfg)
            rec.update({"backend": backend, **note})
            res = self.backends[backend].answer(body, cfg)
            rec.update({"ok": True, "finish": res["finish"], "usage": res["usage"], "schema_mode": res["schema_mode"],
                        "answer_chars": len(res["text"])})
            return res
        except Exception as exc:
            rec.update({"ok": False, "error": f"{type(exc).__name__}:{str(exc)[:160]}"})
            raise
        finally:
            rec["wall_ms"] = round((time.monotonic() - t0) * 1000, 1)
            with self.lock:
                self.meter.parent.mkdir(parents=True, exist_ok=True)
                with self.meter.open("a") as f:
                    f.write(json.dumps(rec, sort_keys=True) + "\n")


def handler_for(bridge: Bridge):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a):  # no request logging (paths and bodies stay out of logs)
            return

        def address_string(self):
            return "unix"

        def _json(self, code: int, obj: dict) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802 - http.server API
            if self.path in ("/health", "/v1/health"):
                return self._json(200, {"status": "ok"})
            if self.path == "/v1/models":
                return self._json(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in bridge.models]})
            if self.path == "/api/version":
                return self._json(200, {"version": "forge-cloud-bridge"})
            return self._json(404, {"error": {"type": "not_found"}})

        def do_POST(self):  # noqa: N802 - http.server API
            if self.path not in ("/v1/chat/completions", "/chat/completions"):
                return self._json(404, {"error": {"type": "not_found"}})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                res = bridge.complete(body)
            except KeyError as exc:
                return self._json(400, {"error": {"type": "bridge_model_unknown", "message": str(exc)[:200]}})
            except Exception as exc:  # noqa: BLE001 - one failed upstream call is the runner's finding, not a crash
                return self._json(502, {"error": {"type": "bridge_upstream_failed", "message": type(exc).__name__}})
            delta = {"role": "assistant", "content": res["text"]}
            if res.get("tool_calls"):
                delta["tool_calls"] = [{"index": i, **c} for i, c in enumerate(res["tool_calls"])]
            chunks = [{"choices": [{"index": 0, "delta": delta}]},
                      {"choices": [{"index": 0, "delta": {}, "finish_reason": res["finish"]}]}]
            if body.get("stream"):
                chunks.append({"choices": [], "usage": res["usage"]})
                payload = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
                data = payload.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return None
            return self._json(200, {"object": "chat.completion", "model": body.get("model"), "usage": res["usage"],
                                    "choices": [{"index": 0, "message": {"role": "assistant", "content": res["text"],
                                                                         **({"tool_calls": res["tool_calls"]}
                                                                            if res.get("tool_calls") else {})},
                                                 "finish_reason": res["finish"]}]})

    return Handler


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve(socket_path: Path, bridge: Bridge) -> UnixServer:
    socket_path = Path(socket_path)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()
    srv = UnixServer(str(socket_path), handler_for(bridge))
    os.chmod(socket_path, 0o600)
    return srv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.lrtx.cloud_bridge")
    ap.add_argument("command", choices=["serve"])
    ap.add_argument("--socket", required=True, type=Path)
    ap.add_argument("--models", required=True, help="JSON: model name -> {backend, model?, effort?, extra_output_tokens?}")
    ap.add_argument("--meter", required=True, type=Path)
    ap.add_argument("--key-file", type=Path, default=Path.home() / ".config/forge-c/anthropic-api.env")
    ap.add_argument("--openai-key-file", type=Path, default=Path.home() / ".config/forge-c/openai-api.env")
    ap.add_argument("--codex-home")
    ap.add_argument("--mode-file", type=Path, help="JSON {mode: api|account} written by the floor control; per call")
    a = ap.parse_args(argv)
    models = json.loads(a.models)
    backends = {}
    if any(c["backend"] == "anthropic" for c in models.values()):
        backends["anthropic"] = AnthropicBackend(read_key(a.key_file))
    if any(c["backend"] == "openai" for c in models.values()):
        backends["openai"] = OpenAIBackend(read_key(a.openai_key_file, "OPENAI_API_KEY"))
    if any(c["backend"] == "codex" for c in models.values()):
        backends["codex"] = CodexBackend(a.codex_home)
    if a.mode_file is not None and "anthropic" in backends:
        backends["claude-cli"] = ClaudeCliBackend()
    srv = serve(a.socket, Bridge(models, backends, a.meter, a.mode_file))
    try:
        srv.serve_forever()
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
