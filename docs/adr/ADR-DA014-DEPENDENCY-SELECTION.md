# Select diagnosis work from the validated unresolved dependency graph

Status: implementation decision, subject to independent CRE qualification and native acceptance.

The sealed packet's partitioner respected dependency order, but job preparation and
serialized diagnosis requests selected the first lexical obligation. With
`AAA-DEPENDENT -> ZZZ-PREREQUISITE`, the model received the dependent first.
An old prepared job could also submit that scope directly to the completion broker.

Use one deterministic graph validator for partitioning, preparation, request
serialization and pending proposal admission. Validate every graph component before
choosing a unit; an unrelated ready root cannot hide a missing dependency or cycle.
Choose one dependency-free unresolved unit, deterministically, or honor an explicit
independent root. Refuse empty, unknown, multi-unit or dependency-blocked scopes.
The full requirement/dependency inventory, global constraints and primary evidence
remain available in the existing request contract. The graph traversal is iterative
and visits each node and unique edge once, with sorted frontiers for reproducibility.

The packet inventories unresolved incident units. Topological planning does not
establish completion, and job fields or model assertions cannot satisfy a
prerequisite. Independent re-verification and refreshed sealed evidence must remove
resolved incident dependencies. This decision adds no synthetic completion receipt,
budget, role, tool permission, authority or safety-policy exception. Duplicate
preparation keeps the existing identity, reservation and deadline. Refused graph
selection occurs before mission execution reservation.

CPU controls exercise the actual prepare/request/broker boundaries. Real-native
short-horizon execution, global integration/coverage fault injection and comparison
with the same larger-task baseline remain required by DA-AT-032; these controls alone
do not close DA-T032 or prove model competence.
