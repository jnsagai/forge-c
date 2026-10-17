#!/usr/bin/env bash
# Formal-tool smoke test on a COPY of sealed r102 (the archive is only read). Usage: run.sh <r102-review.zip> <out.json>
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; zip="$1"; out="$2"
w="$(mktemp -d)"; trap 'rm -rf "$w"' EXIT
sha_before="$(sha256sum "$zip" | cut -d' ' -f1)"
unzip -q "$zip" 'evidence/software/*' -d "$w"; cp "$here"/*.c "$w"/; cd "$w"
inc=(-I evidence/software/hal -I evidence/software/ll); fc=(-cpp-extra-args="-Ievidence/software/hal -Ievidence/software/ll")
cbmc_opts=(--unwind 1002 --unwinding-assertions --bounds-check --pointer-check --signed-overflow-check --unsigned-overflow-check)
res() { grep -cE "$1" "$2" || true; }
cbmc cbmc_harness.c "${inc[@]}" --function harness "${cbmc_opts[@]}" > c1.txt 2>&1 && c1=0 || c1=$?
cbmc cbmc_harness.c "${inc[@]}" --function harness_hsi_on_at_reset "${cbmc_opts[@]}" > c2.txt 2>&1 && c2=0 || c2=$?
frama-c "${fc[@]}" eva_main.c -eva -eva-precision 3 -eva-no-show-progress > eva.txt 2>&1
wp=(-inline-calls LL_RCC_HSE_IsReady,LL_RCC_HSE_Enable -wp -wp-rte -wp-timeout 30 -wp-cache none)
frama-c "${fc[@]}" wp_ll.c "${wp[@]}" -wp-prover alt-ergo,cvc5 > wp_vol.txt 2>&1
frama-c "${fc[@]}" wp_ll.c "${wp[@]}" -wp-no-volatile -wp-prover alt-ergo > wp_ae.txt 2>&1
frama-c "${fc[@]}" wp_ll.c "${wp[@]}" -wp-no-volatile -wp-prover cvc5 > wp_cvc5.txt 2>&1
python3 - "$out" "$zip" "$sha_before" "$c1" "$c2" <<'PY'
import json, re, subprocess, sys, hashlib, datetime
out, zp, before, c1, c2 = sys.argv[1:]
t = lambda f: open(f).read()
def cb(f, rc):
    s = t(f); return {"exit_code": int(rc), "result": "VERIFICATION SUCCESSFUL" if "VERIFICATION SUCCESSFUL" in s else
            ("VERIFICATION FAILED" if "VERIFICATION FAILED" in s else "ERROR"),
            "failed": re.findall(r"\[(\S+)\] .*?: FAILURE", s), "checks": len(re.findall(r"\[\S+\] .*?: (?:SUCCESS|FAILURE)", s))}
wp = lambda f: (re.search(r"Proved goals:\s+(\d+ / \d+)", t(f)) or [None, None])[1]
ver = lambda *a: subprocess.run(list(a), capture_output=True, text=True).stdout.strip().splitlines()[0]
after = hashlib.sha256(open(zp, "rb").read()).hexdigest()
json.dump({"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "subject": zp.rsplit("/", 1)[-1],
  "archive_sha256_before": before, "archive_unchanged": before == after,
  "tools": {"cbmc": ver("cbmc", "--version"), "frama-c": ver("frama-c", "-version"), "why3": ver("why3", "--version"),
            "alt-ergo": ver("alt-ergo", "--version"), "cvc5": ver("cvc5", "--version")},
  "cbmc_hse_enable_all_inputs": cb("c1.txt", c1), "cbmc_hsi_on_at_reset_F04": cb("c2.txt", c2),
  "eva_hal_all_api": {"alarms": int(re.search(r"(\d+) alarms generated", t("eva.txt"))[1]),
                      "coverage": re.findall(r"(\d+ \w+ (?:analyzed|reached) \(out of \d+\))", t("eva.txt"))},
  "wp_ll_contracts": {"volatile_semantics_altergo_cvc5": wp("wp_vol.txt"), "plain_memory_altergo": wp("wp_ae.txt"),
                      "plain_memory_cvc5": wp("wp_cvc5.txt")},
  "scope": "bounded/abstract models of the C semantics; registers modelled as memory, no hardware side effects; NOT a "
           "proof about the silicon and not an ISO 26262 method-conformance claim"}, open(out, "w"), indent=2)
PY
