"""Autonomous line M3 (owner 2026-11-03, decision 3) - production campaign files for the Line Conductor.

A campaign is a YAML file `config/factory/campaigns/*.yaml` (schema `forge-c/line-campaign/1`). The owner approves it
once, by commit: a file is loaded only when it is tracked and unmodified in its git checkout, and every order placed
from it is bound to the file's sha256 (and to the sha256 of its lineage block). Inside one campaign the Line
Conductor chains phases (SWE.n PASS -> SWE.n+1) and lineages (`depends_on`: LL SWE.6 PASS -> HAL SWE.1); a new
lineage or example is a new campaign entry, i.e. a new owner-approved commit.

    schema: forge-c/line-campaign/1
    campaign_id: CMP-...
    line: local
    wo_prefix: WO-F014                          # phase order names: <prefix>-SWE<n>-<tag>-<series>[retry letters]
    lineages:
      - id: crc-ll
        status: ACTIVE | ON_HOLD | DONE         # DONE needs completed_by (the order that passed the last phase)
        example: 0014l-st-cube-crc-swe1-gen
        tag: CRCL                               # the part tag of the order names (unique on the line)
        series: 20261103-L30                    # the name series; retries append B, C, ...
        driver_class: STM32N6_CRC_LL_ST         # PILOT grant scope.driver_classes
        factory_revision: 82fabdb9 | null       # a run-branch revision (decision 4); null = waiting for one
        profile: local-rtx-v2-...               # PILOT grant scope.models
        run_model: hf.co/...
        purpose: ASPICE_ONLY
        phases: [SWE.1, ..., SWE.6]
        start: {resume_from: WO-..., at: SWE.3}           # optional: phases before `at` are carried by resume_from
        provided_from: WO-...                            # optional (HAL on a verified LL), or
        depends_on: {lineage: crc-ll, phase: SWE.6, verdict: PASS}   # provided_from = that lineage's passing order
        after: {lineage: crc-hal, phase: SWE.6, verdict: PASS}       # optional: wait for it, build on nothing
        priority: 50                            # higher first; one GPU run at a time
        quality: {...}                          # optional order quality block (owner rule 2026-11-03), into the order

The validation here is the authority (fail closed); the JSON contract specs/014-.../contracts/line-campaign.schema.json
is checked as well when it is installed. Deterministic and model-free.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, sha256_bytes

SCHEMA_ID = "forge-c/line-campaign/1"
CONTRACT = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/line-campaign.schema.json"
CAMPAIGN_DIR = REPO_ROOT / "config/factory/campaigns"
PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
STATUSES = ("ACTIVE", "ON_HOLD", "DONE")
PURPOSES = ("ASPICE_ONLY", "QM", "DEVELOPMENT", "FORMAL_REVIEW")
TOP_KEYS = {"schema", "campaign_id", "line", "wo_prefix", "lineages", "note"}
LINEAGE_KEYS = {"id", "status", "example", "tag", "series", "driver_class", "factory_revision", "profile", "run_model",
                "purpose", "phases", "start", "provided_from", "depends_on", "after", "priority", "quality", "completed_by",
                "note"}
REQUIRED = ("id", "example", "tag", "series", "driver_class", "factory_revision", "profile", "run_model", "phases")
RX = {
    "campaign_id": re.compile(r"^CMP-[A-Z0-9][A-Z0-9-]{2,62}$"),
    "line": re.compile(r"^[a-z0-9-]{1,32}$"),
    "wo_prefix": re.compile(r"^WO(-F\d{1,4})?(-CMP)?$"),
    "id": re.compile(r"^[a-z0-9][a-z0-9-]{1,47}$"),
    "example": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$"),
    "tag": re.compile(r"^[A-Z0-9]{2,16}$"),
    "series": re.compile(r"^\d{8}-[A-Za-z0-9]{1,12}$"),
    "driver_class": re.compile(r"^[A-Z0-9][A-Z0-9_]{2,63}$"),
    "factory_revision": re.compile(r"^[0-9a-f]{7,40}$"),
    "profile": re.compile(r"^[a-z0-9][a-z0-9.-]{0,120}$"),
    "run_model": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,200}$"),
    "wo": re.compile(r"^WO-[A-Za-z0-9][A-Za-z0-9-]{2,120}$"),
}


class CampaignError(ValueError):
    pass


@dataclass
class Lineage:
    campaign_id: str
    id: str
    status: str
    example: str
    tag: str
    series: str
    driver_class: str
    factory_revision: str | None
    profile: str
    run_model: str
    purpose: str
    phases: tuple[str, ...]
    priority: int
    start: dict | None = None
    provided_from: str | None = None
    depends_on: dict | None = None
    after: dict | None = None  # feature 019: wait for that lineage's phase PASS without building on it
    quality: dict | None = None
    completed_by: str | None = None
    wo_prefix: str = "WO-F014"
    sha256: str = ""          # canonical JSON of the lineage block: every placed order is bound to it
    position: int = 0         # order in the campaign file (priority tie-break)

    @property
    def key(self) -> str:
        return f"{self.campaign_id}/{self.id}"

    def wo(self, phase: str, n: int = 1) -> str:
        """The phase order name of attempt n (1 = the series name; 2, 3, ... append B, C, ..., Z, AA, AB, ...)."""
        return f"{self.wo_prefix}-SWE{phase[-1]}-{self.tag}-{self.series}{retry_suffix(n)}"


@dataclass
class Campaign:
    path: Path
    rel: str
    campaign_id: str
    line: str
    sha256: str               # sha256 of the file bytes (the queue's manifest_sha256)
    commit: str | None        # the last commit that changed the file (the owner's approval)
    root: Path | None = None  # the git checkout the file is committed in (the queue's input_manifest_ref base)
    lineages: list[Lineage] = field(default_factory=list)


def retry_suffix(n: int) -> str:
    if n < 1:
        raise ValueError("attempt numbers start at 1")
    if n == 1:
        return ""
    out = ""
    while n:  # bijective base 26: 2 -> B, 26 -> Z, 27 -> AA
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _contiguous(phases: list) -> bool:
    idx = [PHASES.index(p) for p in phases]
    return idx == list(range(idx[0], idx[0] + len(idx)))


def validate(doc, *, purpose_check: bool = True) -> list[str]:
    """Code-level validation (the authority). Returns issue codes; [] = valid."""
    from ..quality import validate as quality_errors

    if not isinstance(doc, dict):
        return ["CAMPAIGN_NOT_A_MAPPING"]
    out = [f"UNKNOWN_KEY:{k}" for k in doc if k not in TOP_KEYS]
    if doc.get("schema") != SCHEMA_ID:
        out.append("SCHEMA_ID")
    for k in ("campaign_id", "line"):
        if not isinstance(doc.get(k), str) or not RX[k].match(doc[k]):
            out.append(f"FIELD_INVALID:{k}")
    if "wo_prefix" in doc and (not isinstance(doc["wo_prefix"], str) or not RX["wo_prefix"].match(doc["wo_prefix"])):
        out.append("FIELD_INVALID:wo_prefix")
    if str(doc.get("wo_prefix", "")).endswith("-CMP") and doc.get("line") != "cloud":
        out.append("FIELD_INVALID:wo_prefix_cloud_only")
    lins = doc.get("lineages")
    if not isinstance(lins, list) or not lins:
        return out + ["LINEAGES_REQUIRED"]
    ids = [x.get("id") for x in lins if isinstance(x, dict)]
    for i, L in enumerate(lins):
        p = f"lineages[{i}]"
        if not isinstance(L, dict):
            out.append(f"{p}:NOT_A_MAPPING")
            continue
        out += [f"{p}:UNKNOWN_KEY:{k}" for k in L if k not in LINEAGE_KEYS]
        out += [f"{p}:REQUIRED:{k}" for k in REQUIRED if k not in L]
        for k in ("id", "example", "tag", "series", "driver_class", "profile", "run_model"):
            if k in L and (not isinstance(L[k], str) or not RX[k].match(L[k])):
                out.append(f"{p}:FIELD_INVALID:{k}")
        fr = L.get("factory_revision")
        if "factory_revision" in L and fr is not None and (not isinstance(fr, str) or not RX["factory_revision"].match(fr)):
            out.append(f"{p}:FIELD_INVALID:factory_revision")
        st = L.get("status", "ACTIVE")
        if st not in STATUSES:
            out.append(f"{p}:FIELD_INVALID:status")
        purpose = L.get("purpose", "ASPICE_ONLY")
        if purpose not in PURPOSES:
            out.append(f"{p}:FIELD_INVALID:purpose")
        ph = L.get("phases")
        if not isinstance(ph, list) or not ph or any(x not in PHASES for x in ph) or len(set(ph)) != len(ph) \
                or not _contiguous(ph):
            out.append(f"{p}:FIELD_INVALID:phases")
            ph = None
        pr = L.get("priority", 50)
        if not isinstance(pr, int) or isinstance(pr, bool) or not 0 <= pr <= 100:
            out.append(f"{p}:FIELD_INVALID:priority")
        s = L.get("start")
        if s is not None:
            if not isinstance(s, dict) or set(s) != {"resume_from", "at"} or not isinstance(s.get("resume_from"), str) \
                    or not RX["wo"].match(s["resume_from"]) or (ph and s.get("at") not in ph) or s.get("at") == "SWE.1":
                out.append(f"{p}:FIELD_INVALID:start")
        if L.get("provided_from") is not None and (not isinstance(L["provided_from"], str)
                                                   or not RX["wo"].match(L["provided_from"])):
            out.append(f"{p}:FIELD_INVALID:provided_from")
        d = L.get("depends_on")
        if d is not None:
            if L.get("provided_from") is not None:
                out.append(f"{p}:PROVIDED_FROM_AND_DEPENDS_ON")
            if not isinstance(d, dict) or set(d) != {"lineage", "phase", "verdict"} or d.get("verdict") != "PASS" \
                    or d.get("phase") not in PHASES or d.get("lineage") not in ids or d.get("lineage") == L.get("id"):
                out.append(f"{p}:FIELD_INVALID:depends_on")
        a = L.get("after")  # feature 019 (owner 2026-11-09): the ladder's next step waits, builds on nothing
        if a is not None and (not isinstance(a, dict) or set(a) != {"lineage", "phase", "verdict"}
                              or a.get("verdict") != "PASS" or a.get("phase") not in PHASES
                              or a.get("lineage") not in ids or a.get("lineage") == L.get("id")):
            out.append(f"{p}:FIELD_INVALID:after")
        if st == "DONE" and (not isinstance(L.get("completed_by"), str) or not RX["wo"].match(L["completed_by"])):
            out.append(f"{p}:DONE_NEEDS_COMPLETED_BY")
        if st != "DONE" and L.get("completed_by") is not None:
            out.append(f"{p}:COMPLETED_BY_ONLY_WHEN_DONE")
        if L.get("quality") is not None and purpose_check:
            out += [f"{p}:QUALITY:{e}"[:200] for e in quality_errors(L["quality"], purpose)]
        if L.get("note") is not None and (not isinstance(L["note"], str) or len(L["note"]) > 400):
            out.append(f"{p}:FIELD_INVALID:note")
    if len(set(ids)) != len(ids):
        out.append("LINEAGE_ID_DUPLICATE")
    tags = [(x.get("tag"), x.get("series")) for x in lins if isinstance(x, dict)]
    if len(set(tags)) != len(tags):
        out.append("TAG_SERIES_DUPLICATE")
    # no dependency cycle over depends_on and after (feature 019)
    def _edge(x, k):
        v = x.get(k)
        return v.get("lineage") if isinstance(v, dict) else None

    dep = {x.get("id"): [e for e in (_edge(x, "depends_on"), _edge(x, "after")) if e] for x in lins if isinstance(x, dict)}
    for start in dep:
        seen, todo = set(), list(dep[start])
        while todo:
            cur = todo.pop()
            if cur == start:
                out.append(f"DEPENDENCY_CYCLE:{start}")
                break
            if cur in seen:
                continue
            seen.add(cur)
            todo += dep.get(cur, [])
    return out


def contract_errors(doc) -> list[str] | None:
    """The JSON contract's verdict when installed (None when this checkout has no contract)."""
    if not CONTRACT.is_file():
        return None
    import jsonschema

    v = jsonschema.Draft202012Validator(json.loads(CONTRACT.read_text()))
    return [f"CONTRACT:{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:200] for e in v.iter_errors(doc)]


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)


def approval(path: Path) -> tuple[str | None, str]:
    """(commit, code): the file must be tracked and unmodified in its git checkout (the owner approves by commit)."""
    d = path.parent
    if _git(d, "ls-files", "--error-unmatch", path.name).returncode != 0:
        return None, "CAMPAIGN_NOT_COMMITTED"
    if _git(d, "diff", "--quiet", "HEAD", "--", path.name).returncode != 0:
        return None, "CAMPAIGN_MODIFIED_SINCE_COMMIT"
    c = _git(d, "log", "-1", "--format=%H", "--", path.name).stdout.strip()
    return (c or None), ("CAMPAIGN_APPROVED" if c else "CAMPAIGN_NOT_COMMITTED")


def _repo_rel(path: Path) -> tuple[Path, str]:
    top = _git(path.parent, "rev-parse", "--show-toplevel").stdout.strip()
    try:
        return (Path(top), str(path.resolve().relative_to(Path(top).resolve()))) if top else (path.parent, path.name)
    except ValueError:
        return path.parent, path.name


def parse(path: Path, *, require_approval: bool = True) -> Campaign:
    import yaml

    raw = path.read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise CampaignError(f"CAMPAIGN_NOT_YAML:{type(exc).__name__}") from None
    errs = validate(doc)
    cerrs = contract_errors(doc)
    if errs or cerrs:
        raise CampaignError("CAMPAIGN_INVALID:" + "; ".join((errs + (cerrs or []))[:4]))
    commit, code = approval(path) if require_approval else (None, "APPROVAL_NOT_REQUIRED")
    if require_approval and commit is None:
        raise CampaignError(code)
    root, rel = _repo_rel(path)
    c = Campaign(path=path, rel=rel, campaign_id=doc["campaign_id"], line=doc["line"], sha256=sha256_bytes(raw),
                 commit=commit, root=root)
    prefix = doc.get("wo_prefix", "WO-F014")
    for i, L in enumerate(doc["lineages"]):
        c.lineages.append(Lineage(
            campaign_id=c.campaign_id, id=L["id"], status=L.get("status", "ACTIVE"), example=L["example"], tag=L["tag"],
            series=L["series"], driver_class=L["driver_class"], factory_revision=L["factory_revision"],
            profile=L["profile"], run_model=L["run_model"], purpose=L.get("purpose", "ASPICE_ONLY"),
            phases=tuple(L["phases"]), priority=int(L.get("priority", 50)), start=L.get("start"),
            provided_from=L.get("provided_from"), depends_on=L.get("depends_on"), after=L.get("after"),
            quality=L.get("quality"),
            completed_by=L.get("completed_by"), wo_prefix=prefix, sha256=sha256_bytes(canonical_json(L)), position=i))
    return c


def load_all(directory: Path | None = None, *, line: str | None = None, require_approval: bool = True
             ) -> tuple[list[Campaign], list[dict]]:
    """(campaigns, rejected): every *.yaml of the directory; a file that does not validate or is not approved is
    rejected with its code and never planned. Tags+series must be unique across the loaded campaigns of a line."""
    directory = Path(directory or CAMPAIGN_DIR)
    good, bad = [], []
    for p in sorted(directory.glob("*.yaml")) if directory.is_dir() else []:
        try:
            c = parse(p, require_approval=require_approval)
        except (CampaignError, OSError) as exc:
            bad.append({"file": p.name, "code": str(exc)[:300]})
            continue
        if line is not None and c.line != line:
            continue  # another line's campaign
        good.append(c)
    seen: dict = {}
    for c in list(good):
        clash = [f"{L.tag}-{L.series}" for L in c.lineages if (L.tag, L.series) in seen]
        ids = [c2.campaign_id for c2 in good if c2 is not c and c2.campaign_id == c.campaign_id]
        if clash or ids:
            good.remove(c)
            bad.append({"file": c.path.name, "code": f"CAMPAIGN_CONFLICT:{','.join(clash) or 'campaign_id ' + c.campaign_id}"})
            continue
        for L in c.lineages:
            seen[(L.tag, L.series)] = c.campaign_id
    return good, bad
