"""BevDeciderBackend against a fake bev-decide (stdlib HTTP server in a thread),
and the mock backend's decider answer. Asserts on the returned LLMReply."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from fieldmind.runtime.llm_backend import (BevDeciderBackend, LLMReply, MockBackend,
                                           make_backend)

ANSWERS = {"root_cause": {"type": "choice", "choice": "RCA-07",
                          "probabilities": {"RCA-07": 0.7, "RCA-14": 0.2, "RCA-18": 0.1}}}
CANNED = {"model": "bev-decider-0.4b", "answers": ANSWERS, "latency_ms": 812.3,
          "usage": {"prompt_tokens": 431},
          "timings": {"tokenize_ms": 1.5, "decode_ms": 640.25, "head_ms": 3.0}}


class _Handler(BaseHTTPRequestHandler):
    mode = "ok"
    last_path = ""
    last_body = b""

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        _Handler.last_path = self.path
        _Handler.last_body = self.rfile.read(n)
        mode = _Handler.mode
        if mode == "drop":                  # read the request, then hang up
            self.close_connection = True
            return
        if mode == "slow":
            time.sleep(1.5)
        if mode == "http400":
            body = b'{"error": "invalid question q: unknown question type"}'
            self.send_response(400)
        else:
            reply = dict(CANNED)
            if mode == "python_server":     # bev_decider serve: no usage, no timings
                reply = {"model": "bev-decider-0.4b", "answers": ANSWERS, "latency_ms": 90.1}
            if mode == "no_answers":
                reply = {"model": "x"}
            body = b"not json{" if mode == "malformed" else json.dumps(reply).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _b(url, **kw):
    return BevDeciderBackend(url=url, lane="bev", model_file="bev-Q8_0.gguf", **kw)


REQUEST = json.dumps({"state": "facts", "questions": {"root_cause": {
    "type": "choice", "instructions": "q", "criteria": {"RCA-07": "a", "RCA-14": "b"}}}})


def test_reply_fields_come_from_the_server(server):
    _Handler.mode = "ok"
    r = _b(server).generate(REQUEST)
    assert isinstance(r, LLMReply) and r.status == "ok"
    assert json.loads(r.text)["answers"] == ANSWERS
    assert r.prefill_tokens == 431
    assert r.decode_tokens == 0 and r.decode_ms == 0.0      # nothing generated
    assert r.ttft_ms == pytest.approx(640.25)                # server transformer time
    assert r.backend == "bev" and r.model == "bev-Q8_0.gguf"
    assert r.latency_ms > 0


def test_the_request_is_the_prompt_posted_to_systemone(server):
    _Handler.mode = "ok"
    _b(server).generate(REQUEST)
    assert _Handler.last_path == "/v1/systemone"
    assert _Handler.last_body == REQUEST.encode()


def test_bev_deciders_own_server_without_usage_gives_none_not_zero(server):
    _Handler.mode = "python_server"
    r = _b(server).generate(REQUEST)
    assert r.status == "ok"
    assert r.prefill_tokens is None and r.ttft_ms is None
    _Handler.mode = "ok"


@pytest.mark.parametrize("mode,status,why", [
    ("http400", "error", "400"),
    ("malformed", "error", "malformed"),
    ("no_answers", "error", "no answers"),
    ("drop", "error", "connection dropped"),
])
def test_failures_are_failed_calls_not_exceptions(server, mode, status, why):
    _Handler.mode = mode
    r = _b(server).generate(REQUEST)
    _Handler.mode = "ok"
    assert r.status == status and why in r.error
    assert r.text == "" and r.prefill_tokens is None and r.decode_tokens is None


def test_timeout(server):
    _Handler.mode = "slow"
    r = _b(server, timeout_s=0.3).generate(REQUEST)
    _Handler.mode = "ok"
    assert r.status == "timeout"


def test_connection_refused_is_error():
    r = BevDeciderBackend(url="http://127.0.0.1:9", timeout_s=2).generate(REQUEST)
    assert r.status == "error"


def test_registered_and_built_from_config(server):
    b = make_backend({"backend": "bevdecider", "bevdecider": {"url": server, "lane": "bev"}})
    assert isinstance(b, BevDeciderBackend) and b.lane == "bev"


def test_mock_decider_picks_the_first_offered_option_and_sums_to_one():
    r = MockBackend().generate("{}", role="decider",
                               mock_hint={"options": ["RCA-14", "RCA-07", "RCA-18"]})
    a = json.loads(r.text)["answers"]["root_cause"]
    assert a["choice"] == "RCA-14"
    p = a["probabilities"]
    assert list(p) == ["RCA-14", "RCA-07", "RCA-18"]
    assert p["RCA-14"] > p["RCA-07"] > p["RCA-18"]
    assert sum(p.values()) == pytest.approx(1.0)
