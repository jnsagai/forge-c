"""Feature 005 - Autonomous Factory Operations (AFO): the deterministic Conductor around the existing factory.

AFO owns work-order lifecycle, scheduling, cross-run reconciliation and policy-bound recovery plans. It reuses the
002 supervisor, the 003 KPIs and the 004 CRE (taxonomy, CAPA, side-effect journal, promotion gate) instead of
duplicating them, and never deploys factory code, approves safety or changes another feature's policy.
"""
SPEC_DIR = "specs/005-autonomous-factory-operations"
CONTRACTS = f"{SPEC_DIR}/contracts"
