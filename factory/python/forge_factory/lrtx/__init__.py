"""Feature 010 (ADR-0013): isolated, explicitly selected local RTX profile.

Nothing in this package runs unless a work order selects a local profile (`workorder --profile <id>`); the existing
Codex/Claude ACP line and the legacy default keep their behaviour when no profile is selected.
"""
