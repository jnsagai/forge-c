"""HTTP enumeration completeness; no model, canonical store or native mutation."""
import contextlib
import copy
import gzip
import json
import socket
import threading
import tracemalloc
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from forge_factory.afo import line_launcher as LL
from forge_factory.fabro.client import FabroClient, FabroConnectionUnavailable, FabroUnavailable


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


class Chunks(httpx.AsyncByteStream):
    def __init__(self):
        self.produced = 0
        self.closed = False

    async def __aiter__(self):
        for _ in range(10000):
            self.produced += 1
            yield b"x" * 65536

    async def aclose(self):
        self.closed = True


def test_streaming_byte_bound_closes_before_reading_unbounded_body():
    chunks = Chunks()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=chunks))
    with FabroClient(transport=transport) as c:
        with pytest.raises(FabroUnavailable, match="BYTES"):
            c.run_inventory()
    assert chunks.closed and chunks.produced <= 65


def test_shared_deadline_catches_late_final_pass(monkeypatch):
    from types import SimpleNamespace

    from forge_factory.fabro import client as module
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
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = LL.ShellHost(LL.LineConfig.from_env(fabro_host_port=server.server_port, log=False))
        observed = host.fabro_runs()
        assert len(observed) == 150 and observed[-1]["lifecycle"]["status"]["kind"] == "running"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_suspend_or_boot_change_invalidates_complete_observation(monkeypatch):
    from types import SimpleNamespace

    from forge_factory.fabro import client as module
    with client(Pages([])) as c:
        observation = c.run_inventory()
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: observation.observed_monotonic,
                        clock_gettime=lambda kind: observation.observed_boottime + 60, CLOCK_BOOTTIME=7))
    assert not observation.fresh()
    from dataclasses import replace
    assert not replace(observation, boot_identity="another-boot").fresh()


def test_partial_transport_failure_never_becomes_absence():
    class Partial(httpx.AsyncByteStream):
        async def __aiter__(self):
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
    row = run(1, kind)
    row["source_directory"] = str(tmp_path / "state/workorders/private/workspace")
    cfg = LL.LineConfig.from_env(stack_root=tmp_path, log=False)
    line = RealLine(cfg)
    monkeypatch.setattr(line.host, "_client", lambda: client(Pages([row])))
    assert line.live_runs() == [row["id"]]


def test_m3_unknown_lifecycle_is_unknown_not_empty(tmp_path, monkeypatch):
    from forge_factory.afo.line_orders import RealLine
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    row = run(1, "future-unknown")
    row["source_directory"] = str(tmp_path / "state/workorders/private/workspace")
    line = RealLine(LL.LineConfig.from_env(stack_root=tmp_path, log=False))
    monkeypatch.setattr(line.host, "_client", lambda: client(Pages([row])))
    assert line.live_runs() is None


@pytest.mark.parametrize("mode", ["slow-headers", "slow-trickle-body"])
def test_real_http_total_deadline_cancels_header_and_raw_body_waits(mode):
    import time
    stop = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if mode == "slow-headers" and stop.wait(3):
                return
            try:
                self.send_response(200)
                self.send_header("Content-Length", "10000")
                self.end_headers()
                while not stop.wait(0.03):
                    self.wfile.write(b" ")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        before = time.monotonic()
        with FabroClient(base_url=f"http://127.0.0.1:{server.server_port}") as c:
            with pytest.raises(FabroUnavailable, match="TIMEOUT"):
                c.run_inventory(timeout_s=0.3)
        assert time.monotonic() - before < 1.5
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_sync_inventory_refuses_running_event_loop_without_network():
    import asyncio
    pages = Pages([])
    async def check():
        with client(pages) as c:
            with pytest.raises(FabroUnavailable, match="SYNC_IN_ASYNC"):
                c.run_inventory()
    asyncio.run(check())
    assert pages.calls == []


def test_sync_only_mock_transport_is_refused_without_real_network_fallback():
    class SyncOnly(httpx.BaseTransport):
        def handle_request(self, request):
            pytest.fail("unsupported transport was used")
    with FabroClient(transport=SyncOnly()) as c:
        with pytest.raises(FabroUnavailable, match="TRANSPORT_UNSUPPORTED"):
            c.run_inventory()


def test_async_transport_keeps_exact_authentication_endpoint_and_subject():
    pages = Pages([])
    with FabroClient(base_url="http://private-fixture.invalid:12345", token="TEST_ONLY_NOT_OWNER_TOKEN",
                     transport=httpx.MockTransport(pages)) as c:
        observation = c.run_inventory()
        assert observation.observation_identity == c.observation_identity
    assert len(pages.calls) == 2
    assert all(r.url.host == "private-fixture.invalid" and r.url.port == 12345
               and r.headers["Authorization"] == "Bearer TEST_ONLY_NOT_OWNER_TOKEN" for r in pages.calls)


@pytest.mark.parametrize("source", ["/another-project/workspace", None, ""])
@pytest.mark.parametrize("kind", ["runnable", "starting", "blocked", "removing"])
def test_actual_pre_admission_retains_all_counters_when_foreign_or_unknown_source_is_unsafe(tmp_path, monkeypatch, source, kind):
    # Real TEST signatures, normal Placer.cycle and actual private SQLite. The
    # fixture substitutes only normal line workproduct/backend leaves and HTTP.
    import sqlite3
    from contextlib import closing

    from forge_factory.afo import line_orders as LO
    from forge_factory.afo.mission_ledger import MissionLedger
    from forge_factory.afo.queue import Store
    from test_line_conductor_m3 import env as env_fixture
    from test_line_conductor_m3 import grant, lineage, placer, write_campaign
    generator = env_fixture.__wrapped__(tmp_path, monkeypatch)
    environment = generator
    write_campaign(environment, [lineage("crc-ll", "CRCL", "20261103-L30")])
    grant(environment)
    cfg = LL.LineConfig.from_env(stack_root=tmp_path, log=False)
    actual = LO.RealLine(cfg)
    row = run(1, kind)
    row["source_directory"] = source
    monkeypatch.setattr(actual.host, "_client", lambda: client(Pages([row])))
    environment["line"].live_runs = actual.live_runs
    p = placer(environment)
    store = Store(p.queue_path)
    limits = {"deadline": environment["clock"]() + 300, "max_attempts": 4, "max_jobs": 4, "max_requests": 32,
              "max_tokens": 8388608, "max_tools": 256, "max_corrections": 4}
    ledger = MissionLedger(store)
    ledger.register("private-no-admission-mission", "private-lineage", limits, "TEST_ONLY", authorize=lambda *_: True)
    snapshot = ledger.snapshot("private-no-admission-mission")
    def counts():
        with closing(sqlite3.connect(p.queue_path)) as c:
            return {t: c.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in
                    ("afo_attempts", "afo_work_orders", "afo_commands_outbox", "afo_product_jobs", "afo_mission_executions")}
    before = counts()
    result = p.cycle()
    assert result["gpu"]["busy"] and result["gpu"]["reason"] == "RUN_LIVE_NOT_IN_CAMPAIGN"
    assert counts() == before and ledger.snapshot("private-no-admission-mission") == snapshot
    assert environment["line"].launched == []


# Real HTTP/1.1 wire controls. The original fixtures never compressed anything,
# so the measured gzip default of the pinned server escaped every offline check.
@contextlib.contextmanager
def wire(respond):
    """`respond(handler, request_number, rows_page)` owns the whole response."""
    seen = []
    rows = [run(i) for i in range(149)]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            self.headers.add_header("X-Rehearsal-Path", self.path)
            seen.append(self.headers)
            q = parse_qs(urlsplit(self.path).query)
            offset, limit = int(q.get("page[offset]", [0])[0]), int(q.get("page[limit]", [50])[0])
            data = rows[offset:offset + limit]
            raw = json.dumps({"data": data, "meta": {"total": len(rows), "has_more": offset + len(data) < len(rows)}}).encode()
            try:
                respond(self, len(seen), raw)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def send(handler, raw, *headers):
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    for name, value in headers:
        handler.send_header(name, value)
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def measured_negotiation(handler, _, raw):
    """The pinned 0.362 server: gzip when offered, otherwise honest identity."""
    accepted = handler.headers.get("Accept-Encoding", "")
    if "gzip" in accepted:
        send(handler, gzip.compress(raw), ("Content-Encoding", "gzip"))
    else:
        send(handler, raw)


def test_real_http_measured_negotiation_observes_complete_catalog_with_identity():
    with wire(measured_negotiation) as (url, seen):
        with FabroClient(base_url=url, token="PRIVATE_TEST_ONLY") as c:
            observation = c.run_inventory()
    assert observation.complete and len(observation.rows) == 149 and observation.pages == 4
    assert [h["Accept-Encoding"] for h in seen] == ["identity"] * 4
    assert {h["Authorization"] for h in seen} == {"Bearer PRIVATE_TEST_ONLY"}


def test_identity_negotiation_is_inventory_scoped_and_leaves_legacy_decoding_alone():
    with wire(measured_negotiation) as (url, seen):
        with FabroClient(base_url=url) as c:
            assert len(c.list_runs(limit=100)) == 100
    assert "gzip" in seen[0]["Accept-Encoding"]


@pytest.mark.parametrize(("position", "first_bad", "expected_requests"),
                         [("first-page", 1, 1), ("later-page", 2, 2), ("second-pass", 3, 3), ("second-pass-later", 4, 4)])
def test_real_http_server_ignoring_identity_is_typed_unknown_never_absent(position, first_bad, expected_requests):
    def ignoring(handler, number, raw):
        if number >= first_bad:
            send(handler, gzip.compress(raw), ("Content-Encoding", "gzip"))
        else:
            send(handler, raw)
    with wire(ignoring) as (url, seen):
        with FabroClient(base_url=url) as c:
            with pytest.raises(FabroUnavailable, match="^RUN_INVENTORY_CONTENT_ENCODING_UNEXPECTED$") as failure:
                c.run_inventory()
    assert not isinstance(failure.value, FabroConnectionUnavailable)
    assert len(seen) == expected_requests, position


@pytest.mark.parametrize("values", [("br",), ("deflate",), ("GZIP",), ("gzip, identity",), ("identity, gzip",),
                                    ("",), ("identity", "gzip"), ("gzip", "identity")])
def test_real_http_any_non_identity_coding_refuses_before_json(values):
    def coded(handler, _, raw):
        send(handler, raw, *[("Content-Encoding", value) for value in values])
    with wire(coded) as (url, _):
        with FabroClient(base_url=url) as c:
            with pytest.raises(FabroUnavailable, match="CONTENT_ENCODING_UNEXPECTED"):
                c.run_inventory()


@pytest.mark.parametrize("value", ["identity", "IDENTITY", " Identity "])
def test_real_http_explicit_identity_coding_is_the_same_as_none(value):
    with wire(lambda handler, _, raw: send(handler, raw, ("Content-Encoding", value))) as (url, _):
        with FabroClient(base_url=url) as c:
            assert len(c.run_inventory().rows) == 149


def test_real_http_compression_bomb_is_refused_without_inflating():
    bomb = gzip.compress(b"\0" * (64 * 1024 * 1024), compresslevel=9)
    assert len(bomb) < 128 * 1024
    with wire(lambda handler, _, raw: send(handler, bomb, ("Content-Encoding", "gzip"))) as (url, _):
        tracemalloc.start()
        try:
            with FabroClient(base_url=url) as c:
                with pytest.raises(FabroUnavailable, match="CONTENT_ENCODING_UNEXPECTED"):
                    c.run_inventory()
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
    assert peak < 8 * 1024 * 1024


def test_unexpected_coding_closes_stream_before_reading_any_body():
    chunks = Chunks()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=chunks))
    with FabroClient(transport=transport) as c:
        with pytest.raises(FabroUnavailable, match="CONTENT_ENCODING_UNEXPECTED"):
            c.run_inventory()
    assert chunks.closed and chunks.produced == 0


def test_materialized_coded_response_is_refused_by_the_same_rule():
    body = gzip.compress(b'{"data":[],"meta":{"has_more":false,"total":0}}')
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=body))
    with FabroClient(transport=transport) as c:
        with pytest.raises(FabroUnavailable, match="CONTENT_ENCODING_UNEXPECTED"):
            c.run_inventory()


def test_real_http_chunked_framing_is_not_a_content_coding():
    def chunked(handler, _, raw):
        handler.send_response(200)
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        for start in range(0, len(raw), 4096):
            part = raw[start:start + 4096]
            handler.wfile.write(b"%x\r\n%s\r\n" % (len(part), part))
        handler.wfile.write(b"0\r\n\r\n")
    with wire(chunked) as (url, _):
        with FabroClient(base_url=url) as c:
            assert len(c.run_inventory().rows) == 149


@pytest.mark.parametrize("first_bad", [1, 2, 3])
def test_real_http_truncated_identity_body_is_unknown_never_absent(first_bad):
    def truncated(handler, number, raw):
        if number < first_bad:
            return send(handler, raw)
        handler.send_response(200)
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw[:len(raw) // 2])
        handler.wfile.flush()
        handler.close_connection = True
    with wire(truncated) as (url, _):
        with FabroClient(base_url=url) as c:
            with pytest.raises(FabroUnavailable, match="PAGE_UNAVAILABLE") as failure:
                c.run_inventory()
    assert not isinstance(failure.value, FabroConnectionUnavailable)


def test_real_http_page_and_shared_byte_bounds_apply_to_identity_wire_bytes():
    oversized = b" " * (4 * 1024 * 1024 + 1)
    with wire(lambda handler, _, raw: send(handler, oversized)) as (url, _):
        with FabroClient(base_url=url) as c:
            with pytest.raises(FabroUnavailable, match="BYTES"):
                c.run_inventory()
    with wire(measured_negotiation) as (url, seen):
        with FabroClient(base_url=url) as c:
            one_pass = c.run_inventory().pages // 2
            assert one_pass == 2
            with pytest.raises(FabroUnavailable, match="BYTES"):
                c.run_inventory(max_bytes=34 * 1024)  # Both 149-row passes cannot fit on the identity wire.
    assert 2 < len(seen) - 4 <= 4


def set_environment_proxy(monkeypatch, url):
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, url)


def closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_dead_environment_proxy_refusal_is_never_read_as_absent_server(monkeypatch):
    """Otherwise ECONNREFUSED from the proxy proves nothing about the server."""
    with wire(measured_negotiation) as (url, seen):
        set_environment_proxy(monkeypatch, f"http://127.0.0.1:{closed_port()}")
        with FabroClient(base_url=url) as c:
            assert len(c.run_inventory().rows) == 149
    assert len(seen) == 4


def test_listening_environment_proxy_cannot_answer_for_the_catalog(monkeypatch):
    def empty(handler, _, raw):
        send(handler, b'{"data":[],"meta":{"has_more":false,"total":0}}')
    with wire(empty) as (proxy, intercepted), wire(measured_negotiation) as (url, seen):
        set_environment_proxy(monkeypatch, proxy)
        with FabroClient(base_url=url) as c:
            assert len(c.run_inventory().rows) == 149
    # Ephemeral ports can receive stray local connections; only a catalog read would be the defect.
    assert not [h for h in intercepted if h["X-Rehearsal-Path"].startswith("/api/v1/runs")] and len(seen) == 4


def test_genuine_closed_port_stays_initial_absence_with_environment_proxy_set(monkeypatch):
    set_environment_proxy(monkeypatch, f"http://127.0.0.1:{closed_port()}")
    with FabroClient(base_url=f"http://127.0.0.1:{closed_port()}") as c:
        with pytest.raises(FabroConnectionUnavailable):
            c.run_inventory()
