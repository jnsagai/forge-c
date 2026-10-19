"""EASA-T021/T060 and AT-077/AT-026 — change impact: when an artifact digest changes, every dependent verification,
inspection and claim becomes REVALIDATION_REQUIRED. Nothing is overwritten: the invalidation is a new record and
the first-pass outcome stays readable in the store."""
from __future__ import annotations

from collections import defaultdict


class ImpactGraph:
    def __init__(self):
        self.digest: dict[str, str] = {}
        self.dependents: dict[str, set[str]] = defaultdict(set)
        self.bound: dict[str, dict[str, str]] = {}  # node -> {dependency: digest seen when it was verified}

    def add(self, node: str, digest: str, depends_on: list[str] | None = None) -> None:
        self.digest[node] = digest
        self.bound[node] = {d: self.digest[d] for d in depends_on or []}
        for d in depends_on or []:
            if d not in self.digest:
                raise KeyError(f"unknown dependency {d}")
            self.dependents[d].add(node)

    def affected(self, changed: list[str]) -> list[str]:
        out, todo = [], list(changed)
        seen = set(changed)
        while todo:
            n = todo.pop()
            for dep in sorted(self.dependents.get(n, ())):
                if dep not in seen:
                    seen.add(dep)
                    out.append(dep)
                    todo.append(dep)
        return sorted(out)

    def stale(self) -> list[str]:
        """Nodes whose recorded dependency digest no longer matches (detects changes nobody announced)."""
        return sorted(n for n, b in self.bound.items() if any(self.digest.get(d) != h for d, h in b.items()))

    def change(self, node: str, new_digest: str, store=None, actor: str = "easa-impact") -> list[str]:
        if self.digest.get(node) == new_digest:
            return []
        self.digest[node] = new_digest
        hit = self.affected([node])
        if store is not None:
            for h in hit:
                store.append("impact", h, {"status": "REVALIDATION_REQUIRED", "cause": node, "cause_digest": new_digest},
                             actor=actor)
        return hit
