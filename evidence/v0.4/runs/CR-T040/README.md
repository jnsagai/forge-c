# CR-T040: layout check (SC-008)

Recorded 2026-10-19.

`layout_check.py` drives headless Firefox through geckodriver's WebDriver HTTP API, against port 8766 serving
the real state directory.

- **1440 px window:** scrollWidth 1428 = clientWidth 1428. No horizontal scroll and no overflowing element.
  7 stations.
- **390 px:** a Firefox window cannot be narrower than about 490 px, so the page is measured inside a
  same-origin iframe exactly 390 px wide. scrollWidth 378 = clientWidth 378 (inside the scrollbar). No horizontal
  scroll and no overflowing element; the station board collapses to one column.
- Every andon shows a text label ("– IDLE", "▶ RUNNING", "↻ REWORK", "■ STOPPED"), not colour alone.

Result: PASS. Raw measurements are in `layout-check.json`; `layout-1440.png` is the screenshot.
