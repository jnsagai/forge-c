from forge_factory.brownfield import resume as R
PINNED_CONTRACT_SOURCE_REVISION='81a2c26329fa392658cd4289665a264ca8e5d576'
namespace=dict(vars(R))
exec('def contract(man: dict) -> dict:\n    return {**{k: man.get(k) for k in CONTRACT_FIELDS},\n            **{k: man[k] for k in ("aspice_development", "historical_safety_scope") if k in man},\n            **({"semantic_required_operations": man["semantic_required_operations"]}\n               if "semantic_required_operations" in man else {}),\n            "inputs": sorted((r["path"], r["role"], r["sha256"]) for r in man.get("inputs", [])),\n            "provided": sorted((r["path"], r["sha256"]) for r in man.get("provided", [])),\n            "delivered": sorted((r["path"], r["role"], r["sha256"]) for r in man.get("delivered", []))}',namespace)
R.contract=namespace['contract']
