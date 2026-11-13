"""Factory-side model-service client (feature 017, FR-002 to FR-007, FR-029; data-model ModelServiceProfile).

Loads and validates the `model_service` profile, reads each model's served identity (attested by the service's
identity extension, or inferred from `/v1/models` and marked unattested), checks before a run that every model the
run needs is offered, and keeps the per-model link state of data-model.md: UNPINNED -> PINNED -> (WAITING | QUEUED)
-> PINNED, or BLOCKED with a reason. It never starts, stops or swaps anything: the service does that.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml
from model_tier import identity as I

from .reasons import Reason

SCHEMA = Path(__file__).resolve().parents[3].parent / "config/schemas/model-service/model-service-profile.schema.json"
UNPINNED, PINNED, WAITING, QUEUED, BLOCKED = "UNPINNED", "PINNED", "WAITING", "QUEUED", "BLOCKED"


class ProfileError(ValueError):
    pass


def load_profile(path_or_doc) -> dict:
    from jsonschema import Draft202012Validator

    doc = path_or_doc if isinstance(path_or_doc, dict) else yaml.safe_load(Path(path_or_doc).read_text())
    errors = list(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(doc))
    if errors:
        raise ProfileError("MODEL_SERVICE_PROFILE_INVALID:" + "; ".join(e.message for e in errors[:3]))
    if doc["mode"] == "external" and doc["share"]["queue_wait_max_s"] < 1:
        raise ProfileError("MODEL_SERVICE_PROFILE_INVALID:queue_wait_max_s")
    return doc


@dataclass
class Link:
    model: str
    state: str = UNPINNED
    identity: dict | None = None
    reason: str | None = None
    since: float = field(default_factory=time.monotonic)


class ModelServiceClient:
    def __init__(self, profile: dict, http: httpx.Client, *, key: Callable[[], str], clock=time.monotonic):
        if profile["mode"] != "external":
            raise ProfileError("NOT_EXTERNAL_MODE")
        self.p, self.http, self.key, self.clock = profile, http, key, clock
        self.links: dict[str, Link] = {m: Link(m) for m in profile["expected_identity"]}

    def _get(self, path: str, **params) -> httpx.Response:
        return self.http.get(self.p["base_url"].rstrip("/") + path, params=params or None,
                             headers={"Authorization": f"Bearer {self.key()}"}, timeout=30)

    def _root(self) -> str:
        return self.p["base_url"].rstrip("/").removesuffix("/v1")

    def read_identity(self, model: str) -> dict:
        """The served identity of `model`: attested when the service offers the Forge-C extension, else inferred."""
        exp = self.p["expected_identity"][model]
        try:
            r = self.http.get(self._root() + "/forge/v1/identity", params={"model": model},
                              headers={"Authorization": f"Bearer {self.key()}"}, timeout=30)
            if r.status_code == 200:
                return I.validate(r.json())
            if r.status_code in (401, 403):
                raise PermissionError(Reason.CREDENTIAL_REFUSED.value)
        except httpx.HTTPError:
            pass
        r = self._get("/models")
        if r.status_code in (401, 403):
            raise PermissionError(Reason.CREDENTIAL_REFUSED.value)
        r.raise_for_status()
        return I.inferred_from_models_endpoint(r.json(), model, exp)

    def check(self, model: str, ident: dict) -> list[str]:
        """Differences between a served identity and what the profile expects (empty = acceptable)."""
        exp, diff = self.p["expected_identity"][model], []
        for k in ("precision", "reasoning_mode"):
            if ident.get(k) != exp[k]:
                diff.append(k)
        if int(ident.get("context_limit") or 0) < exp["min_context_limit"]:
            diff.append("context_limit")
        if exp.get("revision_fingerprint") and ident.get("revision_fingerprint") != exp["revision_fingerprint"]:
            diff.append("revision_fingerprint")
        return diff

    def preflight(self, models: list[str]) -> dict:
        """Before a run: every model it needs must be expected by the profile, offered by the service and match.
        Returns {model: identity}; raises with a machine reason otherwise (FR-003, edge case 'model not offered')."""
        out = {}
        for m in models:
            if m not in self.links:
                raise ProfileError(f"{Reason.MODEL_NOT_OFFERED.value}:{m}:not in the profile's expected_identity")
            try:
                ident = self.read_identity(m)
            except I.IdentityError as exc:
                self.block(m, Reason.MODEL_NOT_OFFERED)
                raise ProfileError(f"{Reason.MODEL_NOT_OFFERED.value}:{m}") from exc
            diff = self.check(m, ident)
            if diff:
                self.block(m, Reason.IDENTITY_CHANGED)
                raise ProfileError(f"{Reason.IDENTITY_CHANGED.value}:{m}:{','.join(diff)}")
            self.pin(m, ident)
            out[m] = ident
        return out

    # ---- link state machine (data-model.md) ------------------------------------------------------------------
    def pin(self, model: str, ident: dict) -> None:
        link = self.links[model]
        if link.state == BLOCKED:
            return
        if link.identity is not None and I.verify(link.identity, ident):
            self.block(model, Reason.IDENTITY_CHANGED)
            return
        link.identity, link.state, link.since = ident, PINNED, self.clock()

    def block(self, model: str, reason: Reason) -> None:
        link = self.links[model]
        link.state, link.reason, link.since = BLOCKED, reason.value, self.clock()

    def outcome(self, model: str, reason: Reason | None) -> str:
        """Fold one call outcome into the link: a bounded wait stays bounded, a refusal of the run blocks."""
        link, now = self.links[model], self.clock()
        if link.state == BLOCKED:
            return BLOCKED
        if reason is None:
            link.state, link.since = PINNED, now
        elif reason == Reason.SHARE_EXHAUSTED:
            if link.state != QUEUED:
                link.state, link.since = QUEUED, now
            elif now - link.since > self.p["share"]["queue_wait_max_s"]:
                self.block(model, reason)
        elif reason in (Reason.SERVICE_UNREACHABLE, Reason.CHANNEL_INTERRUPTED):
            if link.state != WAITING:
                link.state, link.since = WAITING, now
            elif now - link.since > self.p.get("outage_wait_max_s", 900):
                self.block(model, reason)
        elif reason in (Reason.CREDENTIAL_REFUSED, Reason.IDENTITY_CHANGED, Reason.MODEL_NOT_OFFERED):
            self.block(model, reason)
        return link.state

    def evidence(self) -> dict:
        """What the run's evidence records about its model link (FR-007, SC-002)."""
        return {"model_service_mode": "external", "base_url": self.p["base_url"],
                "models": {m: {"state": link.state, "reason": link.reason,
                               "identity": link.identity and {k: link.identity.get(k) for k in (*I.FIELDS, "attested")}}
                           for m, link in self.links.items()}}
