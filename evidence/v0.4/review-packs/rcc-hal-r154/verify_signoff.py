"""Verify a human sign-off record of the review pack: right package hash, every reviewable item marked, verdict set,
signer recorded. Usage: python verify_signoff.py <signoffs.json> <task> -> exit 0 when a valid record exists."""
import json
import sys

PACK_SHA = "877f5c09e7e6be29a0d5cd307517aa45feaa84dc8692f354d130562d7cb95ef2"
EXPECTED_ITEMS = {"T-009": 18, "T-010": 11, "T-018": 7}
doc, task = json.load(open(sys.argv[1])), sys.argv[2]
ok = [r for r in doc["records"] if r["task"] == task and r["archive_sha256"] == PACK_SHA and r.get("signed_by")
      and r.get("verdict") and len(r["items"]) == EXPECTED_ITEMS[task]
      and all(i["mark"] in ("ok", "finding") and (i["mark"] == "ok" or i["note"]) for i in r["items"].values())]
for r in ok:
    print(json.dumps({"task": task, "verdict": r["verdict"], "signed_by": r["signed_by"], "signed_at": r["signed_at"],
                      "findings": sum(i["mark"] == "finding" for i in r["items"].values())}))
sys.exit(0 if ok else 1)
