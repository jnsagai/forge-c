"""Per-node model exchange log for optimization (owner 2026-11-08: "a complete log between the exchange tokens of the
request and the response for all the model's interactions for a specific run or for all the runs ... organized per node,
to see how I can optimize each node").

Read-only and model-free. Source: the line's own Fabro store (run_events, opened mode=ro), which already records, per
run -> node -> visit -> session, every model call (start, first output, reply text, token usage with the context
breakdown system_prompt/tools/mcp_tools/skills/conversation), every tool call (arguments) and its result (output plus
Fabro's retained/omitted byte counts). Nothing in the line, the gateway or any signed control changes.

Not available by design: the model's hidden reasoning text (FR-025; the gateway strips it before Fabro sees it - only
its token count is kept) and the exact system prompt text (Fabro records its token count, not its text). Any
reasoning/thinking field that would appear is dropped, and secrets are redacted (events.redact) before writing.

PRIVATE OUTPUT: transcripts contain prompt and tool bodies, including authorized private vendor inputs. Never publish,
commit or attach them to a public export.

  python -m forge_factory.lrtx.model_exchanges export --db FABRO.sqlite3 --out DIR [--run ID | --wo TEXT] [--incremental]
  python -m forge_factory.lrtx.model_exchanges runs --db FABRO.sqlite3
"""

# ruff: noqa: E501 - report text and tables read better unwrapped
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

from ..events.redact import redact_obj

SCHEMA = "forge-c/model-exchanges/1"
HIDDEN = re.compile(r"(?i)^(reasoning|reasoning_content|reasoning_details|thinking|thought|thoughts)$")
OVERHEAD = ("system_prompt", "tools", "mcp_tools", "skills")
MD_OUTPUT_CHARS = 4000  # readable transcript only; the .jsonl keeps every retained byte


def _clean(obj):
    """Drop hidden-reasoning fields (never persisted, FR-025), then redact secrets."""

    def drop(o):
        if isinstance(o, dict):
            return {k: drop(v) for k, v in o.items() if not (isinstance(k, str) and HIDDEN.match(k))}
        if isinstance(o, list):
            return [drop(v) for v in o]
        return o

    return redact_obj(drop(obj))[0]


def _ro(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    c.execute("PRAGMA query_only=ON")
    return c


def _ms(ts: str | None) -> float | None:
    if not ts:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None


def _d(a, b):
    return round(b - a) if a is not None and b is not None else None


def runs(c: sqlite3.Connection) -> list[dict]:
    rows = c.execute(
        "SELECT id, title, workflow_name, status, created_at_ms, completed_at_ms, input_tokens, output_tokens, "
        "reasoning_tokens, cache_read_tokens FROM runs ORDER BY created_at_ms"
    ).fetchall()
    out = []
    for r in rows:
        title = r[1] or ""
        m = re.search(r"\bWO-[A-Z0-9-]+", title)
        out.append(
            {
                "run_id": r[0],
                "wo": m.group(0) if m else None,
                "title": title[:160],
                "workflow": r[2],
                "status": r[3],
                "created_ms": r[4],
                "completed_ms": r[5],
                "tokens": {"input": r[6], "output": r[7], "reasoning": r[8], "cache_read": r[9]},
            }
        )
    return out


def collect(c: sqlite3.Connection, run_id: str) -> dict:
    """One run as nodes -> visits -> model turns, each turn with its tool calls and results."""
    visits: dict[str, dict] = {}
    turn_of: dict[str, dict] = {}  # session -> current turn
    tools_of: dict[str, dict] = {}  # tool_call_id -> call
    for node, stage, session, name, ej in c.execute(
        "SELECT node_id, stage_id, session_id, event_name, event_json FROM run_events WHERE run_id=? ORDER BY seq", (run_id,)
    ):
        if not stage:
            continue
        e = json.loads(ej)
        p = e.get("properties") or {}
        ev = p.get("event") if isinstance(p.get("event"), dict) else {}
        ts = e.get("ts") or p.get("timestamp")
        v = visits.setdefault(
            stage,
            {
                "node": node,
                "stage": stage,
                "kind": "agent",
                "visit": int(stage.rsplit("@", 1)[1]) if re.search(r"@\d+$", stage) else p.get("visit"),
                "turns": [],
                "tools_available": [],
                "skills": [],
                "warnings": [],
                "loops": 0,
                "compactions": 0,
                "errors": [],
                "prompt": None,
                "status": None,
                "timing": None,
                "started": None,
                "completed": None,
                "model": None,
            },
        )
        if name == "stage.started":
            v["started"] = ts
        elif name in ("stage.completed", "stage.failed"):
            v["completed"], v["status"] = ts, p.get("status") or ("failed" if name == "stage.failed" else None)
            v["timing"] = p.get("timing")
        elif name == "stage.prompt":
            v["model"] = p.get("model")
        elif name == "agent.input":
            v["prompt"] = (ev.get("UserInput") or {}).get("text")
        elif name == "agent.tools.available":
            v["tools_available"] = [
                {
                    "name": t.get("name"),
                    "category": t.get("category"),
                    "source": (t.get("source") or {}).get("kind"),
                    "description_chars": len(t.get("description") or ""),
                }
                for t in p.get("tools") or []
            ]
        elif name == "agent.skill.activated":
            v["skills"].append((ev.get("SkillActivated") or {}).get("skill_name"))
        elif name == "agent.llm.started":
            t = {
                "i": len(v["turns"]) + 1,
                "session": session,
                "started": ts,
                "first_output": None,
                "replied": None,
                "requested_model": (ev.get("LlmRequestStarted") or {}).get("requested_model"),
                "text": None,
                "usage": None,
                "context": None,
                "tool_calls": [],
                "warnings": [],
            }
            v["turns"].append(t)
            turn_of[session] = t
        elif name == "agent.llm.first_output" and session in turn_of:
            turn_of[session]["first_output"] = ts
        elif name == "agent.message" and session in turn_of:
            m = ev.get("AssistantMessage") or {}
            t = turn_of[session]
            cw = m.get("context_window") or {}
            t.update(
                replied=ts,
                text=m.get("text"),
                model=m.get("model"),
                usage=(m.get("usage") or {}).get("tokens"),
                tool_call_count=m.get("tool_call_count"),
                context={b.get("category"): b.get("tokens") for b in cw.get("breakdown") or []} or None,
                prompt_tokens=cw.get("input_tokens"),
                context_window_tokens=cw.get("context_window_tokens"),
            )
        elif name == "agent.tool.started":
            s = ev.get("ToolCallStarted") or {}
            call = {
                "id": s.get("tool_call_id"),
                "tool": s.get("tool_name"),
                "arguments": s.get("arguments"),
                "started": ts,
                "completed": None,
                "is_error": None,
                "output": None,
            }
            tools_of[call["id"]] = call
            (turn_of[session]["tool_calls"] if session in turn_of else v.setdefault("orphan_tool_calls", [])).append(call)
        elif name == "agent.tool.completed":
            s = ev.get("ToolCallCompleted") or {}
            call = tools_of.get(s.get("tool_call_id"))
            if call is not None:
                call.update(
                    completed=ts,
                    is_error=s.get("is_error"),
                    output=s.get("output"),
                    output_bytes={k: s.get("output_bytes_" + k) for k in ("observed", "retained", "omitted")},
                )
        elif name == "agent.warning":
            w = ev.get("Warning") or {}
            item = {"kind": w.get("kind"), "message": (w.get("message") or "")[:300]}
            (turn_of[session]["warnings"] if session in turn_of else v["warnings"]).append(item)
        elif name == "agent.loop.detected":
            v["loops"] += 1
        elif name == "agent.compaction.started":
            v["compactions"] += 1
        elif name == "agent.error":
            v["errors"].append(json.dumps(ev or p)[:400])
    ai = {k: v for k, v in visits.items() if v["turns"]}
    for v in ai.values():
        for t in v["turns"]:
            s, f, r = _ms(t["started"]), _ms(t["first_output"]), _ms(t["replied"])
            # the line gateway buffers a reply before forwarding it, so Fabro's first output arrives with the full reply:
            # the prompt-processing / generation split is not observable here, only the call's total time
            t["timing_ms"] = {
                "total": _d(s, r),
                "first_output_as_seen_by_fabro": _d(s, f),
                "tools": sum(_d(_ms(x["started"]), _ms(x["completed"])) or 0 for x in t["tool_calls"]),
            }
    return _clean({"schema": SCHEMA, "run_id": run_id, "visits": ai})


def collect_structured(ws: Path, captured: Path | None = None) -> dict:
    """Structured command nodes (e.g. the SWE.1 author) call the gateway from Python, outside Fabro's agent loop. Their
    workspace keeps, per task, every attempt's usage, timing, finish reason, errors and request size/hash, and the final
    output document - not the request text (see the module docstring)."""
    lrtx = Path(ws) / ".forge-run/lrtx"
    visits: dict[str, dict] = {}
    for phase_dir in sorted(x for x in lrtx.glob("*") if (x / "packets").is_dir()):
        roles = {}
        dev = phase_dir / "development-execution.json"
        if dev.is_file():
            for key in json.loads(dev.read_text()).get("calls") or {}:
                role, _, task = key.partition(":")
                roles[task] = role
        for pk in sorted((phase_dir / "packets").glob("*.json")):
            d = json.loads(pk.read_text())
            task = d.get("task") or pk.stem.replace("__", ":")
            node = roles.get(task) or f"{phase_dir.name}-structured"
            v = visits.setdefault(
                node,
                {
                    "node": node,
                    "stage": f"{node}@1",
                    "kind": "structured",
                    "visit": 1,
                    "phase": phase_dir.name,
                    "turns": [],
                    "tasks": [],
                    "status": None,
                },
            )
            tries = [a for a in (d.get("history") or []) if isinstance(a, dict) and ("usage" in a or "accounting" in a)]
            tries += [a for a in (d.get("attempts") or []) if isinstance(a, dict)]
            for n, a in enumerate(tries, 1):
                u = a.get("usage") or {}
                acc = (a.get("accounting") or {}).get("complete_serialized_request") or {}
                prompt, cached = u.get("prompt_tokens"), (u.get("prompt_tokens_details") or {}).get("cached_tokens")
                v["turns"].append(
                    {
                        "i": len(v["turns"]) + 1,
                        "task": task,
                        "attempt": n,
                        "finish_reason": a.get("finish_reason"),
                        "errors": a.get("errors") or [],
                        "schema_mode": a.get("schema_mode"),
                        "prompt_tokens": prompt,
                        "cached_tokens": cached,
                        "usage": {
                            "input": (prompt - (cached or 0)) if prompt is not None else None,
                            "output": u.get("completion_tokens"),
                            "reasoning": None,
                        },
                        "request": {
                            "serialized_bytes": acc.get("serialized_bytes"),
                            "sha256": acc.get("sha256"),
                            "text": "not recorded",
                        },
                        "timing_ms": {"total": a.get("wall_ms")},
                        "tool_calls": [],
                        "warnings": [],
                    }
                )
            v["tasks"].append(
                {
                    "task": task,
                    "status": d.get("status"),
                    "errors": d.get("errors"),
                    "output": d.get("doc"),
                    "rework": d.get("rework"),
                    "reused": d.get("reused"),
                }
            )
    # owner 2026-11-08: complete request and reply of each structured call, when the capture switch was on (structured.py)
    for f in sorted(captured.glob("*/*.json")) if captured and captured.is_dir() else []:
        try:
            rec = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        node = rec.get("role") or f"{rec.get('phase')}-structured"
        v = visits.setdefault(
            node,
            {
                "node": node,
                "stage": f"{node}@1",
                "kind": "structured",
                "visit": 1,
                "phase": rec.get("phase"),
                "turns": [],
                "tasks": [],
            },
        )
        v.setdefault("captured", []).append(rec)
    for v in visits.values():
        caps = sorted(v.get("captured") or [], key=lambda r: r.get("at") or "")
        if caps and not v["turns"]:  # a role without packets (e.g. an inspector): its calls come from the capture alone
            for n, rec in enumerate(caps, 1):
                reply = rec.get("reply") or {}
                u = reply.get("usage") or {}
                prompt, cached = u.get("prompt_tokens"), (u.get("prompt_tokens_details") or {}).get("cached_tokens")
                v["turns"].append(
                    {
                        "i": n,
                        "task": rec.get("task"),
                        "attempt": 1,
                        "finish_reason": reply.get("finish_reason"),
                        "errors": reply.get("errors") or [],
                        "prompt_tokens": prompt,
                        "cached_tokens": cached,
                        "usage": {
                            "input": (prompt - (cached or 0)) if prompt is not None else None,
                            "output": u.get("completion_tokens"),
                            "reasoning": None,
                        },
                        "timing_ms": {"total": reply.get("wall_ms")},
                        "tool_calls": [],
                        "warnings": [],
                    }
                )
        v["captured"] = caps
        if v["tasks"]:
            v["status"] = "valid" if all(x["status"] == "VALID" for x in v["tasks"]) else "has invalid tasks"
        else:
            v["status"] = "captured"
    return _clean(visits)


def visit_stats(v: dict) -> dict:
    turns = v["turns"]
    u = [t.get("usage") or {} for t in turns]
    prompt = [
        t.get("prompt_tokens") if t.get("prompt_tokens") is not None else (x.get("input") or 0)
        for t, x in zip(turns, u, strict=True)
    ]
    processed = [x.get("input") or 0 for x in u]
    overhead = [sum((t.get("context") or {}).get(k) or 0 for k in OVERHEAD) for t in turns]
    calls = [x for t in turns for x in t["tool_calls"]]
    sig = Counter((x["tool"], json.dumps(x.get("arguments"), sort_keys=True)) for x in calls)
    resend = Counter()  # each tool result is carried in every later turn of the visit: an estimate of its prompt cost
    for i, t in enumerate(turns):
        for x in t["tool_calls"]:
            resend[x["tool"]] += len(x.get("output") or "") * (len(turns) - i - 1)
    out_tok = sum(x.get("output") or 0 for x in u)
    visible = (
        sum(len(t.get("text") or "") for t in turns)
        + sum(len(json.dumps(x.get("arguments"))) for x in calls)
        + sum(len(json.dumps(task.get("output"))) for task in v.get("tasks") or [] if task.get("output") is not None)
        + (0 if v.get("tasks") else sum(len((r.get("reply") or {}).get("text") or "") for r in v.get("captured") or []))
    )
    return {
        "kind": v.get("kind", "agent"),
        "turns": len(turns),
        "prompt_tokens": sum(prompt),
        "processed_tokens": sum(processed),
        "cache_reused_tokens": sum(prompt) - sum(processed),
        "output_tokens": out_tok,
        "reasoning_tokens": sum(x.get("reasoning") or 0 for x in u),
        "visible_output_chars": visible,
        "first_turn_prompt": prompt[0] if prompt else 0,
        "last_turn_prompt": prompt[-1] if prompt else 0,
        "max_prompt": max(prompt or [0]),
        "fixed_overhead_tokens": sum(overhead),
        "context_by_category": dict(
            sum((Counter({k: v2 or 0 for k, v2 in (t.get("context") or {}).items()}) for t in turns), Counter())
        ),
        "tool_calls": len(calls),
        "tool_errors": sum(1 for x in calls if x.get("is_error")),
        "tools_used": dict(Counter(x["tool"] for x in calls)),
        "tools_offered": len(v.get("tools_available") or []),
        "tools_never_used": sorted({t["name"] for t in v.get("tools_available") or []} - {x["tool"] for x in calls}),
        "duplicate_tool_calls": sum(n - 1 for n in sig.values() if n > 1),
        "tool_output_chars": sum(len(x.get("output") or "") for x in calls),
        "tool_output_omitted_bytes": sum(((x.get("output_bytes") or {}).get("omitted") or 0) for x in calls),
        "resent_tool_output_chars_est": dict(resend.most_common(5)),
        "empty_replies": sum(
            1 for t in turns if v.get("kind") == "agent" and not (t.get("text") or "").strip() and not t["tool_calls"]
        ),
        "retries": sum(1 for t in turns if (t.get("attempt") or 1) > 1),
        "truncated_outputs": sum(1 for t in turns if t.get("finish_reason") == "length"),
        "failed_attempts": sum(1 for t in turns if t.get("errors")),
        "model_ms": sum((t["timing_ms"].get("total") or 0) for t in turns),
        "tool_ms": sum((t["timing_ms"].get("tools") or 0) for t in turns),
        "warnings": len(v.get("warnings") or []) + sum(len(t["warnings"]) for t in turns),
        "loops": v.get("loops", 0),
        "compactions": v.get("compactions", 0),
        "status": v.get("status"),
        "captured_calls": len(v.get("captured") or []),
    }


def _fence(text: str) -> str:
    text = (
        text
        if len(text) <= MD_OUTPUT_CHARS
        else text[:MD_OUTPUT_CHARS] + f"\n... [{len(text) - MD_OUTPUT_CHARS} more chars in the .jsonl]"
    )
    return "````text\n" + text.replace("````", "` ` ` `") + "\n````"


def _captured_block(rec: dict) -> list[str]:
    """One captured structured call: every request message, the request parameters and the reply text."""
    reply = rec.get("reply") or {}
    u = reply.get("usage") or {}
    lines = [
        f"### Captured call · {rec.get('at')} · {u.get('prompt_tokens')} prompt / {u.get('completion_tokens')} output tokens · "
        f"{(reply.get('wall_ms') or 0) / 1000:.0f} s · finish {reply.get('finish_reason')}",
        "",
    ]
    for m in (rec.get("request") or {}).get("messages") or []:
        content = m.get("content")
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        lines += [f"**{m.get('role')}**", "", _fence(text), ""]
    params = {k: x for k, x in (rec.get("request") or {}).items() if k != "messages"}
    found = "; ".join(reply.get("errors") or [])[:300]
    lines += [
        "Request parameters:",
        "",
        "```json\n" + json.dumps(params, indent=1, ensure_ascii=False)[:MD_OUTPUT_CHARS] + "\n```",
        "",
        "**Reply**" + (f" (findings: {found})" if found else ""),
        "",
        _fence(reply.get("text") or "(no reply text)"),
        "",
    ]
    return lines


def transcript(meta: dict, v: dict, st: dict) -> str:
    out = [
        f"# {v['node']} · visit {v.get('visit')} · {meta.get('wo') or meta['run_id']}",
        "",
        f"PRIVATE - model exchange transcript. Run `{meta['run_id']}`, status {st['status']}. {st['turns']} model calls, "
        f"prompts {st['prompt_tokens']:,} tokens ({st['cache_reused_tokens']:,} reused from the prompt cache), output "
        f"{st['output_tokens']:,} tokens for {st['visible_output_chars']:,} visible chars (hidden reasoning text is not recorded), "
        f"{st['tool_calls']} tool calls. Model time {st['model_ms'] / 1000:,.0f} s, tool time {st['tool_ms'] / 1000:,.0f} s.",
        "",
    ]
    if v.get("kind") == "structured":
        caps = v.get("captured") or []
        out += [
            f"Structured node: {len(caps)} calls captured with their full request and reply (capture switch on); calls made "
            "while the switch was off keep only their size and hash. Each task's attempts and final output follow.",
            "",
        ]
        shown: set[int] = set()
        for task in v.get("tasks") or []:
            rows = [t for t in v["turns"] if t.get("task") == task["task"]]
            out += [
                f"## Task `{task['task']}` · {task['status']}",
                "",
                "| attempt | prompt | cached | output | finish | time s | errors |",
                "|---:|---:|---:|---:|---|---:|---|",
            ]
            out += [
                f"| {t['attempt']} | {t.get('prompt_tokens')} | {t.get('cached_tokens')} | {(t.get('usage') or {}).get('output')} | "
                f"{t.get('finish_reason')} | {(t['timing_ms'].get('total') or 0) / 1000:.0f} | {'; '.join(t.get('errors') or [])[:200]} |"
                for t in rows
            ]
            out += ["", "Final output:", "", _fence(json.dumps(task.get("output"), indent=1, ensure_ascii=False)), ""]
            for i, rec in enumerate(caps):
                if rec.get("task") == task["task"]:
                    out += _captured_block(rec)
                    shown.add(i)
        rest = [rec for i, rec in enumerate(caps) if i not in shown]
        if rest:
            out += ["## Captured calls", ""]
            for rec in rest:
                out += [f"Task `{rec.get('task')}`", ""] + _captured_block(rec)
        return "\n".join(out)
    out += [
        "## Node input (the user message the node starts from)",
        "",
        _fence(v.get("prompt") or "(not recorded)"),
        "",
        f"Tools offered ({len(v.get('tools_available') or [])}): " + ", ".join(t["name"] for t in v.get("tools_available") or []),
        "",
    ]
    for t in v["turns"]:
        u, ctx, tm = t.get("usage") or {}, t.get("context") or {}, t["timing_ms"]
        out += [
            f"## Turn {t['i']} · {(t.get('started') or '')[:19]}Z",
            "",
            f"Request: prompt {t.get('prompt_tokens')} tokens (" + ", ".join(f"{k} {n}" for k, n in ctx.items()) + f"), of which "
            f"{u.get('input')} processed and the rest reused from the cache. Reply: {u.get('output')} output tokens "
            f"({u.get('reasoning')} reported as reasoning). Model call {tm.get('total')} ms.",
            "",
        ]
        if (t.get("text") or "").strip():
            out += ["**Model reply**", "", _fence(t["text"]), ""]
        for x in t["tool_calls"]:
            ob = x.get("output_bytes") or {}
            out += [
                f"**Tool call `{x['tool']}`**"
                + (" (error)" if x.get("is_error") else "")
                + f" · {_d(_ms(x['started']), _ms(x['completed']))} ms",
                "",
                "```json\n" + json.dumps(x.get("arguments"), indent=1, ensure_ascii=False)[:MD_OUTPUT_CHARS] + "\n```",
                "",
                f"Result ({ob.get('retained')} bytes kept"
                + (f", {ob.get('omitted')} omitted by Fabro" if ob.get("omitted") else "")
                + "):",
                "",
                _fence(x.get("output") or ""),
                "",
            ]
        for w in t["warnings"]:
            out += [f"> warning {w['kind']}: {w['message']}", ""]
    return "\n".join(out)


def hints(node: str, agg: dict) -> list[str]:
    """Deterministic, evidence-based optimization pointers for one node across its visits (not model advice)."""
    h, n = [], max(agg["turns"], 1)
    if agg["prompt_tokens"] and agg["fixed_overhead_tokens"]:
        share = agg["fixed_overhead_tokens"] / agg["prompt_tokens"]
        top = sorted(((k, v) for k, v in agg["context_by_category"].items() if k in OVERHEAD), key=lambda kv: -kv[1])
        h.append(
            f"Fixed part of every prompt: {agg['fixed_overhead_tokens'] // n:,} tokens per call ({share:.0%} of all prompt tokens): "
            + ", ".join(f"{k} {v // n:,}" for k, v in top)
            + "."
        )
    conv = agg["context_by_category"].get("conversation", 0)
    if agg["prompt_tokens"] and conv / agg["prompt_tokens"] >= 0.5:
        h.append(
            f"The growing conversation is {conv / agg['prompt_tokens']:.0%} of all prompt tokens; prompts reach {agg['max_prompt']:,} tokens."
        )
    if agg["resent_tool_output_chars_est"]:
        k, v = max(agg["resent_tool_output_chars_est"].items(), key=lambda kv: kv[1])
        h.append(
            f"Largest carried tool output: `{k}` results stay in every later prompt, about {v // 4:,} prompt tokens in total "
            "(estimate: chars/4)."
        )
    if agg["tools_never_used"]:
        h.append(
            f"{len(agg['tools_never_used'])} of the offered tools were never called in any visit (their definitions are in every prompt): "
            + ", ".join(agg["tools_never_used"][:12])
            + (" ..." if len(agg["tools_never_used"]) > 12 else "")
            + "."
        )
    if agg["duplicate_tool_calls"]:
        h.append(
            f"{agg['duplicate_tool_calls']} tool calls repeated an earlier identical call (same tool and arguments) in the same visit."
        )
    if agg["tool_errors"]:
        h.append(f"{agg['tool_errors']} of {agg['tool_calls']} tool calls returned an error.")
    if agg["output_tokens"] and agg["visible_output_chars"] and agg["output_tokens"] > 2 * (agg["visible_output_chars"] / 4):
        h.append(
            f"Generated {agg['output_tokens']:,} tokens for about {agg['visible_output_chars'] // 4:,} tokens of visible output "
            "(chars/4): most generated tokens are hidden reasoning."
        )
    if agg["truncated_outputs"]:
        h.append(f"{agg['truncated_outputs']} calls stopped at the output limit (finish_reason=length).")
    if agg["failed_attempts"] or agg["retries"]:
        h.append(f"{agg['failed_attempts']} calls ended with findings; {agg['retries']} were retries of the same task.")
    if agg["empty_replies"]:
        h.append(f"{agg['empty_replies']} turns produced neither text nor a tool call.")
    if agg["loops"]:
        h.append(f"Fabro detected a loop {agg['loops']} times.")
    if agg["prompt_tokens"]:
        h.append(
            f"Prompt cache: {agg['cache_reused_tokens'] / agg['prompt_tokens']:.0%} of prompt tokens were reused, "
            f"{agg['processed_tokens']:,} processed."
        )
    if agg["model_ms"] and agg["tool_ms"]:
        h.append(f"Time: model {agg['model_ms'] / 1000:,.0f} s, tools {agg['tool_ms'] / 1000:,.0f} s.")
    return h


def _sum(stats: list[dict]) -> dict:
    agg: dict = defaultdict(int)
    agg["context_by_category"], agg["resent_tool_output_chars_est"], agg["tools_used"] = Counter(), Counter(), Counter()
    never = None
    for s in stats:
        for k, v in s.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                agg[k] = max(agg[k], v) if k == "max_prompt" else agg[k] + v
        agg["context_by_category"].update(s["context_by_category"])
        agg["resent_tool_output_chars_est"].update(s["resent_tool_output_chars_est"])
        agg["tools_used"].update(s["tools_used"])
        never = set(s["tools_never_used"]) if never is None else never & set(s["tools_never_used"])
    agg["tools_never_used"] = sorted(never or [])
    agg["kind"] = stats[0]["kind"] if stats else "agent"
    agg["visits"] = len(stats)
    return dict(agg)


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._@-]+", "_", name)[:120]


def _write_visit(rdir: Path, meta: dict, v: dict) -> dict:
    st = visit_stats(v)
    ndir = rdir / _safe(v["node"])
    ndir.mkdir(parents=True, exist_ok=True)
    base = ndir / f"visit-{v.get('visit')}"
    with open(str(base) + ".jsonl", "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "kind": "visit",
                    "run": meta,
                    **{k: x for k, x in v.items() if k not in ("turns", "tasks", "captured")},
                    "stats": st,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        for t in v["turns"]:
            f.write(json.dumps({"kind": "call", **t}, ensure_ascii=False) + "\n")
        for task in v.get("tasks") or []:
            f.write(json.dumps({"kind": "task_output", **task}, ensure_ascii=False) + "\n")
        for rec in v.get("captured") or []:
            f.write(json.dumps({"kind": "captured_call", **rec}, ensure_ascii=False) + "\n")
    Path(str(base) + ".md").write_text(transcript(meta, v, st), encoding="utf-8")
    return {"node": v["node"], "visit": v.get("visit"), **st}


def export(
    db: Path,
    out: Path,
    *,
    run: str | None = None,
    wo: str | None = None,
    incremental: bool = False,
    workorders: Path | None = None,
) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    workorders = workorders or Path(db).resolve().parents[3] / "state/workorders"
    (out / "README.md").write_text(
        "# Model exchanges (PRIVATE)\n\nPer run -> node -> visit model exchange logs, read from the line's Fabro store (agent nodes) and "
        "the order workspaces (structured nodes). They contain prompt and tool bodies, including authorized private vendor inputs: "
        "never publish, commit or attach them to a public export. Hidden reasoning text is not recorded (FR-025); secrets are "
        "redacted.\n\n- `index.md`: all AI nodes, sorted by prompt tokens\n- `by-node/<node>.md`: per-node optimization report across "
        "all exported runs, with links to every visit\n- `nodes.csv`: one row per node\n- `runs/<WO>__<run>/<node>/visit-N.md|.jsonl`: "
        "readable transcript and the full call-by-call record\n"
    )
    state_path = out / ".exported.json"
    done = json.loads(state_path.read_text()) if incremental and state_path.is_file() else {}
    c = _ro(db)
    try:
        every = runs(c)
        newest = {r["wo"]: r["run_id"] for r in every if r["wo"]}  # runs are ordered by creation; the last one wins
        selected = [r for r in every if (not run or r["run_id"] == run) and (not wo or wo in (r["wo"] or "") or wo in r["title"])]
        exported = 0
        for meta in selected:
            final = meta["status"] in ("succeeded", "failed", "cancelled")
            owns_order = bool(meta["wo"]) and newest.get(meta["wo"]) == meta["run_id"]
            # an order's newest run is re-read every time: its structured nodes and captures keep growing after the run ends
            if incremental and final and done.get(meta["run_id"]) == meta["completed_ms"] and not owns_order:
                continue
            visits = list(collect(c, meta["run_id"])["visits"].values())
            if owns_order:  # an order's workspace and captures are shared by all its runs: attached to the newest run only
                ws = workorders / meta["wo"] / "workspace"
                caps = workorders.parent / "model-exchanges/structured" / _safe(meta["wo"])
                if ws.is_dir() or caps.is_dir():
                    visits += list(collect_structured(ws, caps).values())
            done[meta["run_id"]] = meta["completed_ms"] if final else None
            if not visits:
                continue
            rdir = out / "runs" / _safe(f"{meta['wo'] or 'run'}__{meta['run_id']}")
            per_visit = {v["stage"]: _write_visit(rdir, meta, v) for v in visits}
            (rdir / "run.json").write_text(
                json.dumps({"schema": SCHEMA, "run": meta, "visits": per_visit}, indent=1), encoding="utf-8"
            )
            exported += 1
    finally:
        c.close()
    state_path.write_text(json.dumps(done))
    summary = rebuild_by_node(out)
    return {"schema": SCHEMA, "runs_selected": len(selected), "runs_exported": exported, "nodes": len(summary), "out": str(out)}


def rebuild_by_node(out: Path) -> dict:
    """Aggregate every exported run.json into by-node reports, nodes.csv and index.md."""
    by: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    latest: dict[tuple, tuple[dict, dict]] = {}
    for rj in sorted((out / "runs").glob("*/run.json")):
        d = json.loads(rj.read_text())
        for st in d["visits"].values():
            if st.get("kind") == "structured" and d["run"].get("wo"):  # one order workspace, counted once (newest run)
                key = (d["run"]["wo"], st["node"])
                if key not in latest or (latest[key][0].get("created_ms") or 0) < (d["run"].get("created_ms") or 0):
                    latest[key] = (d["run"], st)
                continue
            by[st["node"]].append((d["run"], st))
    for meta, st in latest.values():
        by[st["node"]].append((meta, st))
    nd = out / "by-node"
    nd.mkdir(exist_ok=True)
    rows = []
    for node, items in sorted(by.items()):
        agg = _sum([s for _, s in items])
        n = max(agg["turns"], 1)
        row = {
            "node": node,
            "kind": agg["kind"],
            "visits": agg["visits"],
            "calls": agg["turns"],
            "calls_per_visit": round(agg["turns"] / agg["visits"], 1),
            "prompt_tokens": agg["prompt_tokens"],
            "prompt_per_call": agg["prompt_tokens"] // n,
            "cache_reuse": round(agg["cache_reused_tokens"] / agg["prompt_tokens"], 3) if agg["prompt_tokens"] else None,
            "output_tokens": agg["output_tokens"],
            "visible_output_chars": agg["visible_output_chars"],
            "tool_calls": agg["tool_calls"],
            "tool_errors": agg["tool_errors"],
            "duplicate_tool_calls": agg["duplicate_tool_calls"],
            "retries": agg["retries"],
            "truncated": agg["truncated_outputs"],
            "model_s": round(agg["model_ms"] / 1000),
            "tool_s": round(agg["tool_ms"] / 1000),
            "loops": agg["loops"],
        }
        rows.append(row)
        lines = [
            f"# Node `{node}` ({agg['kind']})",
            "",
            f"{agg['visits']} visits, {agg['turns']} model calls ({row['calls_per_visit']} per visit). "
            f"Prompts {agg['prompt_tokens']:,} tokens ({row['prompt_per_call']:,} per call, largest {agg['max_prompt']:,}), output "
            f"{agg['output_tokens']:,} tokens. Model time {row['model_s']:,} s, tool time {row['tool_s']:,} s.",
            "",
            "## Optimization pointers",
            "",
        ] + [f"- {x}" for x in hints(node, agg) or ["Nothing stands out."]]
        if agg["context_by_category"]:
            lines += ["", "## Where the prompt tokens go (all calls)", "", "| category | tokens | per call |", "|---|---:|---:|"]
            lines += [
                f"| {k} | {v:,} | {v // n:,} |" for k, v in sorted(agg["context_by_category"].items(), key=lambda kv: -kv[1])
            ]
        if agg["tools_used"]:
            lines += ["", "## Tools used", "", ", ".join(f"{k} x{v}" for k, v in agg["tools_used"].most_common())]
        lines += [
            "",
            "## Visits",
            "",
            "| run | order | visit | status | calls | prompt | output | tool calls | errors | model s | transcript |",
            "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for meta, s in sorted(items, key=lambda x: x[0]["created_ms"] or 0, reverse=True):
            link = f"../runs/{_safe((meta['wo'] or 'run') + '__' + meta['run_id'])}/{_safe(node)}/visit-{s.get('visit')}.md"
            lines.append(
                f"| {meta['run_id'][-8:]} | {meta['wo'] or ''} | {s.get('visit')} | {s['status']} | {s['turns']} | {s['prompt_tokens']:,} | "
                f"{s['output_tokens']:,} | {s['tool_calls']} | {s['tool_errors'] + s['failed_attempts']} | {s['model_ms'] // 1000} | [open]({link}) |"
            )
        (nd / f"{_safe(node)}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows.sort(key=lambda r: -r["prompt_tokens"])
    if rows:
        with open(out / "nodes.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (out / "index.md").write_text(
        "# Model exchanges by node (PRIVATE)\n\nUpdated "
        + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        + ". Every AI node of the "
        "exported runs, sorted by prompt tokens. Open a node for its optimization pointers and every visit's transcript.\n\n"
        "| node | kind | visits | calls/visit | prompt tokens | per call | cache reuse | output tokens | tool calls | errors | model s |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
        + "".join(
            f"| [{r['node']}](by-node/{_safe(r['node'])}.md) | {r['kind']} | {r['visits']} | {r['calls_per_visit']} | {r['prompt_tokens']:,} | "
            f"{r['prompt_per_call']:,} | {'' if r['cache_reuse'] is None else format(r['cache_reuse'], '.0%')} | {r['output_tokens']:,} | "
            f"{r['tool_calls']} | {r['tool_errors']} | {r['model_s']:,} |\n"
            for r in rows
        ),
        encoding="utf-8",
    )
    return {r["node"]: r for r in rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--db", required=True, type=Path)
    e.add_argument("--out", required=True, type=Path)
    e.add_argument("--run")
    e.add_argument("--wo", help="work order text, e.g. GPIOL-20261107-L40G")
    e.add_argument("--workorders", type=Path, help="order workspaces (default: <lrtx>/state/workorders next to the Fabro store)")
    e.add_argument("--incremental", action="store_true", help="skip finished runs already exported")
    r = sub.add_parser("runs")
    r.add_argument("--db", required=True, type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "export":
        print(json.dumps(export(a.db, a.out, run=a.run, wo=a.wo, incremental=a.incremental, workorders=a.workorders)))
    else:
        c = _ro(a.db)
        try:
            for x in runs(c):
                print(x["run_id"], x["status"], x["wo"] or "-", x["tokens"]["input"], x["tokens"]["output"])
        finally:
            c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
