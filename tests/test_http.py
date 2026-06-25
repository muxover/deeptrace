import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


def test_parse_headers(trace_http):
    headers = trace_http.parse_headers(["Authorization: Bearer t", "X-Bad", "Accept: application/json"])
    assert headers == {"Authorization": "Bearer t", "Accept": "application/json"}


def test_shape_object(trace_http):
    body = json.dumps({"id": 1, "name": "x", "ok": True})
    assert trace_http.shape(body, "application/json") == "{ id: number, name: string, ok: bool }"


def test_shape_list(trace_http):
    assert trace_http.shape("[1, 2, 3]", "application/json") == "list[3] of number"


def test_shape_ignores_non_json(trace_http):
    assert trace_http.shape("<html>", "text/html") is None


def test_main_requires_method_and_url(trace_http):
    with pytest.raises(SystemExit) as exc:
        trace_http.main([])
    assert exc.value.code == 2


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args):
        pass


def test_captures_real_response(trace_http, capsys):
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/ping"
        code = trace_http.main(["GET", url])
    finally:
        server.shutdown()

    out = capsys.readouterr().out
    assert code == 0
    assert "200 OK" in out
    assert "ok: bool" in out
