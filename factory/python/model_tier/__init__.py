"""Forge-C model tier (feature 017): a factory-agnostic, multi-tenant model service.

One service owns the GPU and serves a catalog of models at full capacity, swapping them on demand and keeping them
warm in host RAM. It knows tenants (credential, share, allowed models), never factories: no module here may import
forge_factory or name factory concepts (FR-032). Contracts: specs/017-model-service-split/contracts/.
"""
