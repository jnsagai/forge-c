# ruff: noqa: E501
"""Omniverse2 adapters of the qualification window controller (feature 017, T014; window-controls.md).

Only existing, unsigned controls are used:

* hold / release - the admission hold `paused` in the owner lane's line queue, written through `Store.set_control`
  of the LIVE code tree with the live lane's Python (the deployer's hold-admission pattern); the operations intent
  file must be byte-identical before and after (never the intent: its epoch would fence the guardian);
* idle - read-only SQL over the line queue (no active order; `quiet_ledger`'s inference, lease, request and outbox
  checks);
* stop / restart the whole lane - the deployer's `window-release <id> <deadline>` / `window-restore` (T072): the
  reviewed deploy chain for a same-tree commit, split at the exact stop. The deployer holds its own lock and an open
  window file, so its timer skips while the window is open and restores an abandoned window itself;
* preflight - refuses before any change when the deployer lacks those commands, is latched or busy, a deploy is
  pending (a window would otherwise revert it), or the deployer's rate limit would refuse the window.

The model tier is started with `recipe apply` (refused outside a window) and stopped with its unit and compose.
"""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

import httpx

F = Path("/mnt/data/forge-c/swe1-fabro-20261031")
LRTX, QUAL = F / "lrtx", F / "qualification"
DEPLOYER = Path("/mnt/data/forge-c/owner-autodeploy/deployer")
INTENT = Path("/home/omniverse2/.config/forge-c/line-local/operations-intent.json")
ACTIVE = ("RUNNING", "ADMITTED", "VALIDATING", "WAITING_RECOVERY", "QUEUED")
QUIET_AND_STOP_S = 9 * 3600  # the deployer waits up to 8 h for a quiet line, then stops and proves the stop

HOLD = """import json,os,sys
from pathlib import Path
S,L,I,V,REASON=Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],sys.argv[5]
sys.path.insert(0,str(S/'factory/python'));sys.dont_write_bytecode=True
os.environ.update(FORGE_REPO_ROOT=str(S),FORGE_DATA_ROOT='/mnt/data/forge-c',FORGE_STATE_DIR=str(L/'state'),FORGE_LRTX_ROOT=str(L))
os.environ.pop('FORGE_OPERATIONS_INTENT',None)
from forge_factory.afo.queue import Store
s=Store(L/'state/supervisor/line-queue.sqlite3');i0=I.read_bytes()
s.set_control('paused',V,'model-service-qualification-window',REASON)
c=s.control();assert c.get('paused')==V and I.read_bytes()==i0,'HOLD_NOT_APPLIED_OR_INTENT_CHANGED'
print(json.dumps({'paused':c.get('paused')}))
"""


class OwnerLane:
    def __init__(self, *, lrtx: Path = LRTX, qual: Path = QUAL, deployer: Path = DEPLOYER, intent: Path = INTENT,
                 python: str | None = None, work: Path, run=subprocess.run, window_id: str = "", deadline: float = 0.0,
                 repo: Path = Path("/mnt/data/forge-c/owner-autodeploy/repo.git"),
                 branch: str = "feat/owner-lane-campaign-v21-20261107"):
        self.lrtx, self.qual, self.deployer, self.intent = Path(lrtx), Path(qual), Path(deployer), Path(intent)
        self.python, self.work, self.run = python or str(Path(lrtx) / "venv/bin/python"), Path(work), run
        self.window_id, self.deadline, self.repo, self.branch = window_id, deadline, Path(repo), branch

    # ---- facts ---------------------------------------------------------------------------------------------------
    def live(self) -> dict:
        return json.loads((self.deployer / "state.json").read_text())["live"]

    def tree(self) -> Path:
        live = self.live()
        return self.qual / f"owner-allowance-{live['commit'][:8]}-main-20261107" / "newS"

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.lrtx / 'state/supervisor/line-queue.sqlite3'}?mode=ro", uri=True)

    def paused(self) -> str | None:
        with contextlib.closing(self._db()) as c:
            row = c.execute("SELECT value FROM afo_control WHERE key='paused'").fetchone()
        return row[0] if row else None

    def preflight(self) -> tuple[bool, str]:
        if not self.tree().is_dir():
            return False, "LIVE_TREE_MISSING"
        if (self.deployer / "deploy.lock").exists():
            return False, "DEPLOY_IN_PROGRESS"
        if (self.deployer / "FAILED_LATCHED.json").exists():
            return False, "DEPLOYER_LATCHED"
        if self.paused() != "0":
            return False, "ADMISSION_ALREADY_HELD"
        src = (self.deployer / "autodeploy.py").read_text()
        if "'window-release'" not in src or "'window-restore'" not in src:
            return False, "BLOCKED:DEPLOYER_WINDOW_COMMANDS_MISSING"
        if (self.deployer / "WINDOW.json").exists():
            return False, "WINDOW_ALREADY_OPEN"
        st = json.loads((self.deployer / "state.json").read_text())
        tip = self.run(["git", "-C", str(self.repo), "rev-parse", self.branch], capture_output=True, text=True, check=False).stdout.strip()
        if tip != st["live"]["commit"]:
            return False, "PENDING_DEPLOY:the branch tip is not live yet (a window would revert it)"
        times = [d["at_epoch"] for d in st.get("deploys", [])]
        if times and time.time() - max(times) <= self._limit(src, "MIN_GAP_S", 3600):
            return False, "DEPLOYER_RATE_LIMIT_GAP"
        if sum(1 for t in times if time.time() - t < 86400) >= self._limit(src, "MAX_PER_DAY", 4):
            return False, "DEPLOYER_RATE_LIMIT_DAY"
        return True, ""

    @staticmethod
    def _limit(src: str, name: str, default: int) -> int:
        """One of the deployer's own rate limits (owner-set: MAX_PER_DAY 10, MIN_GAP_S 0 since 2026-11-08), read from its
        source, never assumed."""
        import re

        m = re.search(rf"^{name} = (\d+)", src, flags=re.M)
        return int(m.group(1)) if m else default

    # ---- controls ------------------------------------------------------------------------------------------------
    def _set(self, value: str, reason: str) -> None:
        self.work.mkdir(parents=True, exist_ok=True)
        script = self.work / "hold.py"
        script.write_text(HOLD)
        r = self.run([self.python, "-B", str(script), str(self.tree()), str(self.lrtx), str(self.intent), value, reason],
                     capture_output=True, text=True, timeout=120, check=False)
        if r.returncode != 0 or self.paused() != value:
            raise RuntimeError(f"ADMISSION_HOLD_{'SET' if value == '1' else 'CLEAR'}_FAILED:{(r.stderr or r.stdout)[-200:]}")

    def hold(self) -> None:
        self._set("1", "feature 017 qualification window: hold new attempts while the model tier uses the GPU")

    def release_hold(self) -> None:
        self._set("0", "feature 017 qualification window ended: lane restored")

    def idle(self) -> tuple[bool, str]:
        with contextlib.closing(self._db()) as c:
            marks = ",".join("?" * len(ACTIVE))  # fixed placeholders; the values are bound
            busy = c.execute(f"SELECT state,count(*) FROM afo_work_orders WHERE state IN ({marks}) GROUP BY state",  # noqa: S608
                             ACTIVE).fetchall()
            if busy:
                return False, "ORDERS_ACTIVE:" + ",".join(f"{s}={n}" for s, n in busy)
            held = c.execute("SELECT holder FROM afo_resource_ownership WHERE resource='inference'").fetchone()
            if held and held[0]:
                return False, "INFERENCE_OWNER_PRESENT"
            if any(json.loads(r[0]).get("resource_lease") != "RELEASED" for r in c.execute("SELECT record FROM afo_execution_liveness")):
                return False, "EXECUTION_LEASE_NOT_RELEASED"
            if c.execute("SELECT 1 FROM afo_request_ledger WHERE state IS NULL OR state!='QUIESCENT' LIMIT 1").fetchone():
                return False, "REQUEST_NOT_QUIESCENT"
            if c.execute("SELECT 1 FROM afo_commands_outbox WHERE state IS NULL OR state NOT IN ('ACKED','FAILED','QUARANTINED') LIMIT 1").fetchone():
                return False, "COMMAND_OUTCOME_UNRESOLVED"
        return True, "IDLE"

    @contextlib.contextmanager
    def suppress_redeploy(self):
        """The deployer suppresses itself: its own lock during release/restore and WINDOW.json in between."""
        yield

    def _deployer(self, cmd: str, *args: str) -> None:
        r = self.run([self.python, str(self.deployer / "autodeploy.py"), cmd, *args], capture_output=True, text=True,
                     timeout=QUIET_AND_STOP_S, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"DEPLOYER_{cmd.upper().replace('-', '_')}_FAILED:{(r.stderr or r.stdout)[-300:]}")

    def stop_lane(self) -> None:
        self._deployer("window-release", self.window_id, str(int(self.deadline)))

    def restart_lane(self) -> None:
        if not (self.deployer / "WINDOW.json").exists() and self._release_refused_untouched():
            return  # CAPA-233: nothing was released, so nothing is restored (the hold is released by the caller)
        self._deployer("window-restore")

    def _release_refused_untouched(self) -> bool:
        """CAPA-233: the deployer's latest record of this window says it refused the release before touching the lane."""
        try:
            with open(self.deployer / "log.jsonl", "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 262144))
                lines = f.read().decode(errors="replace").splitlines()
        except OSError:
            return False
        for line in reversed(lines):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if isinstance(x, dict) and x.get("window") == self.window_id:
                return (x.get("event") == "window_release_failed" and x.get("line_touched") is False
                        and x.get("stopped") is False)
        return False


class ModelTier:
    def __init__(self, *, repo: Path, window_id: str, gateway: str = "http://127.0.0.1:18480", key: str | None = None,
                 run=subprocess.run, http: httpx.Client | None = None, ready_s: float = 1800):
        self.repo, self.window_id, self.gateway, self.key, self.run = Path(repo), window_id, gateway, key, run
        self.http, self.ready_s = http or httpx.Client(timeout=10), ready_s

    def preflight(self) -> tuple[bool, str]:
        tier = self.repo / "deploy/recipe/model-tier"
        for f in ("catalog.yaml", "tenants.yaml"):
            if not (tier / f).is_file():
                return False, f"TIER_NOT_CONFIGURED:{f}"
        return True, ""

    def start(self) -> dict:
        env = {**os.environ, "FORGE_017_WINDOW_ID": self.window_id}
        r = self.run(["uv", "run", "--project", str(self.repo), "python", "-m", "forge_factory.modelservice.recipe", "apply",
                      "--site", "omniverse2", "--execute"], capture_output=True, text=True, env=env, timeout=600, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"TIER_APPLY_FAILED:{(r.stderr or r.stdout)[-300:]}")
        end = time.monotonic() + self.ready_s
        while time.monotonic() < end:  # the gateway warms every model first (vLLM start + sleep, GGUF staging)
            with contextlib.suppress(httpx.HTTPError):
                if self.http.get(self.gateway + "/health").status_code == 200:
                    break
            time.sleep(5)
        else:
            raise TimeoutError("TIER_NOT_READY")
        idents = {}
        if self.key:
            h = {"Authorization": f"Bearer {self.key}"}
            for m in self.http.get(self.gateway + "/forge/v1/catalog", headers=h).json()["models"]:
                idents[m["model"]] = self.http.get(self.gateway + "/forge/v1/identity", params={"model": m["model"]},
                                                   headers=h).json()["revision_fingerprint"][:16]
        return {"identities": idents}

    def stop(self) -> None:
        self.run(["systemctl", "--user", "stop", "forge-model-tier-gateway"], capture_output=True, timeout=180, check=False)
        compose = self.repo / "deploy/recipe/model-tier/compose.yaml"  # only sites with container engines have one
        if compose.is_file():
            self.run(["docker", "compose", "-f", str(compose), "-p", "forge-model-tier", "stop"], capture_output=True, timeout=300,
                     check=False)
