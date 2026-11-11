# Forge-C public website

Custom Astro landing page, Starlight documentation, and Pagefind search, following the X-Verse documentation-site approach. Static output; no paid service, factory process, or licensed input is needed to build the website. The website shares the repository's Apache-2.0 license. The initial Starlight search component and baseline token styles are adapted from the Apache-2.0 X-Verse website.

## Build and preview

Requires Node **22.23.4+**, npm, and Python **3.11+** (standard library only). From the repository root:

```sh
npm --prefix website ci
npm --prefix website run test
npm --prefix website run build
npm --prefix website run preview
```

Open the preview's printed URL under `/forge-c/`. Search is indexed during `build`, so use the built preview for search QA. `npm --prefix website run dev` regenerates references once before launching Astro; restart it after reference source changes.

## Authoring

- Home: `src/pages/index.astro` and `src/styles/home.css`.
- Narrative guides: `src/content/docs/docs/`.
- Documentation navigation and portable hosting: `astro.config.mjs`.
- Generated commands, contracts, examples, and Python entry points: `scripts/generate.py`.
- Local links, fragments, assets, project-prefix checks, and private path checks: `scripts/check_site.py`.

Generated references and output are ignored. Change the source or generator, not generated Markdown. The generator reads a bounded list of tracked files, extracts CLI signatures using AST, and never imports factory modules or follows work-order input paths. `public/publication-manifest.json` records source revision and SHA-256 hashes. Narrative status is a dated evidence snapshot; update it when new verified campaign evidence changes the public description.

Do not copy MCU reference manuals, licensed standards, credentials, live state, raw model traces, or private host addresses into public content. A zero-gap package still requires independent human review.

## Recorded media and diagrams

The homepage includes an interactive replay and a 45-second silent, captioned MP4 visualization of the **actual IWDG HAL rc4 gate events**, including rework and recorded author-output warnings. It is explicitly labeled as a time-compressed event visualization, not live footage or a screen recording. `public/media/recorded-run.json` selects safe metadata from the public source log and package; it excludes local archive paths and raw issue text. `video-provenance.json` binds the rendered video to that replay by SHA-256. Tests validate those hashes and the six recorded phase gate results.

The Control Room image is an unchanged copy of the public `CR-T044` evidence capture, labeled with its historical date. The architecture image is an authored SVG process map with text alternatives and full-size viewing. None of these assets establishes a new runtime or safety result.

To deliberately update recorded media from its fixed source campaign:

```sh
python3 website/scripts/prepare-media.py
```

After building and serving the site, render the video with an external Playwright installation, an available Chromium executable, and FFmpeg:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright \
BROWSER_EXECUTABLE=/absolute/path/to/chromium \
node website/scripts/render-video.cjs http://127.0.0.1:4321/forge-c/
```

Commit the curated data, video, captions, poster, and provenance together. Video playback is opt-in, and replay animation has explicit play/pause controls and reduced-motion support.

## Publication

`.github/workflows/website.yml` verifies PRs and builds relevant main-branch changes. It checks root and project hosting, then deploys the checked project artifact using the GitHub Actions Pages environment. GitHub Pages must use the **GitHub Actions** build type. No personal token is stored in source.

Default public destination: **https://jnsagai.github.io/forge-c/**.

For root hosting:

```sh
SITE_URL=https://example.org BASE_PATH=/ npm --prefix website run build
```

`SITE_URL` must be an HTTP(S) origin and `BASE_PATH` must have leading and trailing slashes. Change the workflow and Pages domain settings when changing the public destination.

## Verification scope

Website checks cover source extraction boundaries, generated references, internal URLs and fragments, required search assets, responsive navigation, and browser interactions. They do not execute a factory run, start or restart services, run target verification, or establish new driver/safety evidence.

Optional browser QA uses an external Playwright installation and an available Chromium browser:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright \
BROWSER_EXECUTABLE=/absolute/path/to/chromium \
node website/scripts/browser-check.cjs \
  http://127.0.0.1:4321/forge-c/ /tmp/forge-c-website-qa
```
