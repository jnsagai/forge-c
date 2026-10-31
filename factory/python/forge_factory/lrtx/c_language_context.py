"""Optional C notation context, shared by native and structured local roles.

This clarifies parameter syntax only. It cannot assign a return type, change
work-order scope, refute an inspection automatically, or waive a gate.
"""
from __future__ import annotations

import json
from pathlib import Path

NOTE = (
    "C declaration notation: in a declaration such as uint32_t query(void), "
    "(void) is the parameter list and means no arguments; the return type is uint32_t. "
    "A void return type is written before the function name, as in void update(void). "
    "The scope shorthand '(void) functions' alone does not establish void return types. "
    "Determine return contracts from explicit requirements or baselined declarations; "
    "record unresolved ambiguity instead of inventing a signature or inferring a type conflict "
    "solely from that shorthand."
)


def selected(profile):
    value = (profile.get("structured") or {}).get("c_parameter_list_note", False)
    if type(value) is not bool:
        raise ValueError("C_PARAMETER_LIST_NOTE_POLICY_INVALID")
    return value


def for_workspace(workspace):
    from .profile import load

    manifest = json.loads((Path(workspace) / ".forge-run/manifest.json").read_text())
    identity = (manifest.get("local_profile") or {}).get("id")
    return NOTE if identity and selected(load(identity)) else ""

