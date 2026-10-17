"""EASA-T018 and AT-018/AT-076 — trust-domain independence attestation (EASA-FR-013/015).

Different role names are not enough. The attestation compares the actual identities used by the author, the
inspector and the verifier (agent id, model, provider, prompt/skill digest) and the provenance of the oracles:
  * same agent identity or same role for author and verifier/inspector  -> INDEPENDENCE_VIOLATION (NOT_INDEPENDENT)
  * same prompt or skill digest                                           -> SAME_PROMPT_CONTAMINATION (NOT_INDEPENDENT)
  * any oracle CONTAMINATED                                               -> ORACLE_NOT_INDEPENDENT (NOT_INDEPENDENT)
  * same model+provider for author and inspector                          -> COMMON_CAUSE_MODEL (PARTIAL, recorded)
  * an identity field not recorded                                        -> UNKNOWN (never assumed independent)
"""
from __future__ import annotations

from . import contracts

FIELDS = ("agent_id", "role", "model", "provider")


def attest(work_order_id: str, author: dict, inspector: dict, verifier: dict, oracles: list[dict]) -> dict:
    hard, common, unknown = [], [], []
    for name, other in (("inspector", inspector), ("verifier", verifier)):
        if author.get("agent_id") and author.get("agent_id") == other.get("agent_id"):
            hard.append(f"INDEPENDENCE_VIOLATION:author=={name} identity {author['agent_id']}")
        if author.get("role") == other.get("role"):
            hard.append(f"INDEPENDENCE_VIOLATION:author role == {name} role")
        for d in ("prompt_digest", "skill_digest"):
            if author.get(d) and author.get(d) == other.get(d):
                hard.append(f"SAME_PROMPT_CONTAMINATION:{d} shared with {name}")
    if verifier.get("kind") != "deterministic" and verifier.get("model") and verifier.get("model") == author.get("model"):
        common.append("COMMON_CAUSE_MODEL:verifier uses the author's model")
    if inspector.get("model") and inspector.get("model") == author.get("model") and \
            inspector.get("provider") == author.get("provider"):
        common.append(f"COMMON_CAUSE_MODEL:{author['model']}@{author.get('provider')}")
    for f in ("model", "provider"):
        if not author.get(f) or (inspector and not inspector.get(f)):
            unknown.append(f"IDENTITY_NOT_RECORDED:{f}")
    for o in oracles:
        if o.get("independence_status") != "INDEPENDENT":
            hard.append(f"ORACLE_NOT_INDEPENDENT:{o.get('oracle_id')}:{o.get('independence_status')}")
    decision = "NOT_INDEPENDENT" if hard else ("UNKNOWN" if unknown else ("PARTIAL" if common else "SUPPORTED"))
    rec = {"work_order_id": work_order_id, "author_role": author.get("role", ""), "inspector_role": inspector.get("role", ""),
           "verifier_role": verifier.get("role", ""),
           "oracle_origin_refs": [o.get("oracle_id", "") for o in oracles],
           "shared_common_cause_refs": hard + common + unknown, "independent": decision == "SUPPORTED",
           "decision": decision}
    rec["schema_issues"] = contracts.errors("independence-attestation", {k: v for k, v in rec.items()
                                                                        if k != "schema_issues"})
    return rec
