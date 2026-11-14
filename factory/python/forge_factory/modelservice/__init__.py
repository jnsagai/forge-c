"""Feature 017: model-service split (specs/017-model-service-split/plan.md).

Omniverse2 mirrors the production deployment. One model service owns the GPU and serves a catalog of models,
each at full capacity, swapped on demand and kept warm in host RAM (owner 2026-11-08). The factory is a tenant
that reaches it through one channel and never starts, stops or swaps a model itself.

Hard limits that apply to everything in this package:
* no edit to signed controls, the production lane or its units; the production observer stays OBSERVE;
* the GPU is used only inside a qualification window until the owner approves a cutover (FR-019, FR-020);
* no hidden reasoning and no secret is ever written; prompt capture stays off by default (FR-022 to FR-024);
* no paid or cloud dependency.
"""
