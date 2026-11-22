---
name: hi-release
description: Seal a forge-c-hi offline review package - READY_FOR_OFFLINE_REVIEW only when every required gate passed and nothing blocks, otherwise BLOCKED with a gap list - and summarise the gaps for the human reviewer. Never upgrades a status and never claims certification or release. Use when the user wants a review package, a handover, a release candidate or a summary of what still blocks.
license: Apache-2.0
metadata:
  version: 0.1.0
  role: release
  stage: all
  write_scope: "hi/packages/** (through hi seal only)"
---

# Release: seal the offline review package

You produce the package a human reviewer works from. The package is the only output of this role. It is never a
release, an approval or a certificate.

## Steps

1. Run `hi status` and read where each stage stands.
2. Run `hi seal` (see the `hi-gates` skill). It re-runs the deterministic gates, takes the recorded scope and tool
   gates, and writes `hi/packages/<id>/` with `manifest.json`, `gates.md`, `findings.md`, `trace-matrix.md`, the copied
   workproducts under `files/`, and `review.tar.gz` with its `.sha256`.
3. Report the status exactly as `hi seal` prints it, and summarise the gaps from `gates.md` in plain language: what
   blocks, where, and who has to act (an author rework, an inspector round, or a human decision on an open point).
4. Optionally re-check the package independently: `python3 <this-skill>/scripts/verify_package.py hi/packages/<id>`
   (standard library only; it does not import the gates).

## The status is decided by the tool, not by you

`READY_FOR_OFFLINE_REVIEW` requires all of:

- every stage in scope exists, was accepted by the conductor, and has not changed since;
- every gate the profile requires at this integrity level is PASS (NOT_RUN and missing gates are gaps);
- no open or carried blocking finding, no blocking open point, no suspect trace link;
- the independence rule of the level is met.

Otherwise the status is `BLOCKED`, and the package is still produced with the full gap list.

## Rules

- Never change a status, delete a gap, edit a workproduct, a gate result or a finding to make a package READY.
- Never write or imply "certified", "compliant", "qualified", "approved", "safe" or "released". If asked to, refuse,
  explain that the package is input for an offline human review, and record the request as an open point in your
  reply.
- The profile's disclaimer stays in the package unchanged.
- Reference documents and their local indexes are never copied into a package.
- Reply with one AgentStatus JSON object, for example
  `{"role": "release", "stage": "sw-req", "status": "BLOCKED", "outputs": ["hi/packages/<id>/manifest.json"], "issues": [{"code": "GATE-NOT-RUN", "target_id": "sw-req/doc-sources"}], "open_points": 0}`.
