# Addendum 2026-11-01: Factory floor view (halls and cells)

**Status:** first increment implemented (mockup approved by the owner).

**Owner input, 2026-11-01:**
- "what I'd like to have is a dashboard that really mimics what is a real factory … groups … for each SWE process. And
  then when we click in this group, we can have all the nodes, and the nodes would be represented with a kind of
  industrial cells, where I can see progress … what is the speed of working … I would like to see myself as a factory
  manager … The details can be logged in the backgrounds".
- "when a cell is working, we have a kind of robot arm that is moving … a green light … When it is stopped, we have
  another kind of animation … progress, speed, maybe gauge".
- On the mockup: "the mockup is great!! lets commit and push it and use it from now on for new runs".

## Scope of the first increment

This view lives next to the Control Room. It does not replace it: the scorecard, Pareto, SPC and K01–K20 views of
feature 007 are unchanged.

*   **Halls:** one per SWE process (SWE.1–SWE.6) plus Shipping. Each hall has an andon state (working / stopped / done /
    idle), its orders now (as crates) and its KPIs: done/entered, first-pass yield, average time to pass, reworks.
*   **Cells:** clicking a hall opens its cells, which are the workflow nodes of a structured phase: tool changer,
    author cell, freeze gate, inspection cell, inspection gate and rework router. Each cell shows:
    *   a state with a stack light and an animated robot arm (working, rework, stopped, waiting, idle);
    *   the job, a segmented progress counter with ETA, speed gauges (output tokens per second, tasks per hour);
    *   the shift's counters.
*   **Shift KPIs:** orders on the floor, completed / total, SWE.1 first-pass yield, rework cycles (failed inspections),
    stopped orders, model work in hours and tokens, and the line speed.
*   **Orders this shift:** each order's route through the halls (carried-over phases marked), its state and a plain
    one-line note.

## Rules (from feature 007, unchanged)

*   Read-only and model-free. The view derives every number from recorded gate decisions, task packets, visit states
    and package records (`forge_factory/lrtx/floor_api.py`, `progress_api.py`). Nothing is guessed.
*   Model reasoning is never read or shown.
*   When the feed is interrupted, the page shows a stale-data banner with the age of the last update.
*   No release claim. Shipping shows offline review candidates only.
*   Animations stop under `prefers-reduced-motion`.

## Delivery

*   **Server:** `python -m forge_factory.lrtx.progress_api --port 32398` serves `/` (the page,
    `forge_factory/dashboard/static/factory-floor.html`), `/floor.json[?since=]` and `/progress`. It binds loopback
    only and runs on the factory machine.
*   **Access:** the loop10 tunnel unit forwards it to the owner's network.

## Acceptance (tests: factory/python/tests/test_factory_floor.py)

1.  Each order gets a state (DONE / RUNNING / STOPPED) and a note from recorded decisions only, and an earlier shift is
    not counted.
2.  Hall and shift KPIs count recorded inspections, failed inspections and stops; idle halls have no cells.
3.  The working cell shows the job, the progress (tasks valid / total) and the speed (output tokens per model second).
4.  The server serves the page and the floor JSON.

## Next increments (not yet implemented)

*   Cell detail for native agent phases (the current node from the Fabro run state).
*   A per-hall throughput trend.
*   Link from the Fabro monitor at :8787.
