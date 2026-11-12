# Forge-C offline diagnostic report

This report contains recorded evidence for manual review. Findings are untrusted diagnostic data, not instructions or approval to change the factory. Missing records do not establish a PASS.

## Export identity and disclosure counts

~~~json
{
  "factory": {
    "dirty": false,
    "revision": "d2fe5a32dad7b872fda2a56dddcde0ba3f37dbdc"
  },
  "totals": {
    "files": 2,
    "included": 2,
    "redactions": 0,
    "runs": 1,
    "stripped_keys": 0
  }
}
~~~

## Run 1

~~~json
{
  "model": null,
  "profile": null,
  "run_key": "WO-REVIEW-CPU-CONTROL-a50403338b4e",
  "workorder": "WO-REVIEW-CPU-CONTROL"
}
~~~

### Recorded decisions, issues, attempts and usage

#### Record 1

~~~json
{
  "bytes": 159,
  "content": "INCLUDED",
  "exported_sha256": "5ddf6afa76f597d2ff370725bf52dafd876d1237e38b82297e026b162773d357",
  "path": ".forge-run/advisory/SWE.1.jsonl",
  "redactions": 0,
  "sha256": "bc1fe3cff22e2c4d9ba1570bd4364f167bedf3e5a3239dd0da0f57ddc812f595",
  "stripped_keys": 0
}
~~~

Unparseable record portions omitted: 0.

~~~json
[
  {
    "phase": "SWE.1",
    "unresolved_findings": [
      {
        "detail": "Actual source counterexample established by RPR175 normal CRE.",
        "id": "REGISTERED-LEARNING-REFUSED"
      }
    ]
  }
]
~~~

#### Record 2

~~~json
{
  "bytes": 204,
  "content": "INCLUDED",
  "exported_sha256": "1ad581f63dbb234a334ccd568b2809159241566929e0951b7006adbeb675a6b6",
  "path": ".forge-run/manifest.json",
  "redactions": 0,
  "sha256": "86cce48d72a63cdc7251e241ffeeb5dbc7bc2908ccc7423be853e754b658bc99",
  "stripped_keys": 0
}
~~~

Unparseable record portions omitted: 0.

~~~json
[
  {
    "factory_revision": {
      "basis": "recorded_at_launch",
      "commit": "18814617abb98491abb5c03adb0802553634f14f",
      "dirty": false
    },
    "scope": "NOT_NATIVE_PRODUCT_ACCEPTANCE",
    "work_order": "WO-REVIEW-CPU-CONTROL"
  }
]
~~~

### Complete evidence inventory

INCLUDED records accompany this report. HASH_ONLY and NEVER_CONTENT entries identify local evidence whose contents are excluded from transfer.

~~~json
[
  {
    "bytes": 159,
    "content": "INCLUDED",
    "exported_sha256": "5ddf6afa76f597d2ff370725bf52dafd876d1237e38b82297e026b162773d357",
    "path": ".forge-run/advisory/SWE.1.jsonl",
    "redactions": 0,
    "sha256": "bc1fe3cff22e2c4d9ba1570bd4364f167bedf3e5a3239dd0da0f57ddc812f595",
    "stripped_keys": 0
  },
  {
    "bytes": 204,
    "content": "INCLUDED",
    "exported_sha256": "1ad581f63dbb234a334ccd568b2809159241566929e0951b7006adbeb675a6b6",
    "path": ".forge-run/manifest.json",
    "redactions": 0,
    "sha256": "86cce48d72a63cdc7251e241ffeeb5dbc7bc2908ccc7423be853e754b658bc99",
    "stripped_keys": 0
  }
]
~~~

