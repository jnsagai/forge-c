"""T036 — secret redaction applied before any persistence (events, lessons, archives, UI).

Deterministic regex rules; conservative (prefers over-redaction). Returns (clean_text, redacted?).
"""
from __future__ import annotations

import re
from typing import Any

RULES: list[tuple[str, re.Pattern[str]]] = [
    ("fabro_token", re.compile(r"fabro_dev_[0-9a-f]{16,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----|$)")),
    ("aws_key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("openai_like", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("bearer", re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}")),
    ("kv_secret", re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|session_secret|access[_-]?key)"
                             r"(\s*[:=]\s*|\"\s*:\s*\")([^\s\"',;]{4,})")),
    ("url_creds", re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")),
]


# Whole key names that hold secrets (not substrings: e.g. `token_count_provenance`/`input_tokens` are metadata).
SECRET_KEY = re.compile(r"(?i)^(.*[_-])?(password|passwd|secret|client_secret|session_secret|api[_-]?key|"
                        r"authorization|token|access[_-]?token|refresh[_-]?token|auth[_-]?token|private[_-]?key)$")


def redact_text(text: str) -> tuple[str, bool]:
    changed = False
    for name, pat in RULES:
        def repl(m: re.Match[str], name: str = name) -> str:
            if name == "kv_secret":
                return f"{m.group(1)}{m.group(2)}[REDACTED:{name}]"
            if name == "url_creds":
                return f"{m.group(1)}[REDACTED:{name}]@"
            if name == "bearer":
                return f"{m.group(1)} [REDACTED:{name}]"
            return f"[REDACTED:{name}]"

        new = pat.sub(repl, text)
        if new != text:
            changed, text = True, new
    return text, changed


def redact_obj(obj: Any) -> tuple[Any, bool]:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        out, changed = {}, False
        for k, v in obj.items():
            if isinstance(k, str) and SECRET_KEY.match(k) \
                    and isinstance(v, str) and v:
                out[k], changed = "[REDACTED:key_name]", True
                continue
            nv, c = redact_obj(v)
            out[k], changed = nv, changed or c
        return out, changed
    if isinstance(obj, list):
        items, changed = [], False
        for v in obj:
            nv, c = redact_obj(v)
            items.append(nv)
            changed = changed or c
        return items, changed
    return obj, False
