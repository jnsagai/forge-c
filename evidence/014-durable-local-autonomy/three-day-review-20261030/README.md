# Offline Astra review package — 28–30 October 2026

Start with [the engineering review](../../../specs/014-durable-local-autonomy/ASTRA-REVIEW-20261028-30.md).
It separates runtime implementation, model capability, product delivery, learning
benefit and availability. The date window is three calendar work days, not a
completed72-hour campaign.

- `review-scope.json`: exact reviewed source, complete/open task IDs and scope.
- `commits.tsv`:185history entries in the review window, complete revision IDs.
- `qwen-live-snapshot.json`: read-only live state at18:32–18:33UTC.
- `codex-claude-r4-terminal-snapshot.json`: terminal cloud control result.
- `publication-checks.json`: publication checks and explicit boundaries.
- `SHA256SUMS`: hashes of files in this review evidence directory, excluding itself.

The [shared-fixes evidence](../matched-controls-20261030/) adds exact local/native
test logs, original failures, corrected results, transfer manifests and scoped
activation/reuse records. Its separate SHA256SUMS covers those published files.

```sh
(cd evidence/014-durable-local-autonomy/three-day-review-20261030 && sha256sum -c SHA256SUMS)
(cd evidence/014-durable-local-autonomy/matched-controls-20261030 && sha256sum -c SHA256SUMS)
```

No new live run, deployment, campaign or task completion is claimed by publishing
this package. Full private product archives and private primary inputs are not
bundled into Git; archive identities are retained for separate inspection.
