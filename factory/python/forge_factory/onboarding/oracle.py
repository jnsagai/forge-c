"""Feature 016 (OB-T002, OB-T019): the regression oracle - derived facts compared with the values written by hand in
the existing peripheral profiles and examples (FR-020). Differences are allowed only when listed, with an
explanation, in config/factory/onboarding/oracle-exceptions.yaml."""
from __future__ import annotations

from ..common import CONFIG_DIR, load_yaml

EXCEPTIONS = CONFIG_DIR / "onboarding/oracle-exceptions.yaml"
FIELDS = ("example", "fact", "hand_value", "derived_value", "explanation", "reviewed_by")


class OracleError(ValueError):
    pass


def exceptions() -> dict[tuple[str, str], dict]:
    doc = load_yaml(EXCEPTIONS) or {}
    if doc.get("schema") != "forge-c/onboarding-oracle-exceptions/0.1":
        raise OracleError("ORACLE_EXCEPTIONS_SCHEMA")
    out = {}
    for e in doc.get("exceptions") or []:
        missing = [k for k in FIELDS if k not in e or (k == "explanation" and not str(e[k]).strip())]
        if missing:
            raise OracleError(f"ORACLE_EXCEPTION_INCOMPLETE:{e.get('example')}:{e.get('fact')}:{','.join(missing)}")
        out[(e["example"], e["fact"])] = e
    return out


ORACLE_EXAMPLES = ("0008c-st-cube-rcc", "0010c-st-cube-gpio", "0011c-st-cube-spi", "0012c-st-cube-usart",
                   "0013c-st-cube-tim", "0014c-st-cube-crc", "0010d-st-cube-gpio-hal", "0011d-st-cube-spi-hal",
                   "0012d-st-cube-usart-hal", "0013d-st-cube-tim-hal", "0014d-st-cube-crc-hal")  # every ST delivery


def hand_values(example) -> dict:
    """The derivable values written by hand for an existing example: its profile and its delivery block."""
    import json
    import re
    from pathlib import Path

    from ..peripheral import load

    spec = json.loads((Path(example) / "workorder.json").read_text())
    prof = load(spec.get("peripheral") or "rcc")
    d = spec["delivery"]
    hal = d["scope"]["functions"][0].startswith("HAL_")
    api = prof["hal"] if hal else prof["ll"]
    m = re.search(r"\(([A-Z][A-Z0-9]*)\)\s*$", prof["name"])
    out = {"instance": m.group(1) if m else None, "base_address": prof["base_address"].upper().replace("0X", "0x"),
           "mm_page": prof.get("mm_page"), "register_prefix": prof["register_prefix"],
           "function_prefix": api["function_prefix"], "header": api["header"],
           "files": sorted((f["from"], f["to"]) for f in d["files"]),
           "dependencies": sorted((x["from"], x["to"]) for x in d.get("dependencies") or [])}
    if hal:
        out["source"] = prof["hal"].get("source")
        out["time_base"] = prof["hal"].get("time_base") or "NONE"
        out["host_instance"] = prof["hal"].get("host_instance") or "NONE"
        cs = prof["hal"].get("clock_stub")
        out["value_externals"] = [cs["prototype"].split("(")[0].split()[-1]] if cs else []
        out["framework_modules"] = next((x["configure"]["hal_modules"] for x in d.get("dependencies") or []
                                         if x.get("configure")), [])
    return out


def derived_values(pkg: dict) -> dict:
    from .facts import value

    hd = value(pkg, "headers") or {}
    fm = value(pkg, "file_map") or {}
    out = {"instance": value(pkg, "instance"), "base_address": value(pkg, "base_address"),
           "mm_page": value(pkg, "mm_page"), "register_prefix": value(pkg, "register_prefix"),
           "function_prefix": value(pkg, "function_prefix"), "header": hd.get("header"),
           "files": sorted((f["from"], f["to"]) for f in fm.get("files") or []),
           "dependencies": sorted((x["from"], x["to"]) for x in fm.get("dependencies") or [])}
    if pkg["driver_style"].startswith("HAL"):
        out["source"] = hd.get("source")
        out["time_base"] = value(pkg, "time_base")
        out["host_instance"] = value(pkg, "host_instance")
        out["value_externals"] = [e["symbol"] for e in value(pkg, "undelivered_externals") or [] if e["role"] == "value"]
        out["framework_modules"] = value(pkg, "framework_modules")
    return out


def compare(example, wo: str = "WO-ORACLE") -> list[dict]:
    """Differences between the hand values and a fresh derivation; an `instance` exception supplies the owner's
    instance (the hand profile chose it) so the remaining facts are still compared."""
    import json
    import shutil
    import tempfile
    from pathlib import Path

    from . import derive

    name = Path(example).name
    exc = exceptions()
    src = Path(example)
    with tempfile.TemporaryDirectory(prefix="forge-ob-oracle-") as td:
        if (name, "instance") in exc:
            ex = Path(td) / name
            shutil.copytree(src, ex, symlinks=True)
            spec = json.loads((ex / "workorder.json").read_text())
            spec.setdefault("target", {})["instance"] = exc[(name, "instance")]["hand_value"]
            (ex / "workorder.json").write_text(json.dumps(spec))
            for item in spec.get("inputs") or []:          # relative inputs keep resolving from the original place
                if not (ex / item["path"]).exists():
                    (ex / item["path"]).parent.mkdir(parents=True, exist_ok=True)
                    (ex / item["path"]).symlink_to((src / item["path"]).resolve())
            src = ex
        pkg = derive(src, wo)
    hand, got = hand_values(example), derived_values(pkg)
    diffs = []
    for k in hand:
        if k == "dependencies":
            h, g = set(hand[k]), set(got.get(k) or [])
            if h != g:
                diffs.append({"fact": k, "hand_value": sorted(h - g), "derived_value": sorted(g - h)})
        elif hand[k] != got.get(k):
            diffs.append({"fact": k, "hand_value": hand[k], "derived_value": got.get(k)})
    return diffs
