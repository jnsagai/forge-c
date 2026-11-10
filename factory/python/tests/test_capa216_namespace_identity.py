"""CAPA-216 (owner 2026-11-10, exception for the pinned lrtx/stack.py granted): TIM LL L43L's stack start recorded Fabro's
identity right after spawning it through nsenter, before nsenter had entered the stack network namespace, so the record
named the host netns. The start then failed (database locked); its cleanup compared the record with the live Fabro,
refused LOCAL_PROCESS_OWNERSHIP_UNPROVEN, left Fabro and the namespace holder running and the launch lease HELD. A spawned
stack process's identity is now recorded once it has left the caller's network namespace (bounded wait)."""
from __future__ import annotations

import inspect

from forge_factory.lrtx import stack as ST

HOST, STACK = "net:[4026531840]", "net:[4026533514]"


def _ident(netns):
    return {"boot_id": "b", "start_ticks": "1", "netns": netns, "uid": 1000}


def test_the_identity_waits_until_the_process_is_in_the_stack_namespace(monkeypatch):
    seen = iter([_ident(HOST), _ident(HOST), _ident(STACK)])
    monkeypatch.setattr(ST, "process_identity", lambda pid: next(seen))
    monkeypatch.setattr(ST.os, "readlink", lambda p: HOST if "self" in p else STACK)
    assert ST._ns_identity(42, 7)["netns"] == STACK


def test_a_process_already_in_the_namespace_is_recorded_at_once(monkeypatch):
    monkeypatch.setattr(ST, "process_identity", lambda pid: _ident(STACK))
    monkeypatch.setattr(ST.os, "readlink", lambda p: HOST if "self" in p else STACK)
    assert ST._ns_identity(42, 7)["netns"] == STACK


def test_the_wait_is_bounded(monkeypatch):
    monkeypatch.setattr(ST, "process_identity", lambda pid: _ident(HOST))
    monkeypatch.setattr(ST.os, "readlink", lambda p: HOST if "self" in p else STACK)
    assert ST._ns_identity(42, 7, timeout=0.05)["netns"] == HOST  # unchanged result; the stop still refuses it


def test_the_start_records_spawned_identities_through_the_namespace_wait():
    src = inspect.getsource(ST._start)
    assert "_ns_identity(proc.pid, holder)" in src and "process_identity(proc.pid)" not in src
