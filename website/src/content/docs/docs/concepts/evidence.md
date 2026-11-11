---
title: "Evidence and provenance"
description: "The useful output of a factory run is a reviewable relationship between inputs, workproducts, tool results, findings, and the final decision state."
---

The useful output of a factory run is a reviewable relationship between inputs, workproducts, tool results, findings, and the final decision state.

## A traceable run

The factory records input hashes, work-order identity, workproduct baselines, inspections, gate decisions, tool evidence, and packaging results. This makes it possible to distinguish an agent's assertion from an actual check.

## Integrity and meaning

A hash establishes that bytes match the recorded bytes. It does not establish that a requirement is correct, that a model represents the MCU, or that an independent reviewer has accepted the evidence.

Sealed archives include `SHA256SUMS.txt`. Use the archive verifier, then inspect the evidence and assumptions as described in [offline review](/docs/guides/offline-review/).

## Operational evidence

The event stream, incident history, validated lessons, and manufacturing KPIs describe factory operation. KPI values need their numerator, denominator, definition, and event provenance. Missing observations remain unknown or not computable; they are not zero or synthetic success.

## Visibility and retention

Capture policy is separate from a dashboard's display filters. Critical audit events cannot be hidden by disabling capture. Raw model prompts and responses are off by default, and hidden model reasoning is not collected.

The public website publishes documentation and approved source metadata. Runtime databases, credentials, input manuals, private dashboards, and live traces remain with the operator.
