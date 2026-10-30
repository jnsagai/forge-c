"""Execute authored peripheral models in a small, offline filesystem view.

Authored models use arithmetic, containers, functions and request.{IsInit,IsRead,
IsWrite,Offset,Length,Value}. Imports, reflection, file/process access and output
are refused before execution. The Renode process sees its distribution, system
libraries and one scratch directory; it cannot read the hand model or owner home.
Existing trusted models retain their existing gate path.
"""
from __future__ import annotations

import ast
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from ..mcp.sdk import ProcResult, _limits

BUILTINS = {"abs", "bool", "dict", "enumerate", "hex", "int", "len", "list", "max", "min", "range",
            "reversed", "sum", "tuple", "zip"}
METHODS = {"append", "clear", "copy", "get", "items", "keys", "pop", "update", "values"}
REQUEST_FIELDS = {"IsInit", "IsRead", "IsWrite", "Offset", "Length", "Value"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "globals", "locals", "vars", "dir", "getattr", "setattr",
                   "delattr", "input", "print", "help", "breakpoint", "exit", "quit", "type", "object", "super"}
MAX_SOURCE = 64 * 1024
MAX_LOG = 1024 * 1024


def source_issues(text: str) -> list[str]:
    """A deliberately small executable language, independent of inspector judgment."""
    if len(text.encode()) > MAX_SOURCE:
        return ["MODEL_SOURCE_TOO_LARGE"]
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return ["MODEL_SOURCE_SYNTAX"]
    functions = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    issues = set()
    forbidden = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Lambda, ast.With, ast.AsyncWith, ast.AsyncFunctionDef,
                 ast.Await, ast.Yield, ast.YieldFrom, ast.Delete, ast.JoinedStr, ast.AnnAssign, ast.NamedExpr, ast.Match,
                 ast.Raise, ast.Assert, ast.Try)
    for node in ast.walk(tree):
        if isinstance(node, forbidden):
            issues.add("MODEL_SOURCE_FORBIDDEN:" + type(node).__name__)
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in FORBIDDEN_NAMES):
            issues.add("MODEL_SOURCE_NAME:" + node.id)
        if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.name.startswith("__") or
                                                node.name in FORBIDDEN_NAMES):
            issues.add("MODEL_SOURCE_FUNCTION:" + node.name)
        if isinstance(node, ast.Attribute):
            request = isinstance(node.value, ast.Name) and node.value.id == "request"
            if not (request and node.attr in REQUEST_FIELDS or
                    not request and isinstance(node.value, ast.Name) and node.attr in METHODS):
                issues.add("MODEL_SOURCE_ATTRIBUTE:" + node.attr)
            if isinstance(node.ctx, ast.Store) and not (request and node.attr == "Value"):
                issues.add("MODEL_SOURCE_ATTRIBUTE_WRITE:" + node.attr)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in BUILTINS | functions:
                    issues.add("MODEL_SOURCE_CALL:" + node.func.id)
            elif not (isinstance(node.func, ast.Attribute) and node.func.attr in METHODS):
                issues.add("MODEL_SOURCE_CALL:indirect")
    return sorted(issues)


def argv(renode: Path, scratch: Path, args: list[str]) -> list[str]:
    """Build a new mount/PID/network namespace. No host repo or home is mounted."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("MODEL_SANDBOX_UNAVAILABLE:bwrap")
    renode, scratch = renode.resolve(strict=True), scratch.resolve(strict=True)
    if not renode.is_file() or not scratch.is_dir() or scratch == Path("/"):
        raise ValueError("MODEL_SANDBOX_PATH")
    for path in scratch.rglob("*"):
        if path.is_symlink():
            raise ValueError("MODEL_SANDBOX_SYMLINK")
    command = [bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL"]
    for path in (Path("/usr"), Path("/lib"), Path("/lib64"), Path("/etc")):
        if path.exists():
            command += ["--ro-bind", str(path), str(path)]
    command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--ro-bind", str(renode.parent), str(renode.parent),
                "--bind", str(scratch), str(scratch), "--chdir", str(scratch),
                "--setenv", "HOME", str(scratch), "--setenv", "TMPDIR", "/tmp", "--", str(renode), *args]
    return command


def run(renode: Path, scratch: Path, args: list[str], timeout: int = 170) -> ProcResult:
    command = argv(renode, scratch, args)
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
                   "HOME": str(scratch), "DOTNET_EnableWriteXorExecute": "0", "DOTNET_GCHeapHardLimit": "0x60000000"}
    start, timed_out, code = time.monotonic(), False, 1
    # A file descriptor plus RLIMIT_FSIZE bounds output without buffering an untrusted pipe in the broker.
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=scratch, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   preexec_fn=_limits(65536, timeout + 5, 4))
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            code = 124
        length = log.seek(0, 2)
        log.seek(0)
        output = log.read(MAX_LOG)
    if length > MAX_LOG:
        code, output = 125, output + b"\nMODEL_SANDBOX_LOG_LIMIT\n"
    if timed_out:
        output += b"\nMODEL_SANDBOX_TIMEOUT\n"
    return ProcResult(command, code, output, b"", (time.monotonic() - start) * 1000, timed_out)
