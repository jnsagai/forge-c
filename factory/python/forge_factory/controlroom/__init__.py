"""Feature 007 - Factory KPI Control Room: the manager's real-time view of the software factory.

Contract (specs/007-kpi-control-room): every value is a deterministic, model-free projection of records the factory
already writes (manifests, gate logs, packages, Fabro run status/usage, ACP proxy usage counts, the feature-003 KPI
engine, the CRE store). Nothing here writes factory state, calls a model, or decides a gate (FR-020, FR-026).
Missing inputs are NOT_MEASURED with a reason, never a default number (FR-007).
"""
