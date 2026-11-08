# Forge-C deployment recipe (feature 017)

This recipe builds the two-tier Forge-C deployment, on Omniverse2 (the mirror) and in production, from the same files.

- **Model tier:** one service owns the GPU and serves a catalog of models at full capacity. It swaps them on demand, keeps them warm in host RAM, and puts a tenant gateway in front (keys, shares, identity).
- **Factory machine:** a VM, or a container stand-in, whose only route to a model is the model channel.

| Path | Content |
| --- | --- |
| `params/<site>.yaml` | Every site-specific value, documented with its production counterpart |
| `recipe.lock.json` | Pinned fingerprints of images, model files and tools |
| `model-tier/` | Engine definitions, catalog and tenant gateway |
| `factory-machine/` | Provisioning, cloud-init, container stand-in and VM |

The interface the platform team must provide is `specs/017-model-service-split/contracts/model-channel.md`. Secrets are referenced by name only and never stored here.

The rest of this README (build steps, the parameter mapping and what the Omniverse2 build does not prove) is completed by task T053.
