"""Model-free controller evidence export. Product export v1 is unchanged.

No synthetic product workspace, native execution, inference or defect verdict.
The caller supplies a sealed, whitelisted observation; this module only renders
sanitized deterministic bytes. Filesystem persistence belongs to the caller.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

from jsonschema import Draft202012Validator

from ..common import REPO_ROOT
from .export import FIXED_TIME, _clean

CONTRACT = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/controller-export.schema.json"
MAX_BYTES = 1024 * 1024


def _json(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def _require(value, *, case=False):
    schema = json.loads(CONTRACT.read_text())
    if case:
        schema = schema["$defs"]["case"]
    if not Draft202012Validator(schema).is_valid(value):
        raise ValueError("CONTROLLER_EXPORT_SCHEMA_INVALID")


def render(case: dict) -> dict:
    _require(case, case=True)
    n = [0, 0]
    cleaned = _clean(case, n)
    body = _json(cleaned)
    if len(body) > MAX_BYTES // 2:
        raise ValueError("CONTROLLER_EXPORT_BYTE_BOUND")
    # Evidence is JSON-fenced data, never executable instructions/active markup.
    fence = "~" * max(3, 1 + max((len(x) for x in __import__("re").findall(r"~+", body.decode())), default=0))
    report = (
        "# Forge-C controller escalation report\n\n"
        "Observed controller failure requiring external engineering review. "
        "This is not a verified defect, product run, acceptance or release.\n\n"
        "No native run is recorded. Original charges and unknown usage remain conserved. "
        "No replay, model request, automatic merge or factory promotion is authorized. "
        "Transfer this bundle manually for analysis; return patches through the normal reviewed gates.\n\n"
        + fence
        + "json\n"
        + body.decode()
        + fence
        + "\n"
    ).encode()
    manifest = dict(
        schema="forge-c/controller-export/1",
        case_id=case["case_id"],
        classification=case["classification"],
        native_run="NOT_RECORDED",
        case_sha256=hashlib.sha256(body).hexdigest(),
        report_sha256=hashlib.sha256(report).hexdigest(),
        stripped_keys=n[0],
        redactions=n[1],
    )
    _require(manifest)
    blobs = {"CASE.json": body, "REPORT.md": report, "MANIFEST.json": _json(manifest)}
    blobs["SHA256SUMS.txt"] = "".join(hashlib.sha256(v).hexdigest() + "  " + k + "\n" for k, v in sorted(blobs.items())).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in sorted(blobs.items()):
            entry = zipfile.ZipInfo(name, FIXED_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o444 << 16
            z.writestr(entry, data)
    archive = out.getvalue()
    if len(archive) + len(report) > MAX_BYTES:
        raise ValueError("CONTROLLER_EXPORT_BYTE_BOUND")
    return dict(archive=archive, report=report, manifest=manifest, sha256=hashlib.sha256(archive).hexdigest())


def verify(archive: bytes) -> list[str]:
    try:
        if len(archive) > MAX_BYTES:
            raise ValueError("BYTE_BOUND")
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            expected = {"CASE.json", "REPORT.md", "MANIFEST.json", "SHA256SUMS.txt"}
            if set(z.namelist()) != expected or len(z.namelist()) != 4:
                raise ValueError("MEMBERS")
            if sum(x.file_size for x in z.infolist()) > MAX_BYTES:
                raise ValueError("BYTE_BOUND")
            blobs = {n: z.read(n) for n in z.namelist()}
        sums = dict(line.split("  ", 1)[::-1] for line in blobs["SHA256SUMS.txt"].decode().splitlines())
        if set(sums) != expected - {"SHA256SUMS.txt"}:
            raise ValueError("HASH_INVENTORY")
        for name, digest in sums.items():
            if hashlib.sha256(blobs[name]).hexdigest() != digest:
                raise ValueError("HASH_MISMATCH")
        m, c = json.loads(blobs["MANIFEST.json"]), json.loads(blobs["CASE.json"])
        _require(m)
        _require(c, case=True)
        if m["case_sha256"] != sums["CASE.json"] or m["report_sha256"] != sums["REPORT.md"] or m["case_id"] != c["case_id"]:
            raise ValueError("CASE_BINDING")
        return []
    except (ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile):
        return ["CONTROLLER_EXPORT_INVALID"]
