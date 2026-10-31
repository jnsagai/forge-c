"""Bounded field partitioning from explicit joint owner-scope clauses.

No model diagnoses dependencies or changes scope here. Parenthesized clauses
retain the literal REGISTER.FIELD references the owner wrote. Old inventories
without this opt-in metadata keep their original partition.
"""
from __future__ import annotations

import re

FIELD = re.compile(r"\b([A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*)\b")


class CoherentScopeRefused(ValueError):
    pass


def scope_sections(scope, document, baseline):
    """Union catalog seeds with literal, document-bound owner section references.

    No semantic scope inference: only numbered sections following the selected
    manual's name, optional revision/section marker, and explicit ranges/lists.
    Missing sections remain obligations for the caller to report, never dropped.
    """
    number = r"\d+(?:\.\d+){2,}"
    item = rf"{number}(?:\s*[-–]\s*{number})?"
    references = re.compile(
        rf"\b{re.escape(document)}\b[\s,:;]*(?:Rev\.?\s*\d+[\s,:;]*)?"
        rf"(?:sections?\s+|§{{1,2}}\s*)?(?P<items>{item}(?:\s*(?:,|and)\s*{item})*)",
        re.I,
    )
    result = list(dict.fromkeys(baseline))
    if len(result) > 1024:
        raise CoherentScopeRefused("SCOPE_SECTION_INVENTORY_EXCEEDS_BOUND")
    for text in scope:
        if text.lstrip().lower().startswith("out of scope"):
            continue
        for reference in references.finditer(text):
            if re.match(r"\s*[-–]\s*\d", text[reference.end():]):
                raise CoherentScopeRefused("SCOPE_SECTION_RANGE_UNREPRESENTABLE")
            for match in re.finditer(rf"({number})(?:\s*[-–]\s*({number}))?", reference["items"]):
                first = tuple(map(int, match[1].split(".")))
                last = tuple(map(int, (match[2] or match[1]).split(".")))
                if first[:-1] != last[:-1] or not 0 <= last[-1] - first[-1] < 1024:
                    raise CoherentScopeRefused("SCOPE_SECTION_RANGE_UNREPRESENTABLE")
                for value in range(first[-1], last[-1] + 1):
                    section = ".".join(map(str, (*first[:-1], value)))
                    if section not in result:
                        result.append(section)
                    if len(result) > 1024:
                        raise CoherentScopeRefused("SCOPE_SECTION_INVENTORY_EXCEEDS_BOUND")
    return result


def scope_field_sets(scope):
    out = []
    for text in scope:
        if text.lower().startswith("out of scope"):
            continue
        for clause in re.findall(r"\(([^()]*)\)", text):
            fields = list(dict.fromkeys(FIELD.findall(clause)))
            if len(fields) > 1 and fields not in out:
                out.append(fields)
    return out


def partition(register, names, links, maximum):
    """Keep connected fields together, with deterministic, bounded, balanced bins."""
    if not names:
        return []
    parent = {name: name for name in names}

    def root(name):
        while parent[name] != name:
            name = parent[name]
        return name

    linked = False
    for relation in links:
        if not isinstance(relation, list) or any(not isinstance(x, str) or not FIELD.fullmatch(x) for x in relation):
            raise CoherentScopeRefused("COHERENT_SCOPE_DEPENDENCY_INVALID")
        if len({x.split(".", 1)[0] for x in relation}) > 1:
            raise CoherentScopeRefused("COHERENT_SCOPE_CROSS_REGISTER_OBLIGATION_UNSUPPORTED")
        fields = list(dict.fromkeys(x.split(".", 1)[1] for x in relation if x.split(".", 1)[0] == register))
        if any(f not in parent for f in fields):
            raise CoherentScopeRefused("COHERENT_SCOPE_FIELD_NOT_IN_INVENTORY:" + register)
        if len(fields) < 2:
            continue
        linked = True
        for field in fields[1:]:
            parent[root(field)] = root(fields[0])
    if not linked:
        count = -(-len(names) // maximum)
        size = -(-len(names) // count)
        return [names[i:i + size] for i in range(0, len(names), size)]
    components = {}
    for name in names:
        components.setdefault(root(name), []).append(name)
    if any(len(c) > maximum for c in components.values()):
        raise CoherentScopeRefused("COHERENT_SCOPE_GROUP_EXCEEDS_FIELD_LIMIT:" + register)
    order = {name: i for i, name in enumerate(names)}
    bins = [[] for _ in range(-(-len(names) // maximum))]
    for component in sorted(components.values(), key=lambda c: (-len(c), order[c[0]])):
        available = [i for i, part in enumerate(bins) if len(part) + len(component) <= maximum]
        if not available:
            bins.append([])
            available = [len(bins) - 1]
        selected = min(available, key=lambda i: (len(bins[i]), i))
        bins[selected].extend(component)
    return sorted((sorted(b, key=order.get) for b in bins if b), key=lambda b: order[b[0]])
