# Explicit signed prospective mission capacity

Implementation and exact native tested revision:
**b713e354b5c50744c549b1a9cada491c3ca017bd**. Local affected tree identical to the
committed implementation: **199PASS**,0failures/errors/skips,39.285seconds.
Exact Omniverse2 native **51PASS**,0failures/errors/skips,71.521seconds,
clean before/after. Ruff and specification/static design checks PASS separately.
Static checks are not model/runtime or availability qualification.

The operator CLI adds a separately signed append-only capacity amendment to the
existing mission ledger. Original mission row, lineage, original limits, expired
grants/deadlines, all expenditure and uncertainty remain. Current signature binds
the exact complete snapshot, new ceilings and current policy. Ordinary execution
authority and runtime agents cannot increase capacity. Finite monotonic policy-
bounded ceilings; protocol correction ceiling unchanged; max8amendments.
All exhausted non-time allowances and unbounded historical usage refuse amendment.
No order is reopened, inference admitted, deadline changed or old grant renewed.
Intent epoch locking fences concurrent newer pause/stop. Time requires a separate
exact owner-signed time-only decision. Historical receipt replay has no new effects.

The executed tests include real public-key signature validation and modified-payload
rejection; expired time remains blocked after capacity alone; time/capacity in both
orders retain old charges and charge new work; actual exhaustion refuses a new
grant; all six allowance counters, live/prepared work, newer pause/resume, authenticated
CLI, bounded chains and damaged/rehashed history. Synthetic fixture keys are not
owner authority or Qwen capability evidence. No model generation occurred.

Local command: pytest -q -p no:cacheprovider test_mission_capacity.py,
test_mission_deadline.py,test_da014_protocol.py,test_da014_integration.py,
test_da014_launch_boundary.py,test_da014_settled_usage.py,
test_afo_maintenance_rework.py,test_afo_review_disposition.py,
test_da014_high_allowance.py,test_da014_overnight.py,test_afo_local_autonomy.py
under the existing offline test environment. Logs/XML retain actual results.
Native command, environment, source bundle SHA and exact bounds are in provenance
and the executable v2 helper:4CPU affinity20..23,nice5,1.5GiB address space,
240CPU seconds,480wall seconds; no network/GPU/owner identity/SSH agent exposed.

Native v1:48PASS/3FAIL. The sandbox UID2001 had no passwd entry: ssh-keygen and
the operator CLI could not resolve a username. V2 overlays a minimal synthetic
verifier passwd/group read-only inside the same isolated namespace. The real
signature and ownership checks remain; all51then PASS. Initial local fixture
failures omitted execution reservation, then used an invalid nonce; both original
XML files remain. Production logic did not change to suppress these failures.

Actual owner-delegated RCC application is separately recorded in
[aspice-rcc-pair-20261030](../aspice-rcc-pair-20261030/README.md). The original
120000ceiling/86000charged mission was unexhausted; its history was preserved while
the explicit high-allowance request was applied. No new-order budget refill.
Feature014 formal30/58 unchanged; no new task IDs complete.
