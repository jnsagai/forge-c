"""Owner 2026-11-13 ("go ahead with 1, 2 and 3", autonomy item 2): the line releases a stopped lineage itself when
the cause of the stop is gone - no series bump by hand.

A lineage stops (SAME_ISSUE_EXCEEDED_3) after more than three consecutive attempts with the same failure fingerprint.
A new deployed revision already rebinds every lineage block (the derived campaign names the revision in each block),
so the attempts on the old revision become history by themselves. What stayed manual was an environment or input fix
that no deploy follows (L48: a toolchain header fixed on the host). Rule CAUSE_GONE: every attempt of the stopping
fingerprint ended before its run started on an input/environment cause (launch log stage delivery_intake / inputs /
prepare, or issues INPUT_GAP*/DELIVERY_*), and the same checks the line runs before a placement pass now. The release
is recorded with its evidence and granted once per lineage block (block = revision + lineage settings): if the
failure comes back, the lineage stops again and stays stopped until something changes."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import utc_now

CAUSE_GONE = "CAUSE_GONE"
PRE_RUN_STAGES = ("delivery_intake", "inputs", "input_readiness", "prepare")
PRE_RUN_PREFIXES = ("INPUT_GAP", "DELIVERY_")


def launch_cause(runs_root: Path, wo: str) -> dict | None:
    """The cause the launcher recorded for a work order that did not start: the last result line of its newest
    attempt log (<runs>/.launch/<WO>/attempt-N/workorder-launch.log); None when there is none."""
    base = Path(runs_root) / ".launch" / wo
    logs = sorted(base.glob("attempt-*/workorder-launch.log"), key=lambda p: p.stat().st_mtime) if base.is_dir() else []
    for p in reversed(logs):
        try:
            lines = p.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if "stage" in d or "issues" in d:
                return {"status": d.get("status"), "stage": d.get("stage"), "issues": list(d.get("issues") or [])}
    return None


def pre_run(cause: dict | None) -> bool:
    """True for an attempt that ended before its run started on an input/environment cause."""
    if not cause or cause.get("status") != "BLOCKED":
        return False
    issues = [str(i) for i in cause.get("issues") or []]
    return cause.get("stage") in PRE_RUN_STAGES or (bool(issues) and all(i.startswith(PRE_RUN_PREFIXES)
                                                                           for i in issues))


class Releases:
    """The release log (append-only JSONL). `path` None: decisions are made but nothing is persisted (dry run)."""

    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self._rows: list[dict] | None = None

    def rows(self) -> list[dict]:
        if self._rows is None:
            self._rows = []
            if self.path and self.path.is_file():
                for line in self.path.read_text().splitlines():
                    try:
                        self._rows.append(json.loads(line))
                    except ValueError:
                        continue
        return self._rows

    def latest(self, lineage_sha: str, phase: str) -> dict | None:
        mine = [r for r in self.rows() if r.get("lineage_sha") == lineage_sha and r.get("phase") == phase]
        return mine[-1] if mine else None

    def has(self, lineage_sha: str, phase: str, fingerprint: str, rule: str) -> bool:
        return any(r.get("lineage_sha") == lineage_sha and r.get("phase") == phase and r.get("fingerprint") ==
                   fingerprint and r.get("rule") == rule for r in self.rows())

    def record(self, row: dict) -> dict:
        row = {**row, "recorded_at": utc_now()}
        self.rows().append(row)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")
        return row
