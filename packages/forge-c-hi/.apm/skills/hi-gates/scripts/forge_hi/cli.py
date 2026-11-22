"""`hi` command line (contracts/cli-and-mcp.md). One compact JSON object on stdout, exit 0/1/2."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, api
from .config import ConfigError, find_root


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # usage errors are exit 2 with a JSON reply
        _emit(2, {"cmd": self.prog, "status": "ERROR", "error": message})


def _emit(code: int, payload: dict) -> None:
    sys.stdout.write(json.dumps(api.compact(payload), separators=(",", ":"), sort_keys=True) + "\n")
    sys.stdout.flush()
    raise SystemExit(code)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="hi", description="forge-c-hi deterministic gates")
    p.add_argument("--root", help="project root (default: nearest folder with .hi/project.json, else cwd)")
    p.add_argument("--version", action="version", version=f"forge-c-hi {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)

    s = sub.add_parser("init", help="create .hi/project.json and hash the inputs")
    s.add_argument("--level", help="HI-0..HI-4")
    s.add_argument("--profile", help="standard profile (default generic)")
    s.add_argument("--class", dest="input_class", help="natural_language | reference_document")
    s.add_argument("--entry", help="entry stage")
    s.add_argument("--stages", help="comma-separated stage list")
    s.add_argument("--input", action="append", default=[], help="PATH:KIND[:DOC_ID], repeatable")
    s.add_argument("--project-id")
    for r in ("author", "inspector"):
        s.add_argument(f"--{r}", help="harness preset (claude-code, codex, codex-oss-ollama, manual)")
        s.add_argument(f"--{r}-model")
        s.add_argument(f"--{r}-family")
    s.add_argument("--from", dest="from_file", help="start from an example project JSON")
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("doc-index", help="section/page outline of your own reference document")
    s.add_argument("pdf")
    s.add_argument("--doc-id", required=True)
    s = sub.add_parser("validate", help="schema and envelope check")
    s.add_argument("file")
    s = sub.add_parser("quality", help="deterministic requirement-quality rules")
    s.add_argument("stage")
    s = sub.add_parser("trace", help="bidirectional traceability")
    s.add_argument("--stage")
    s = sub.add_parser("scope", help="changed files within the role write scope")
    s.add_argument("--role", required=True)
    s.add_argument("--stage", required=True)
    s.add_argument("--snapshot")
    s = sub.add_parser("gate", help="all required gates for a stage")
    s.add_argument("stage")
    sub.add_parser("status", help="V-model position and verdicts")
    sub.add_parser("seal", help="sealed review package")
    s = sub.add_parser("role", help="set or clear the active role for the guard hook")
    rs = s.add_subparsers(dest="action", required=True, parser_class=_Parser)
    r = rs.add_parser("set")
    r.add_argument("role")
    r.add_argument("stage")
    r.add_argument("--run-id")
    rs.add_parser("clear")
    return p


def dispatch(args: argparse.Namespace, root: Path) -> tuple[int, dict]:
    c = args.cmd
    if c == "init":
        return api.init(root, level=args.level, profile=args.profile, input_class=args.input_class, entry=args.entry,
                        inputs=args.input, project_id=args.project_id, author=args.author, inspector=args.inspector,
                        author_model=args.author_model, inspector_model=args.inspector_model,
                        author_family=args.author_family, inspector_family=args.inspector_family,
                        from_file=args.from_file, force=args.force,
                        stages_list=args.stages.split(",") if args.stages else None)
    if c == "doc-index":
        return api.not_available("doc-index", "US2, T047-T049")
    if c == "validate":
        return api.validate(root, args.file)
    if c == "quality":
        return api.quality(root, args.stage)
    if c == "trace":
        return api.trace(root, args.stage)
    if c == "scope":
        return api.scope(root, args.role, args.stage, args.snapshot)
    if c == "gate":
        return api.gate(root, args.stage)
    if c == "status":
        return api.status(root)
    if c == "seal":
        return api.not_available("seal", "US5, T043-T044")
    if c == "role":
        return api.role_set(root, args.role, args.stage, args.run_id) if args.action == "set" else api.role_clear(root)
    raise ValueError(f"unknown command {c}")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else (Path.cwd() if args.cmd == "init" else find_root())
    try:
        code, payload = dispatch(args, root)
    except (ConfigError, ValueError, FileNotFoundError) as exc:
        _emit(2, {"cmd": args.cmd, "status": "ERROR", "error": str(exc)[:500]})
    _emit(code, payload)
