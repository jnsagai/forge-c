"""Feature 016: peripheral onboarding as a factory stage before SWE.1.

    python -m forge_factory.onboarding derive <example> <WO> [--no-author]   # deterministic facts -> package
    python -m forge_factory.onboarding summary <WO>                          # owner review page
    python -m forge_factory.onboarding verify <WO>                           # owner-signed approval check
    python -m forge_factory.onboarding prompts <WO> --check                  # generated instructions + leftovers
    python -m forge_factory.onboarding check-model <peripheral>              # simulation model gate

The derivation makes no model call (FR-022); unknowns are NOT_DERIVED, disagreements CONFLICT (FR-005)."""
