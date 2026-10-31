# Retain the source of a shutdown-order projection

Exact tested implementation: `a4bc71d186806afe45492d8c38cdd3a10e3bed7c`.
This follows [the stopped-order fix](../shutdown-order-projection-c0777ead/README.md).

An independent review of that change found that its event retained a digest
of the execution lifecycle row, while later native reconciliation could advance
that mutable row. The event now retains the complete lifecycle snapshot alongside
its canonical hash in the existing durable queue event. No new store or authority.

Two real-SQLite/native-protocol regression cases fail before for the absent
snapshot. After live and terminal fixture settlement, repeated reconciliation
must leave the original event reproducibly hash-bound. These are deterministic
fixtures, not a Qwen self-healing or native runtime qualification.

The exact source reruns the same nine-file lifecycle cohort: 152 cases, no
failures/errors/skips (see raw JUnit for measured duration). Ruff and 14 static
design checks PASS. Test counts overlap the earlier cohort. No original DA task
is newly closed. Historical c0777ead receipts retain their original test version.

No deployment, model execution, deadline extension or grant signing occurs.
The stopped-job learning disposition and full LL/HAL pipeline remain open.
All native Qwen/generated-C work must remain on Omniverse under valid scope;
the earlier eight configured grants expired at 07:57:59 UTC.
