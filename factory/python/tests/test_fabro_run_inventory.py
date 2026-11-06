"""HTTP enumeration completeness; no model, canonical store or native mutation."""
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from forge_factory.fabro.client import FabroClient, FabroUnavailable
from forge_factory.afo import line_launcher as LL


def run(i, kind="succeeded"):
    return {"id": f"run-{i:05}", "source_directory": "/private/work", "labels": {},
            "lifecycle": {"status": {"kind": kind}}}


class Pages:
    def __init__(self, rows, change=None, total=True):
        self.rows, self.change, self.total, self.calls = rows, change, total, []

    def __call__(self, request):
        q = request.url.params
        self.calls.append(request)
        offset, limit = int(q.get("page[offset]", 0)), int(q.get("page[limit]", 50))
        data = copy.deepcopy(self.rows[offset:offset + limit])
        meta = {"has_more": offset + len(data) < len(self.rows)}
        if self.total:
            meta["total"] = len(self.rows)
        value = {"data": data, "meta": meta}
        if self.change:
            result = self.change(value, len(self.calls), request)
            if isinstance(result, httpx.Response):
                return result
        return httpx.Response(200, json=value)


def client(pages):
    return FabroClient(transport=httpx.MockTransport(pages))


@pytest.mark.parametrize("count", [0, 100, 149, 200])
@pytest.mark.parametrize("total", [True, False])
def test_exact_page_boundary_and_optional_total_are_complete(count, total):
    pages = Pages([run(i) for i in range(count)], total=total)
    with client(pages) as c:
        observation = c.run_inventory()
    assert observation.complete and observation.fresh()
    assert {r["id"] for r in observation.rows} == {f"run-{i:05}" for i in range(count)}
    assert len(pages.calls) == 2 * max(1, (count + 99) // 100)


def test_legacy_list_runs_keeps_single_page_contract():
    pages = Pages([run(i) for i in range(149)])
    with client(pages) as c:
        assert len(c.list_runs(limit=100)) == 100
    assert len(pages.calls) == 1


@pytest.mark.parametrize("fault", ["missing-has-more", "bool-total", "count", "empty-more", "duplicate", "total-change",
                                  "disappear", "identity-change", "http-error", "non-json", "unknown-shape"])
def test_partial_invalid_or_racing_catalog_is_never_empty_success(fault):
    def change(value, call, request):
        if fault == "missing-has-more":
            value["meta"].pop("has_more")
        elif fault == "bool-total":
            value["meta"]["total"] = True
        elif fault == "count":
            value["meta"]["total"] = 150
        elif fault == "empty-more":
            value["data"] = []
        elif fault == "duplicate" and call == 2:
            value["data"][0] = run(0)
        elif fault == "total-change" and call == 2:
            value["meta"]["total"] = 150
        elif fault == "disappear" and call == 4:
            value["data"][-1] = run(999)
        elif fault == "identity-change" and call == 3:
            value["data"][0]["labels"] = {"afo_agent": "foreign"}
        elif fault == "http-error" and call == 2:
            return httpx.Response(503)
        elif fault == "non-json":
            return httpx.Response(200, content=b"not-json")
        elif fault == "unknown-shape":
            value["data"][0]["lifecycle"] = None
    with client(Pages([run(i) for i in range(149)], change)) as c:
        with pytest.raises(FabroUnavailable):
            c.run_inventory()


def test_reordering_between_pages_duplicate_does_not_hide_an_active_run():
    def changed(value, call, request):
        if call == 2:
            value["data"][0] = run(99)
    rows = [run(i) for i in range(149)] + [run(149, "running")]
    with client(Pages(rows, changed)) as c:
        with pytest.raises(FabroUnavailable, match="DUPLICATE"):
            c.run_inventory()


@pytest.mark.parametrize("kwargs", [{"max_pages": 1}, {"max_runs": 100}, {"max_bytes": 1024}])
def test_explicit_scale_bounds_refuse_instead_of_truncating(kwargs):
    with client(Pages([run(i) for i in range(149)])) as c:
        with pytest.raises(FabroUnavailable):
            c.run_inventory(**kwargs)


class Chunks(httpx.SyncByteStream):
    def __init__(self):
        self.produced = 0
        self.closed = False

    def __iter__(self):
        for _ in range(10000):
            self.produced += 1
            yield b"x" * 65536

    def close(self):
        self.closed = True


def test_streaming_byte_bound_closes_before_reading_unbounded_body():
    chunks = Chunks()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=chunks))
    with FabroClient(transport=transport) as c:
        with pytest.raises(FabroUnavailable, match="BYTES"):
            c.run_inventory()
    assert chunks.closed and chunks.produced <= 65


def test_shared_deadline_catches_late_final_pass(monkeypatch):
    from forge_factory.fabro import client as module
    from types import SimpleNamespace
    clock = [0.0]
    pages = Pages([run(1)])
    def changed(value, call, request):
        if call == 2:
            clock[0] = 6.0
    pages.change = changed
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0],
                        clock_gettime=lambda kind: clock[0], CLOCK_BOOTTIME=7))
    with client(pages) as c:
        with pytest.raises(FabroUnavailable, match="TIMEOUT"):
            c.run_inventory(timeout_s=5)


def test_active_and_unknown_and_removing_after_first_page_remain_observed():
    rows = [run(i) for i in range(149)] + [run(150, "running"), run(151, "UNKNOWN"), run(152, "removing")]
    with client(Pages(rows)) as c:
        observation = c.run_inventory()
    assert {r["lifecycle"]["status"]["kind"] for r in observation.rows} == {"succeeded", "running", "UNKNOWN", "removing"}


def test_repeated_status_query_uses_pinned_array_encoding():
    pages = Pages([])
    with client(pages) as c:
        result = c.run_inventory(statuses=("running", "blocked", "removing"))
    assert result.complete
    assert pages.calls[0].url.params.get_list("status") == ["running", "blocked", "removing"]
    assert pages.calls[0].url.params["include_archived"] == "true"


def test_real_http_transport_shellhost_observes_all149_terminal_and_active():
    rows = [run(i) for i in range(149)] + [run(149, "running")]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlsplit(self.path).query)
            offset, limit = int(q.get("page[offset]", [0])[0]), int(q.get("page[limit]", [50])[0])
            data = rows[offset:offset + limit]
            raw = json.dumps({"data": data, "meta": {"total": len(rows), "has_more": offset + len(data) < len(rows)}}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        host = LL.ShellHost(LL.LineConfig.from_env(fabro_host_port=server.server_port, log=False))
        observed = host.fabro_runs()
        assert len(observed) == 150 and observed[-1]["lifecycle"]["status"]["kind"] == "running"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_suspend_or_boot_change_invalidates_complete_observation(monkeypatch):
    from forge_factory.fabro import client as module
    from types import SimpleNamespace
    with client(Pages([])) as c:
        observation = c.run_inventory()
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: observation.observed_monotonic,
                        clock_gettime=lambda kind: observation.observed_boottime + 60, CLOCK_BOOTTIME=7))
    assert not observation.fresh()
    from dataclasses import replace
    assert not replace(observation, boot_identity="another-boot").fresh()


def test_partial_transport_failure_never_becomes_absence():
    class Partial(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"data":['
            raise httpx.ReadError("private interrupted body")
    with FabroClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=Partial()))) as c:
        with pytest.raises(FabroUnavailable, match="PAGE_UNAVAILABLE"):
            c.run_inventory()


def test_only_kernel_connection_refusal_has_absent_server_type():
    import errno
    from forge_factory.fabro.client import FabroConnectionUnavailable
    def refused(request):
        try:
            raise ConnectionRefusedError(errno.ECONNREFUSED, "private refusal")
        except ConnectionRefusedError as e:
            raise httpx.ConnectError("private connect", request=request) from e
    with FabroClient(transport=httpx.MockTransport(refused)) as c:
        with pytest.raises(FabroConnectionUnavailable):
            c.run_inventory()
    for exc in [httpx.ConnectTimeout("private timeout"), httpx.ConnectError("opaque connection failure")]:
        def failed(request, exc=exc):
            raise exc
        with FabroClient(transport=httpx.MockTransport(failed)) as c:
            with pytest.raises(FabroUnavailable) as failure:
                c.run_inventory()
            assert not isinstance(failure.value, FabroConnectionUnavailable)


def test_real_closed_loopback_port_is_initial_connection_refusal():
    import socket
    from forge_factory.fabro.client import FabroConnectionUnavailable
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with FabroClient(base_url=f"http://127.0.0.1:{port}") as c:
        with pytest.raises(FabroConnectionUnavailable):
            c.run_inventory()


def test_default_complete_query_includes_every_board_column():
    from forge_factory.fabro.client import ALL_RUN_COLUMNS
    pages = Pages([])
    with client(pages) as c:
        observation = c.run_inventory()
    assert observation.statuses == ALL_RUN_COLUMNS
    assert pages.calls[0].url.params.get_list("status") == list(ALL_RUN_COLUMNS)


def test_safety_query_omits_ordinary_terminal_history_but_retains_archived_unsafe_and_removing(monkeypatch):
    from forge_factory.fabro.client import UNSAFE_RUN_COLUMNS
    rows = [run(i) for i in range(20000)]
    # The pinned actual-server mapping is independently measured. This HTTP
    # transport fixture exercises the consumer query/coverage contract only.
    special = [run(30000, "paused"), run(30001, "removing"), run(30002, "succeeded")]
    for row in special:
        row["archived"] = row["id"] != "run-30001"
    rows.extend(special)
    calls = []
    def filtered(request):
        calls.append(request)
        selected = request.url.params.get_list("status")
        def board(row):
            if row.get("archived"):
                return "archived"
            return {"paused": "running"}.get(row["lifecycle"]["status"]["kind"], row["lifecycle"]["status"]["kind"])
        values = [row for row in rows if board(row) in selected]
        offset = int(request.url.params["page[offset]"])
        limit = int(request.url.params["page[limit]"])
        data = values[offset:offset + limit]
        return httpx.Response(200, json={"data": data, "meta": {"total": len(values), "has_more": offset + len(data) < len(values)}})
    host = LL.ShellHost(LL.LineConfig.from_env(log=False))
    monkeypatch.setattr(host, "_client", lambda: FabroClient(transport=httpx.MockTransport(filtered)))
    observed = host.fabro_runs()
    assert {row["id"] for row in observed} == {row["id"] for row in special}
    assert len(calls) == 2 and calls[0].url.params.get_list("status") == list(UNSAFE_RUN_COLUMNS)


@pytest.mark.parametrize("change", ["filter", "archives", "subject", "stale", "unknown-kind"])
def test_shellhost_rejects_inappropriate_complete_inventory(monkeypatch, change):
    from dataclasses import replace
    from forge_factory.fabro.client import UNSAFE_RUN_COLUMNS
    pages = Pages([run(1)])
    c = client(pages)
    observation = c.run_inventory(statuses=UNSAFE_RUN_COLUMNS)
    if change == "filter":
        observation = replace(observation, statuses=("running",))
    elif change == "archives":
        observation = replace(observation, include_archived=False)
    elif change == "subject":
        observation = replace(observation, observation_identity="foreign")
    elif change == "stale":
        observation = replace(observation, observed_boottime=observation.observed_boottime - 60)
    else:
        observation = replace(observation, rows=(run(1, "future-unknown"),))
    monkeypatch.setattr(c, "run_inventory", lambda **kw: observation)
    host = LL.ShellHost(LL.LineConfig.from_env(log=False))
    monkeypatch.setattr(host, "_client", lambda: c)
    with pytest.raises(LL.FabroInventoryUnknown):
        host.fabro_runs()


@pytest.mark.parametrize("kind", ["runnable", "starting", "running", "blocked", "paused", "removing"])
def test_m3_live_runs_recognizes_all_pinned_nonterminal_lifecycles(tmp_path, monkeypatch, kind):
    from forge_factory.afo.line_orders import RealLine
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    row = run(1, kind); row["source_directory"] = str(tmp_path / "state/workorders/private/workspace")
    cfg = LL.LineConfig.from_env(stack_root=tmp_path, log=False)
    line = RealLine(cfg)
    monkeypatch.setattr(line.host, "_client", lambda: client(Pages([row])))
    assert line.live_runs() == [row["id"]]


def test_m3_unknown_lifecycle_is_unknown_not_empty(tmp_path, monkeypatch):
    from forge_factory.afo.line_orders import RealLine
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    row = run(1, "future-unknown"); row["source_directory"] = str(tmp_path / "state/workorders/private/workspace")
    line = RealLine(LL.LineConfig.from_env(stack_root=tmp_path, log=False))
    monkeypatch.setattr(line.host, "_client", lambda: client(Pages([row])))
    assert line.live_runs() is None
