# Staged native qualification (not executed)

Exact candidate9f9a93f174f46aa0add59c16a423be7d56988614 is staged on Omniverse2:

```text
/mnt/data/forge-c/production-local-014/deployment/qualification-mcp-root-9f9a93f/
  source.bundle
  bootstrap-v2.py
  render-real-unit-cases-v2.py
  real-unit-cases/SWU-LL-01.puml
  real-unit-cases/SWU-LL-02.puml
  staging-v2.json
```

**NOT_RUN.** Source bundle verified; no pytest, renderer, model request, service
restart, deployment, job dispatch or grant mutation was executed during staging.
staging-v2.json records exact byte hashes; the script snapshots here preserve
those exact bytes, including their trailing newline layout.

After the current production run is authoritatively quiescent and every provider
request/lease/verification job released, run once through the existing SSH control:

```sh
/mnt/data/forge-c/production-local-014/venv/bin/python \
 /mnt/data/forge-c/production-local-014/deployment/qualification-mcp-root-9f9a93f/bootstrap-v2.py
```

It requires unchanged RUNNING operator intent at epoch32 and refuses while native
execution, nonquiescent requests or resources remain. It clones/fetches the exact
source into its isolated qualification checkout, prepares private input copies,
runs the same13-test cohort, then renders the two actual failed unit diagrams
using the candidate's generated MCP environment. The renderer verifies each input
hash against the **frozen failed SWE.3 baseline97f4c1...**, not an earlier draft.
A finite guard terminates only its own qualification process group on new operator
intent/execution or timeout. It never activates source, starts a model, submits
an order, releases production inference or changes a production authority.

The first staging attempt correctly rejected pre-freeze diagram hashes before
executing any test. Initial files are retained; bootstrap.py and
render-real-unit-cases.py are superseded. Use **only the v2 entrypoint**.
initial-staging-refusal.json and staging-v2.json preserve both states.
This is a preparation result, not native qualification, rendered-diagram success,
model capability or product acceptance. Inspect actual pytest/provenance/render
outputs after execution before a separately signed/fenced continuation.
