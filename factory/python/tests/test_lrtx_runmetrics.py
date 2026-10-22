"""LRTX-T010 (LRTX-FR-007): the per-run measurement record separates queue, load, prefill, decode and tool time,
captures GPU residency and memory pressure from observed samples, and labels what was not observed UNKNOWN."""
import json
from pathlib import Path

from forge_factory.lrtx import runmetrics

RID = "01RUNMETRICSTEST0000000000"


def _stage(at: str, node: str, wall: int, tool: int) -> str:
    return (f'{at}  INFO run{{id={RID}}}: fabro_workflow::event::events: Stage completed node_id="{node}" stage="x" '
            f'index=1 wall_time_ms={wall} active_time_ms={wall} inference_time_ms=0 tool_time_ms={tool} '
            f'status="succeeded" attempt=1 max_attempts=1')


def _setup(tmp_path: Path, samples: list[dict]) -> tuple[Path, Path, Path]:
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/fabro_run_id").write_text(RID)
    storage = tmp_path / "storage"
    log = storage / f"scratch/20261021-{RID}/runtime/server.log"
    log.parent.mkdir(parents=True)
    log.write_text("\n".join([_stage("2026-10-21T10:00:01Z", "start", 100, 0),
                              _stage("2026-10-21T10:10:00Z", "swe1_author", 590000, 589000),
                              _stage("2026-10-21T10:10:01Z", "swe1_route", 300, 200), "unrelated line"]) + "\n")
    calls = [{"ts_utc": "2026-10-21T10:01:00Z", "tokens_input": 4000, "tokens_output": 900, "basis": "reported",
              "local": {"queue_wait_ms": 0.5, "model_loaded_before": False, "load": {"load_ms": 70000},
                        "prefill_ms": 13000, "decode_ms": 45000, "first_delta_ms": 13000,
                        "prefill_tokens_per_s": 300.0, "decode_tokens_per_s": 20.0}},
             {"ts_utc": "2026-10-21T10:05:00Z", "tokens_input": 3000, "tokens_output": 1, "basis": "reported",
              "local": {"queue_wait_ms": 2.5, "model_loaded_before": True, "prefill_ms": "UNKNOWN",
                        "decode_ms": "UNKNOWN (single chunk)", "first_delta_ms": 9000}},
             {"ts_utc": "2026-10-21T11:00:00Z", "tokens_input": 99999, "basis": "reported", "local": {}},  # outside
             {"ts_utc": "2026-10-21T10:06:00Z", "refused": {"reason": "QUEUE_FULL"}}]
    meter = tmp_path / "usage.jsonl"
    rows = calls + [{"ts_utc": f"2026-10-21T10:0{i}:00Z", "sample": s} for i, s in enumerate(samples, start=2)]
    meter.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return ws, storage, meter


def _sample(power: float | None, frac: float, swap: int, avail: int) -> dict:
    return {"gpu": {"power_w": power}, "residency": {"status": "OK", "loaded": [{"name": "m", "vram_fraction": frac}]},
            "host": {"swap_used_mib": swap, "mem_available_mib": avail}}


def test_time_split_residency_memory_pressure_and_energy(tmp_path):
    ws, storage, meter = _setup(tmp_path, [_sample(40.0, 0.34, 100, 12000), _sample(60.0, 0.36, 16383, 11426),
                                           _sample(None, 0.34, 200, 13000)])
    m = runmetrics.collect(ws, storage, meter)
    c = m["calls"]
    assert c["count"] == 2 and c["refused_or_cancelled"] == 1 and c["prompt_tokens"]["sum"] == 7000
    assert (c["queue_wait_ms"]["sum"], c["queue_wait_ms"]["max"]) == (3.0, 2.5)
    assert (c["model_loads"], c["load_ms"]) == (1, 70000)
    assert (c["prefill_ms"], c["decode_ms"], c["first_delta_ms"]) == (13000, 45000, 22000)
    assert c["split_unobservable"] == 1  # a single-chunk answer is not counted as prefill or decode
    assert m["stages"]["tool_ms"] == 589200 and m["stages"]["by_node"]["swe1_author"]["visits"] == 1
    r = m["resources"]
    assert (r["gpu_vram_fraction_min"], r["gpu_vram_fraction_median"]) == (0.34, 0.34)
    assert (r["host_swap_used_mib_max"], r["host_mem_available_mib_min"]) == (16383, 11426)
    e = m["energy"]
    assert e["gpu_board_j"] == 3000.0 and e["coverage"] == round(2 / 3, 3)  # 60 s at a mean of 50 W
    assert e["wall"].startswith("UNKNOWN")


def test_unobserved_quantities_stay_unknown(tmp_path):
    ws, storage, meter = _setup(tmp_path, [_sample(None, 0.34, 0, 1)])
    e = runmetrics.collect(ws, storage, meter)["energy"]
    assert e["gpu_board_j"] == e["gpu_board_wh"] == "UNKNOWN" and e["coverage"] == 0.0
    assert runmetrics.collect(ws, tmp_path / "no-storage", meter)["status"] == "UNKNOWN"
