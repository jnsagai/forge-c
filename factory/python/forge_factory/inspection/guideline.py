"""Deterministic HAL/LL coding-guideline verification (SWE.3 verification node, checklist SWE3-07).

Implements the automatable subset of the ST Cube2 HAL SAD v1.2 (rules in
config/factory/guidelines/st-cube2-hal-v1.2.yaml, pinned to the guideline hash). Lexical C analysis
on comment/string-stripped source; findings cite rule ID, guideline section, file and line.
Judgement-based guideline content stays a manual inspection item and is never claimed here.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..common import REPO_ROOT, sha256_file

RULES_FILE = REPO_ROOT / "config/factory/guidelines/st-cube2-hal-v1.2.yaml"
C_TYPES_SIZE = {"uint8_t": 1, "int8_t": 1, "char": 1, "uint16_t": 2, "int16_t": 2, "uint32_t": 4, "int32_t": 4,
                "uint64_t": 8, "int64_t": 8, "float": 4, "double": 8}


def load_rules(path: Path = RULES_FILE) -> dict:
    data = yaml.safe_load(path.read_text())
    src = REPO_ROOT / data["guideline"]["source"]
    data["guideline_hash_ok"] = src.is_file() and sha256_file(src) == data["guideline"]["sha256"]
    return data


C_STATEMENT_KEYWORDS = {"return", "else", "case", "goto", "do", "sizeof", "typedef", "break", "continue", "default"}


def strip_c(src: str) -> str:
    """Remove comments and string/char literals, preserving line structure."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", src[i:j]))
            i = j
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append(c + " " * max(0, j - i - 1) + (c if j < n else ""))
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


class Checker:
    def __init__(self, ws: Path, rules: dict):
        self.ws, self.rules = ws, rules
        self.sev = {r["id"]: r for r in rules["rules"]}
        from ..layer import profile  # feature 009: the work order's peripheral (the rule file names RCC by default)

        self.ppp = profile(ws)["id"] if (Path(ws) / ".forge-run/manifest.json").is_file() else rules["peripheral"].lower()
        self.PPP = self.ppp.upper()
        self.series = rules["series_prefix"]
        self.violations: list[dict] = []

    def v(self, rule: str, file: str, line: int, detail: str) -> None:
        r = self.sev[rule]
        self.violations.append({"rule": rule, "section": r["section"], "severity": r["severity"], "file": file,
                                "line": line, "detail": detail[:160]})

    def files(self) -> tuple[list[Path], list[Path]]:
        lay = self.rules["layout"]
        hal = sorted((self.ws / lay["hal_dir"]).glob("*.[ch]")) if (self.ws / lay["hal_dir"]).is_dir() else []
        ll = sorted((self.ws / lay["ll_dir"]).glob("*.[ch]")) if (self.ws / lay["ll_dir"]).is_dir() else []
        return hal, ll

    def check_layout(self, hal: list[Path], ll: list[Path]) -> None:
        from ..layer import layer_of

        lay = self.rules["layout"]
        required = [(lay["ll_dir"], lay["ll_files"])]  # ADR-0009: an LL work order has no HAL files
        if layer_of(self.ws) != "LL":
            required.insert(0, (lay["hal_dir"], lay["hal_files"]))
        for d, names in required:
            for name in names:
                p = self.ws / d / name.format(ppp=self.ppp)
                if not p.is_file():
                    self.v("GL-FILE-01", f"{d}/{name.format(ppp=self.ppp)}", 0, "required file missing")
        for p in ll:
            if p.suffix == ".c":
                self.v("GL-FILE-02", self.rel(p), 0, "LL source file not allowed")
        for p in hal + ll:
            if not re.fullmatch(rf"{self.series}_(hal|ll)_[a-z0-9_]+\.[ch]", p.name):
                self.v("GL-FILE-01", self.rel(p), 0, "file name does not follow stm32n6xx_{hal|ll}_ppp")

    def rel(self, p: Path) -> str:
        return p.relative_to(self.ws).as_posix()

    def check_header_guard(self, p: Path, raw: str) -> None:
        guard = p.name.upper().replace(".", "_")
        lines = [ln.strip() for ln in strip_c(raw).splitlines() if ln.strip()]
        ok = (len(lines) >= 3 and lines[0] == f"#ifndef {guard}" and lines[1] == f"#define {guard}"
              and lines[-1].startswith("#endif") and re.search(rf"#endif\s*/\*\s*{guard}\s*\*/", raw))
        if not ok:
            self.v("GL-GUARD-01", self.rel(p), 1, f"expected guard {guard} with '#endif /* {guard} */'")

    def check_common(self, p: Path, raw: str, layer: str) -> None:
        s = strip_c(raw)
        rel = self.rel(p)
        for m in re.finditer(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", s, re.M):
            name = m.group(1)
            if name.startswith("_"):
                self.v("GL-MACRO-01", rel, _line(s, m.start()), f"macro {name} starts with underscore")
            elif name != name.upper():
                self.v("GL-MACRO-01", rel, _line(s, m.start()), f"macro {name} not all capital")
        for m in re.finditer(r"^\s*#\s*(?:if|elif)\b.*\bdefined\s*\(?\s*(STM32N6[0-9A-Z]{2,}xx)\b", s, re.M | re.I):
            self.v("GL-RPN-01", rel, _line(s, m.start()), f"device RPN conditional {m.group(1)}")
        for m in re.finditer(r"\}\s*([A-Za-z_][A-Za-z0-9_]*)\s*;|typedef\s+[^;{}]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*;", s):
            name = m.group(1) or m.group(2)
            if m.group(1) and not self._closes_typedef(s, m.start()):
                continue
            if name != name.lower() or not name.endswith("_t"):
                self.v("GL-TYPE-01", rel, _line(s, m.start()), f"typedef {name} must be lower case ending _t")
            elif p.suffix == ".h" and not name.startswith("hal_" if layer == "hal" else "ll_"):
                self.v("GL-TYPE-02", rel, _line(s, m.start()), f"exported type {name} lacks {layer}_ prefix")
        for m in re.finditer(r"\bwhile\s*\(([^;{]*)\)", s):
            cond = m.group(1)
            if re.fullmatch(r"\s*(1|true|1U|1u)\s*", cond) or not re.search(
                    r"(?i)timeout|tick|count|cnt|retr|attempt|loop|remaining|budget|i\b|n\b", cond):
                # do { } while(cond) counts too
                self.v("GL-LOOP-01", rel, _line(s, m.start()), f"loop not timeout-bounded: while({cond.strip()[:60]})")
        for m in re.finditer(r"\bfor\s*\(\s*;\s*;\s*\)", s):
            self.v("GL-LOOP-01", rel, _line(s, m.start()), "for(;;) infinite loop")
        arr = r"\b(u?int(?:8|16|32|64)_t|char|float|double)\s+[a-z_][a-z0-9_]*\s*\[\s*(\d+)[uU]?\s*\]"
        for m in re.finditer(arr, s):
            size = C_TYPES_SIZE.get(m.group(1), 4) * int(m.group(2))
            if size > 128 and not re.match(r"\s*(static|const)", s[s.rfind("\n", 0, m.start()) + 1: m.start()]):
                self.v("GL-ARRAY-01", rel, _line(s, m.start()), f"local array {size} bytes > 128")

    @staticmethod
    def _closes_typedef(s: str, close_pos: int) -> bool:
        depth, i = 0, close_pos
        while i >= 0:
            if s[i] == "}":
                depth += 1
            elif s[i] == "{":
                depth -= 1
                if depth == 0:
                    head = s[max(0, s.rfind(";", 0, i), s.rfind("}", 0, i), s.rfind("#", 0, i)) : i]
                    return "typedef" in head
            i -= 1
        return False

    def functions(self, s: str) -> list[tuple[str, str, str, int]]:
        """(qualifiers+return, name, params, pos) for prototypes and definitions."""
        out = []
        for m in re.finditer(r"^[ \t]*((?:static\s+|inline\s+|__STATIC_INLINE\s+|__WEAK\s+|const\s+|extern\s+)*"
                             r"[A-Za-z_][A-Za-z0-9_]*(?:\s*\*+\s*|\s+))([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;{)]*)\)\s*[;{]",
                             s, re.M):
            if m.group(2) in ("if", "while", "for", "switch", "return", "sizeof"):
                continue
            if m.group(1).split()[-1].strip("*") in C_STATEMENT_KEYWORDS:  # r26: 'return f(x);' is a call, not a decl
                continue
            out.append((m.group(1), m.group(2), m.group(3), m.start()))
        return out

    def check_api(self, p: Path, raw: str, layer: str) -> None:
        s = strip_c(raw)
        rel = self.rel(p)
        for quals, name, params, pos in self.functions(s):
            line = _line(s, pos)
            is_static = "static" in quals or "__STATIC_INLINE" in quals
            if layer == "hal" and not is_static and not name.startswith(f"HAL_{self.PPP}_") \
                    and not name.startswith("HAL_"):
                self.v("GL-API-01", rel, line, f"exported HAL function {name} lacks HAL_{self.PPP}_ prefix")
            if layer == "ll":
                if not name.startswith(f"LL_{self.PPP}_") and not name.startswith("LL_"):
                    self.v("GL-API-02", rel, line, f"LL function {name} lacks LL_{self.PPP}_ prefix")
                if not ("__STATIC_INLINE" in quals or ("static" in quals and "inline" in quals)):
                    self.v("GL-API-02", rel, line, f"LL function {name} is not static inline")
            if params.strip() in ("", "void"):
                continue
            for prm in params.split(","):
                pm = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*(\[\s*\])?\s*$", prm.strip())
                if not pm:
                    continue
                pname = pm.group(1)
                if pname != pname.lower():
                    self.v("GL-ARG-01", rel, line, f"{name}: parameter {pname} not lower case")
                if "*" in prm and re.search(r"(config|cfg|init)", pname) and "const" not in prm:
                    self.v("GL-CONST-01", rel, line, f"{name}: pointer {pname} must be const-qualified")
        for m in re.finditer(r"struct\s*[a-z_0-9]*\s*\{([^{}]*)\}", s):
            for fm in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\])?\s*;", m.group(1)):
                if fm.group(1) != fm.group(1).lower():
                    self.v("GL-ARG-01", rel, _line(s, m.start()), f"structure field {fm.group(1)} not lower case")

    def check_enums(self, p: Path, raw: str, layer: str) -> None:
        s = strip_c(raw)
        rel = self.rel(p)
        for m in re.finditer(r"\benum\b\s*[A-Za-z_0-9]*\s*\{([^}]*)\}", s):
            if layer == "ll":
                self.v("GL-ENUM-01", rel, _line(s, m.start()), "enumeration not allowed in LL")
                continue
            for vm in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:=[^,]*)?(?:,|$)", m.group(1).strip()):
                if not vm.group(1).startswith("HAL_"):
                    self.v("GL-ENUM-02", rel, _line(s, m.start()), f"enum value {vm.group(1)} lacks HAL_ prefix")

    def check_hal_header_macros(self, p: Path, raw: str) -> None:
        s = strip_c(raw)
        for m in re.finditer(r"^\s*#\s*define\s+(HAL_[A-Z0-9_]+)\s*\([^)]*\)\s*(.*)$", s, re.M):
            if re.search(r"->|READ_REG|WRITE_REG|SET_BIT|CLEAR_BIT|MODIFY_REG|\b" + self.PPP + r"\b", m.group(2)):
                self.v("GL-MACRO-02", self.rel(p), _line(s, m.start()),
                       f"exported macro {m.group(1)} accesses registers")
        if "hal_status_t" not in s and p.name.endswith(f"hal_{self.ppp}.h"):
            self.v("GL-STATUS-01", self.rel(p), 0, "hal_status_t not used by HAL API")

    def run(self) -> dict:
        hal, ll = self.files()
        self.check_layout(hal, ll)
        for layer, files in (("hal", hal), ("ll", ll)):
            for p in files:
                raw = p.read_text(encoding="utf-8", errors="replace")
                if p.suffix == ".h":
                    self.check_header_guard(p, raw)
                self.check_common(p, raw, layer)
                self.check_api(p, raw, layer)
                self.check_enums(p, raw, layer)
                if layer == "hal" and p.suffix == ".h":
                    self.check_hal_header_macros(p, raw)
        major = [x for x in self.violations if x["severity"] == "major"]
        verdict = "PASS" if not major and self.rules["guideline_hash_ok"] and (hal or ll) else "FAIL"
        return {"check_id": "SWE3-07", "guideline": self.rules["guideline"]["title"],
                "guideline_version": self.rules["guideline"]["version"],
                "guideline_sha256": self.rules["guideline"]["sha256"],
                "guideline_hash_ok": self.rules["guideline_hash_ok"], "verdict": verdict,
                "files_checked": [self.rel(p) for p in hal + ll],
                "rules_applied": [r["id"] for r in self.rules["rules"]],
                "violations": self.violations,
                "not_automated": "API semantics, process models and documentation completeness: manual SWE3 items"}


def check_workspace(ws: Path, rules_path: Path = RULES_FILE) -> dict:
    return Checker(ws, load_rules(rules_path)).run()
