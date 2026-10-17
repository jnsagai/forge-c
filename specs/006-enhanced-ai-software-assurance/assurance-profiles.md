# Assurance Profiles: minimum vs enhanced assurance, never elevated product ASIL

| Dimension | STANDARD | ENHANCED | HIGH_ASSURANCE |
|---|---|---|---|
| ASIL allocation | Unchanged from approved safety scope | Unchanged | Unchanged |
| Normative methods | Controlled catalog, applicability rationale | All applicable STANDARD methods plus justified supplemental verification | Same, with deeper formal and target-sensitive checks where feasible |
| SWE.1/2 | Source-linked requirements/architecture and existing independent inspector | Semantic source contradiction and flow/scheduling checks | Formalized constraints and adversarial review on risky interfaces |
| SWE.3 | Baseline style/static/compilation/hardware checks | Semantics of register operations, MISRA coverage, concurrency, resource boundaries | Selected bounded proofs, formal contracts and stronger timing/resource assumptions |
| SWE.4 | Requirements derived unit tests and statement/branch coverage | Independently derived oracles, mutations, negative cases, selected MC/DC | More comprehensive mutation and formally proved properties where suitable |
| SWE.5 | Executed integration and model fidelity evidence | Fault injection, boundary, concurrency and resource limits | More diverse target/real-hardware campaigns as available |
| SWE.6 | Actual requirements-based embedded software tests | Degraded/operational transitions and measured requirements observation | Stronger target representativeness and independent scenario/test oracle selection |
| CAE | Minimum evidence-linked claims and known gaps | Richer counterevidence, confidence and independence | Strong claims with qualified external reviewer as appropriate |
| Gate | Existing mandatory baseline unchanged | Selected extra methods HARD only once calibrated and approved | Additional scoped methods HARD subject to feasibility/approved risk policy |

**Never set an arbitrary global default of 100% coverage, 100% mutation score, or all formal proofs.** Configure objective/scope/toolchain constraints, treatment of equivalent mutants and justified coverage gaps. Selection of a higher profile cannot become a shortcut for omitting a required lower-profile method.

Safety-related scope is determined by approved upstream safety workproducts. If those are missing, do not imply ASIL B evidence from a HIGH_ASSURANCE badge. Standard selection also does not imply existing tool qualification. A signed process qualification and human safety acceptance are outside feature 006.
