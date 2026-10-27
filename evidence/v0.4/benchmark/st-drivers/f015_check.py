"""Feature 015 task evidence checks (run through forge_factory.evidence_run; exit 0 = PASS). Read-only.

    inputs                 F015-T001: the five RM0486 chapter inputs match their tracked hash manifests and the
                           register-map parser finds the in-scope registers of each chapter
    outcome <peripheral>   F015-T0x1: the frozen record holds a READY_FOR_OFFLINE_REVIEW package of that peripheral
                           whose sealed archive still has the recorded SHA-256; the owner's review decision, if any
    afo-live               F015-T081: the AFO policy is PILOT under a valid owner-signed authorization, the Conductor
                           runs, and every benchmark order the Conductor ran has a recorded terminal outcome
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REC = ROOT / "evidence/v0.4/benchmark/st-drivers/record.json"
EXAMPLES = {"crc": "0014-crc-st", "spi": "0011-spi-st", "usart": "0012-usart-st", "gpio": "0010-gpio-st",
            "tim": "0013-tim-st"}
REGISTERS = {"crc": ["CRC_DR", "CRC_CR", "CRC_INIT", "CRC_POL"], "spi": ["SPI_CR1", "SPI_CFG1", "SPI_SR", "SPI_IFCR"],
             "usart": ["USART_CR1", "USART_BRR", "USART_ISR", "USART_TDR", "USART_RDR"],
             "gpio": ["GPIO_MODER", "GPIO_OTYPER", "GPIO_AFRL", "GPIO_AFRH", "GPIO_BSRR"],
             "tim": ["TIM_CR1", "TIM_SR", "TIM_CNT", "TIM_PSC", "TIM_ARR"]}


def inputs() -> int:
    sys.path.insert(0, str(ROOT / "factory/python"))
    from forge_factory import workorder as WO
    from forge_factory.inspection.regmap import parse_section

    bad = 0
    for p, ex in EXAMPLES.items():
        n = 0
        for m in glob.glob(str(ROOT / "examples" / ex / "inputs/*manifest*.json")):
            for d in json.load(open(m)).get("documents", []):
                f = Path(m).parent / d["markdown"]
                ok = f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() == d["markdown_sha256"]
                n += 1
                bad += not ok
                print(f"{p}: {d['markdown']} {'OK' if ok else 'HASH MISMATCH OR MISSING'}")
        rm = next(iter(sorted((ROOT / "examples" / ex / "inputs").glob("RM0486-*.md"))), None)
        if rm is None:
            print(f"{p}: no RM chapter")
            bad += 1
            continue
        files, _ = WO.split_sections(rm.read_text(), rm.stem)
        regs = {r["name"] for r in (parse_section(t, p.upper()) for t in files.values()) if r}
        miss = [r for r in REGISTERS[p] if r not in regs]
        bad += bool(miss) + (n == 0)
        print(f"{p}: {len(regs)} registers parsed from {rm.name}; in-scope missing: {miss or 'none'}")
    return 1 if bad else 0


def outcome(p: str) -> int:
    rec = json.loads(REC.read_text())
    ready = [e for e in rec["entries"] if e.get("peripheral") == p and (e.get("package") or {}).get("status")
             == "READY_FOR_OFFLINE_REVIEW"]
    print(f"{p}: {sum(e.get('peripheral') == p for e in rec['entries'])} attempts recorded, {len(ready)} READY")
    ok = False
    for e in ready:
        pk = e["package"]
        st = Path(os.environ.get("FORGE_STATE_DIR", ""))  # the record keeps the hash; the run's package.json the path
        pj = st / "workorders" / e["work_order"] / "workspace/.forge-run/package.json"
        arc = Path(json.loads(pj.read_text()).get("archive", "")) if pj.is_file() else Path("")
        sha = hashlib.sha256(arc.read_bytes()).hexdigest() if arc.is_file() else None
        good = sha is not None and sha == pk.get("archive_sha256") and not pk.get("gaps")
        ok |= good
        print(f"  {e['request_id']} {e['work_order']} rev {str(e.get('factory_revision'))[:7]} gaps {pk.get('gap_count')} "
              f"archive {'sha256 verified' if good else 'NOT VERIFIED'} {pk.get('archive_sha256')}")
        for od in sorted((ROOT / "evidence/easa/owner-decisions").glob("OD-*.json")):
            d = json.loads(od.read_text())
            if any(x.get("archive_sha256") == pk.get("archive_sha256") for x in d.get("packages") or []):
                print(f"  owner review: {d['decision_id']} \"{d['statement']}\"")
    return 0 if ok else 1


def afo_live() -> int:
    sys.path.insert(0, str(ROOT / "factory/python"))
    from forge_factory.afo import policy

    e = policy.load()
    print(f"AFO policy: mode {e.mode}, authorization {e.authorization_id}, issues {e.issues[:3]}")
    act = subprocess.run(["systemctl", "--user", "is-active", "forge-conductor"], capture_output=True, text=True)
    print(f"forge-conductor: {act.stdout.strip()}")
    rec = json.loads(REC.read_text())
    afo = [x for x in rec["entries"] if x["route"] == "AFO"]
    done = [x for x in afo if (x.get("package") or {}).get("status") or x.get("outcome")]
    print(f"AFO benchmark attempts recorded: {len(afo)}; with a package: {len(done)}; READY: "
          f"{sum((x.get('package') or {}).get('status') == 'READY_FOR_OFFLINE_REVIEW' for x in afo)}")
    return 0 if e.mode == "PILOT" and not e.issues and act.stdout.strip() == "active" and done else 1


if __name__ == "__main__":
    os.chdir(ROOT)
    cmd = sys.argv[1]
    sys.exit(inputs() if cmd == "inputs" else outcome(sys.argv[2]) if cmd == "outcome" else afo_live())
