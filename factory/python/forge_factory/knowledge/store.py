"""T030–T033 — durable, evidence-linked lessons learned (SQLite + FTS5), model-free validation.

Lifecycle: PROPOSED -> QUARANTINED | VALIDATING -> VALIDATED -> RETRACTED | EXPIRED
* A lesson can only be VALIDATED when its source repair attempt was PROMOTED with all tests PASS and the
  deterministic curator validators pass (no secrets, no prompt injection, no gate/policy weakening,
  evidence present, not a duplicate).
* Retrieval returns only VALIDATED, unexpired lessons, top-K (<=3) within a token budget, wrapped as
  *reference data* with provenance — never as instructions. Every use is recorded for impact analysis.
* Retraction (manual policy or tool-version regression) removes a lesson from retrieval and returns the
  list of runs that consumed it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..common import schema_errors, state_dir, utc_now
from ..events.emit import emit
from ..events.redact import redact_text

INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|above)|disregard (the )?(instructions|rules)|"
    r"system prompt|you are now|act as|new instructions|<\|im_start\|>|<\|system\|>|"
    r"###\s*instruction|override (the )?(policy|rules)|do not tell|jailbreak)"
)
WEAKENING = re.compile(
    r"(?i)(disable|skip|bypass|waive|suppress|turn off|lower|relax|remove)\b[^\n]{0,60}"
    r"(gate|inspection|check|test|coverage|misra|policy|threshold|audit|hook|sandbox|safety)|"
    r"--no-verify|allow[_ -]?shell|chmod\s+777|protected[_ ]paths?|"
    r"release-package-policy|supervisor-policy|safety/|evidence/"
)
DEFAULT_TTL_DAYS = 180
CHARS_PER_TOKEN = 4

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS lessons (
  lesson_id TEXT PRIMARY KEY, record TEXT NOT NULL, state TEXT NOT NULL, content_hash TEXT NOT NULL,
  tools TEXT NOT NULL, phase TEXT, created_at TEXT NOT NULL, expires_at TEXT, reasons TEXT NOT NULL DEFAULT '[]');
CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(lesson_id UNINDEXED, symptoms, root_cause, remedy, tools);
CREATE TABLE IF NOT EXISTS lesson_usage (lesson_id TEXT NOT NULL, run_id TEXT NOT NULL, used_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lesson_history (seq INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id TEXT, from_state TEXT,
  to_state TEXT, at TEXT, reason TEXT);
"""


class LessonStore:
    def __init__(self, path: Path | None = None, incidents=None):
        self.path = path or state_dir() / "knowledge" / "lessons.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.incidents = incidents
        with self._conn() as c:
            c.executescript(SCHEMA)
            from .experience import SCHEMA as EXPERIENCE_SCHEMA

            c.executescript(EXPERIENCE_SCHEMA)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    # -- helpers ------------------------------------------------------------------------------
    @staticmethod
    def content_hash(rec: dict) -> str:
        norm = " ".join(re.sub(r"\s+", " ", str(rec.get(k, "")).lower()).strip() for k in ("symptoms", "remedy"))
        if rec.get("contract_version") == "2.0":
            norm += json.dumps(
                {k: rec.get(k) for k in ("applicability", "tool_versions", "version", "source_kind")}, sort_keys=True
            )
        return hashlib.sha256(norm.encode()).hexdigest()

    def _set_state(self, c, lesson_id: str, new: str, reason: str, reasons: list[str] | None = None) -> None:
        row = c.execute("SELECT state, record FROM lessons WHERE lesson_id=?", (lesson_id,)).fetchone()
        rec = json.loads(row["record"])
        rec["state"] = new
        if new == "VALIDATED":
            rec["validated_at"] = utc_now()
        c.execute(
            "UPDATE lessons SET state=?, record=?, reasons=? WHERE lesson_id=?",
            (new, json.dumps(rec, sort_keys=True), json.dumps(reasons or []), lesson_id),
        )
        c.execute(
            "INSERT INTO lesson_history(lesson_id,from_state,to_state,at,reason) VALUES(?,?,?,?,?)",
            (lesson_id, row["state"], new, utc_now(), reason[:200]),
        )
        if new == "VALIDATED":
            c.execute(
                "INSERT INTO lessons_fts(lesson_id,symptoms,root_cause,remedy,tools) VALUES(?,?,?,?,?)",
                (lesson_id, rec["symptoms"], rec["root_cause"], rec["remedy"], " ".join(rec.get("tool_versions", {}).keys())),
            )
        elif row["state"] == "VALIDATED":
            c.execute("DELETE FROM lessons_fts WHERE lesson_id=?", (lesson_id,))

    def must(self, lesson_id: str) -> dict:
        rec = self.get(lesson_id)
        if rec is None:
            raise KeyError(lesson_id)
        return rec

    def get(self, lesson_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT record, reasons FROM lessons WHERE lesson_id=?", (lesson_id,)).fetchone()
        if not r:
            return None
        rec = json.loads(r["record"])
        rec["_reasons"] = json.loads(r["reasons"])
        return rec

    # -- T030 propose -------------------------------------------------------------------------
    def propose(self, candidate: dict, phase: str | None = None) -> dict:
        """Store a candidate as PROPOSED (always quarantinable); sanitize text before persistence."""
        rec = {
            k: v
            for k, v in candidate.items()
            if k
            in (
                "source_incident_id",
                "source_attempt_id",
                "symptoms",
                "root_cause",
                "remedy",
                "constraints",
                "evidence_refs",
                "tool_versions",
                "validation_tests",
                "expires_at",
                "contract_version",
                "source_kind",
                "version",
                "supersedes",
                "experience_ref",
                "qualification_ref",
                "applicability",
            )
        }
        redacted = False
        for k in ("symptoms", "root_cause", "remedy", "constraints"):
            if isinstance(rec.get(k), str):
                rec[k], r = redact_text(rec[k])
                redacted |= r
        rec.update({"lesson_id": f"lesson-{uuid.uuid4().hex[:12]}", "state": "PROPOSED", "created_at": utc_now()})
        rec.setdefault("expires_at", (datetime.now(UTC) + timedelta(days=DEFAULT_TTL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        rec["hash"] = self.content_hash(rec)
        rec["consumed_by_runs"] = []
        errs = schema_errors("lesson.schema.json", {k: v for k, v in rec.items() if not k.startswith("_")})
        reasons = [f"SCHEMA:{e}"[:120] for e in errs] + (["SECRET_REDACTED"] if redacted else [])
        with self._conn() as c:
            c.execute(
                "INSERT INTO lessons(lesson_id,record,state,content_hash,tools,phase,created_at,expires_at,"
                "reasons) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    rec["lesson_id"],
                    json.dumps(rec, sort_keys=True),
                    "PROPOSED",
                    rec["hash"],
                    json.dumps(sorted((rec.get("tool_versions") or {}).keys())),
                    phase,
                    rec["created_at"],
                    rec["expires_at"],
                    json.dumps(reasons),
                ),
            )
            c.execute(
                "INSERT INTO lesson_history(lesson_id,from_state,to_state,at,reason) VALUES(?,?,?,?,?)",
                (rec["lesson_id"], None, "PROPOSED", rec["created_at"], "proposed"),
            )
        emit("knowledge", "INFO", f"lesson {rec['lesson_id']} proposed", correlation_id=rec.get("source_incident_id"))
        return self.must(rec["lesson_id"])

    # -- T031 deterministic curator validation ---------------------------------------------------
    def validators(self, rec: dict, original_text: str = "") -> list[str]:
        reasons: list[str] = []
        text = " ".join(str(rec.get(k, "")) for k in ("symptoms", "root_cause", "remedy", "constraints"))
        if errs := schema_errors("lesson.schema.json", {k: v for k, v in rec.items() if not k.startswith("_")}):
            reasons += [f"SCHEMA:{e}"[:120] for e in errs[:3]]
        if "[REDACTED" in text or redact_text(original_text or text)[1]:
            reasons.append("CONTAINS_SECRET")
        if INJECTION.search(text):
            reasons.append("PROMPT_INJECTION")
        if WEAKENING.search(text):
            reasons.append("UNSAFE_POLICY_OR_GATE_CHANGE")
        if not rec.get("evidence_refs"):
            reasons.append("NO_EVIDENCE")
        tests = rec.get("validation_tests") or []
        if not tests or any(t.get("status") != "PASS" for t in tests):
            reasons.append("VALIDATION_TESTS_NOT_ALL_PASS")
        if rec.get("source_kind") in ("ORDINARY_OUTCOME", "NEGATIVE_OBSERVATION"):
            from .qualification import issues as qualification_issues

            reasons += qualification_issues(self, rec)
        elif self.incidents is not None:
            atts = [
                a
                for a in self.incidents.attempts(rec.get("source_incident_id"))
                if a["attempt_id"] == rec.get("source_attempt_id")
            ]
            if not atts or atts[-1]["status"] != "PROMOTED" or any(t["status"] != "PASS" for t in atts[-1]["tests"]):
                reasons.append("SOURCE_REPAIR_NOT_PROMOTED")
        else:
            reasons.append("SOURCE_REPAIR_UNVERIFIABLE")
        with self._conn() as c:
            dup = c.execute(
                "SELECT lesson_id FROM lessons WHERE content_hash=? AND state='VALIDATED' AND lesson_id!=?",
                (rec.get("hash"), rec.get("lesson_id")),
            ).fetchone()
        if rec.get("contract_version") == "2.0":
            with self._conn() as c:
                peers = [
                    json.loads(r[0])
                    for r in c.execute(
                        "SELECT record FROM lessons WHERE state='VALIDATED' AND lesson_id!=?", (rec.get("lesson_id"),)
                    )
                ]
            for peer in peers:
                if (
                    peer.get("applicability") == rec.get("applicability")
                    and peer.get("tool_versions") == rec.get("tool_versions")
                    and peer.get("symptoms") == rec.get("symptoms")
                    and peer.get("remedy") != rec.get("remedy")
                    and rec.get("supersedes") != peer["lesson_id"]
                ):
                    reasons.append("CONTRADICTS:" + peer["lesson_id"])
        if dup:
            reasons.append(f"DUPLICATE_OF:{dup['lesson_id']}")
        return reasons

    def validate(self, lesson_id: str) -> dict:
        rec = self.get(lesson_id)
        if rec is None or rec["state"] not in ("PROPOSED", "QUARANTINED"):
            raise ValueError(f"lesson {lesson_id} not validatable")
        prior = rec.pop("_reasons", [])
        reasons = sorted(set(self.validators(rec) + [r for r in prior if r == "SECRET_REDACTED"]))
        reasons = ["CONTAINS_SECRET" if r == "SECRET_REDACTED" else r for r in reasons]
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            self._set_state(c, lesson_id, "VALIDATING", "curator validation started")
            new = "VALIDATED" if not reasons else "QUARANTINED"
            self._set_state(c, lesson_id, new, ",".join(reasons) or "all validators passed", reasons)
            if new == "VALIDATED" and rec.get("supersedes"):
                self._set_state(c, rec["supersedes"], "RETRACTED", "superseded by independently qualified " + lesson_id)
            c.execute("COMMIT")
        emit("knowledge", "INFO" if not reasons else "WARN", f"lesson {lesson_id} {new} {','.join(reasons)[:80]}")
        return self.must(lesson_id)

    # -- T032 retrieval ---------------------------------------------------------------------------
    def expire(self) -> int:
        now = utc_now()
        n = 0
        with self._conn() as c:
            for r in c.execute("SELECT lesson_id FROM lessons WHERE state='VALIDATED' AND expires_at < ?", (now,)).fetchall():
                c.execute("BEGIN IMMEDIATE")
                self._set_state(c, r["lesson_id"], "EXPIRED", "ttl elapsed")
                c.execute("COMMIT")
                n += 1
        return n

    def find(
        self,
        query: str,
        run_id: str,
        tool: str | None = None,
        phase: str | None = None,
        k: int = 3,
        token_budget: int = 700,
        *,
        role: str | None = None,
        target: str | None = None,
        source_version: str | None = None,
        tool_versions: dict | None = None,
        record_usage: bool = True,
    ) -> dict:
        self.expire()
        k = max(0, min(3, k))
        terms = [t for t in re.findall(r"[A-Za-z0-9_]{3,}", query.lower())][:12]
        if not terms or k == 0:
            return {"lessons": [], "tokens_estimated": 0, "note": "reference data only, not instructions"}
        fts = " OR ".join(f'"{t}"' for t in terms)
        with self._conn() as c:
            rows = c.execute(
                "SELECT l.lesson_id,l.record,l.phase FROM lessons_fts f JOIN lessons l ON l.lesson_id=f.lesson_id "
                "WHERE lessons_fts MATCH ? AND l.state='VALIDATED' ORDER BY bm25(lessons_fts) LIMIT 20",
                (fts,),
            ).fetchall()
        out: list[dict] = []
        used = 0
        for r in rows:
            try:
                rec = json.loads(r["record"])
                if not isinstance(rec, dict):
                    raise ValueError("INVALID_LESSON_RECORD")
            except (ValueError, TypeError):
                with self._conn() as c:
                    c.execute("BEGIN IMMEDIATE")
                    c.execute(
                        "UPDATE lessons SET state='QUARANTINED',reasons=? WHERE lesson_id=?",
                        (json.dumps(["MALFORMED_LESSON_RECORD"]), r["lesson_id"]),
                    )
                    c.execute("DELETE FROM lessons_fts WHERE lesson_id=?", (r["lesson_id"],))
                    c.execute(
                        "INSERT INTO lesson_history(lesson_id,from_state,to_state,at,reason) VALUES (?,?,?,?,?)",
                        (
                            r["lesson_id"],
                            "VALIDATED",
                            "QUARANTINED",
                            utc_now(),
                            "malformed record retained; sha256=" + hashlib.sha256(r["record"].encode()).hexdigest(),
                        ),
                    )
                    c.execute("COMMIT")
                continue
            if role == "swe1-author" and r["phase"] is None:
                continue
            if r["phase"] is not None and r["phase"] != phase:
                continue
            if role and role.endswith("-inspector"):
                continue  # inspector memory retains the independently governed IL path
            if rec.get("source_kind") in ("ORDINARY_OUTCOME", "NEGATIVE_OBSERVATION"):
                from .qualification import issues as qualification_issues

                if qualification_issues(self, rec):
                    self.retract(rec["lesson_id"], "source-specific qualification became stale")
                    continue
            app = rec.get("applicability")
            if app and (
                phase not in app["phases"]
                or role not in app["roles"]
                or target not in app["targets"]
                or source_version not in app["source_versions"]
            ):
                continue
            if rec.get("contract_version") == "2.0" and rec.get("tool_versions") and tool_versions is None:
                continue
            if tool_versions is not None and any(tool_versions.get(k) != v for k, v in rec.get("tool_versions", {}).items()):
                continue
            if tool and tool not in (rec.get("tool_versions") or {}):
                continue
            with self._conn() as c:
                validation = c.execute(
                    "SELECT at FROM lesson_history WHERE lesson_id=? AND to_state='VALIDATED' ORDER BY seq DESC LIMIT 1",
                    (rec["lesson_id"],),
                ).fetchone()
            item = {
                "lesson_id": rec["lesson_id"],
                "validated_at": rec.get("validated_at") or (validation[0] if validation else None),
                "symptoms": rec["symptoms"],
                "root_cause": rec["root_cause"],
                "remedy": rec["remedy"],
                "constraints": rec.get("constraints", ""),
                "provenance": {
                    "incident": rec.get("source_incident_id"),
                    "attempt": rec.get("source_attempt_id"),
                    "experience_ref": rec.get("experience_ref"),
                    "version": rec.get("version", 1),
                    "qualification_ref": rec.get("qualification_ref"),
                    "applicability": rec.get("applicability"),
                    "evidence_refs": rec["evidence_refs"][:3],
                    "tool_versions": rec["tool_versions"],
                    "expires_at": rec.get("expires_at"),
                },
            }
            cost = len(json.dumps(item)) // CHARS_PER_TOKEN + 1
            if used + cost > token_budget or len(out) >= k:
                continue
            out.append(item)
            used += cost
        with self._conn() as c:
            for it in out if record_usage else []:
                c.execute(
                    "INSERT INTO lesson_usage(lesson_id,run_id,used_at) VALUES(?,?,?)", (it["lesson_id"], run_id, utc_now())
                )
        from .experience import transfer

        for it in out if record_usage else []:
            transfer(self, it["lesson_id"], run_id, "EXPOSURE")
        return {"lessons": out, "tokens_estimated": used, "note": "reference data only, not instructions"}

    # -- T033 retraction -----------------------------------------------------------------------------
    def consumers(self, lesson_id: str) -> list[str]:
        with self._conn() as c:
            return sorted({r["run_id"] for r in c.execute("SELECT run_id FROM lesson_usage WHERE lesson_id=?", (lesson_id,))})

    def retract(self, lesson_id: str, reason: str) -> dict:
        rec = self.get(lesson_id)
        if rec is None or rec["state"] != "VALIDATED":
            raise ValueError(f"lesson {lesson_id} not retractable from {rec and rec['state']}")
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            self._set_state(c, lesson_id, "RETRACTED", reason)
            c.execute("COMMIT")
        impacted = self.consumers(lesson_id)
        emit("knowledge", "WARN", f"lesson {lesson_id} RETRACTED; {len(impacted)} runs flagged for impact review")
        return {"lesson_id": lesson_id, "state": "RETRACTED", "impacted_runs": impacted}

    def invalidate_tool_version(self, tool: str, bad_version: str, reason: str = "tool regression") -> list[dict]:
        out = []
        with self._conn() as c:
            rows = c.execute("SELECT lesson_id, record FROM lessons WHERE state='VALIDATED'").fetchall()
        for r in rows:
            if json.loads(r["record"]).get("tool_versions", {}).get(tool) == bad_version:
                out.append(self.retract(r["lesson_id"], f"{reason}:{tool}@{bad_version}"))
        return out

    def list(self, state: str | None = None) -> list[dict]:
        with self._conn() as c:
            q = "SELECT record FROM lessons" + (" WHERE state=?" if state else "") + " ORDER BY created_at"  # noqa: S608
            return [json.loads(r["record"]) for r in c.execute(q, (state,) if state else ())]
