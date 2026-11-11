---
title: "Contributing"
description: "Forge-C is Apache-2.0 licensed. Contributions should keep the same evidence and authority boundaries as the factory itself."
---

Forge-C is Apache-2.0 licensed. Contributions should keep the same evidence and authority boundaries as the factory itself.

## Prepare the change

Start with the [project constitution](https://github.com/jnsagai/forge-c/blob/main/.specify/memory/constitution.md), the relevant feature under `specs/`, and the current implementation evidence. Keep requirements, source, checks, and documentation aligned.

Keep work scoped. Preserve the host demonstration, existing packager behavior, protected safety policies, and immutable evidence. Changes to safety or release criteria require the project's explicit engineering authorization process.

## Verify the implementation

From a configured factory environment:

```sh
make design-check
make factory-test
make test
```

Run the focused checks for your actual change. Record tool versions, commands, results, and relevant hashes. Do not mark a task passed without executed evidence.

Factory-specific bootstrap and development guidance lives in [CLAUDE.md](https://github.com/jnsagai/forge-c/blob/main/CLAUDE.md) and [PROJECT_HANDOFF_v0.5.md](https://github.com/jnsagai/forge-c/blob/main/PROJECT_HANDOFF_v0.5.md). Those documents contain historical baseline plans; compare them with later evidence before assuming a feature is missing.

## Update the website

The website uses Astro and Starlight, following the X-Verse documentation-site structure. Narrative pages live in `website/src/content/docs/docs/`; the homepage is `website/src/pages/index.astro`.

```sh
npm --prefix website ci
npm --prefix website run test
npm --prefix website run build
npm --prefix website run preview
```

Node 22.23.4 or newer and Python 3.11 or newer are required for the website. Search is available in the built preview. Generated references are replaced on every build; edit their source or generator instead.

See [website/README.md](https://github.com/jnsagai/forge-c/blob/main/website/README.md) for authoring, base paths, checks, and publication.
