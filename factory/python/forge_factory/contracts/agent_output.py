"""T008/T043 — strict compact agent result parser (`status, artifacts, issues, next_action`).

Free-form prose is rejected: the final agent message must be exactly one JSON object, optionally
inside a single ```json fence and nothing else. Size is bounded. Issues are preserved verbatim
(never summarised away). Routing directives (`preferred_next_label`, `suggested_next_ids`,
`context_updates`) are forbidden so an agent cannot steer the deterministic lifecycle.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..common import schema_errors

MAX_BYTES = 4096
HUMAN_STATUS_MAX = 160
_FENCE = re.compile(r"^```(?:json)?\s*\n(?P<body>.*)\n```$", re.S)
ROUTING_KEYS = {"preferred_next_label", "suggested_next_ids", "context_updates", "jump_to_node"}


@dataclass
class AgentResult:
    status: str
    artifacts: list[str]
    issues: list[str]
    next_action: str
    raw_sha_bytes: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def human_status(self) -> str:
        """<=160-char operator line; full issues stay in the structured record."""
        s = f"{self.status} next={self.next_action} issues={len(self.issues)} artifacts={len(self.artifacts)}"
        if self.issues:
            s += f" first={self.issues[0]}"
        return s[:HUMAN_STATUS_MAX]


def parse(text: str | bytes | None) -> AgentResult:
    def fail(code: str) -> AgentResult:
        return AgentResult("FAILED", [], [code], "halt", 0, [code])

    if text is None:
        return fail("AGENT_OUTPUT_MISSING")
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            return fail("AGENT_OUTPUT_NOT_UTF8")
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        return fail("AGENT_OUTPUT_TOO_LARGE")
    body = text.strip()
    m = _FENCE.match(body)
    if m:
        body = m.group("body").strip()
    if not body.startswith("{") or not body.endswith("}"):
        return fail("AGENT_OUTPUT_PROSE")
    try:
        obj = json.loads(body)
    except ValueError:
        return fail("AGENT_OUTPUT_INVALID_JSON")
    if not isinstance(obj, dict):
        return fail("AGENT_OUTPUT_NOT_OBJECT")
    if ROUTING_KEYS & set(obj):
        return fail("AGENT_OUTPUT_ROUTING_FORBIDDEN")
    errs = schema_errors("agent-output.schema.json", obj)
    if errs:
        r = fail("AGENT_OUTPUT_SCHEMA")
        r.errors += errs[:5]
        if isinstance(obj.get("issues"), list):  # preserve the agent's findings even when rejected
            r.issues += [str(i)[:120] for i in obj["issues"][:30]]
        return r
    return AgentResult(obj["status"], list(obj["artifacts"]), list(obj["issues"]), obj["next_action"], size)
