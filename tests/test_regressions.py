"""Regression tests for bugs found by running each tool against real fixtures."""

import json
import os
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

# --- recon ---------------------------------------------------------------


def test_bug_marker_does_not_match_debug(recon, tmp_path):
    (tmp_path / "app.py").write_text("DEBUG = True\nlog.debug('x')\n# BUG: real one\n", encoding="utf-8")
    report = recon.scan(str(tmp_path))
    assert report["marker_count"] == 1
    assert report["markers"][0][1] == 3


def test_entry_points_from_code_and_manifests(recon, tmp_path):
    (tmp_path / "tool.py").write_text("if __name__ == '__main__':\n    pass\n", encoding="utf-8")
    (tmp_path / "cmd").mkdir()
    (tmp_path / "cmd" / "server.go").write_text("package main\n\nfunc main() {}\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(json.dumps({"main": "lib/index.js", "bin": {"x": "bin/x.js"}}),
                                           encoding="utf-8")
    entries = recon.scan(str(tmp_path))["entry_points"]
    assert "tool.py" in entries
    assert os.path.join("cmd", "server.go") in entries
    assert os.path.join("lib", "index.js") in entries
    assert os.path.join("bin", "x.js") in entries


# --- run -----------------------------------------------------------------


def test_yarn_lockfile_selects_yarn(runner, tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}', encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/" + name)
    assert ["yarn", "run", "test"] in runner.detect(str(tmp_path))["test"]


def test_package_manager_field_wins(runner, tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text('{"packageManager": "pnpm@9.1.0", "scripts": {"build": "tsc"}}',
                                           encoding="utf-8")
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/" + name)
    assert ["pnpm", "run", "build"] in runner.detect(str(tmp_path))["build"]


def test_make_only_adds_existing_targets(runner, tmp_path):
    (tmp_path / "Makefile").write_text("VAR := 1\nall:\n\techo hi\nbuild: all\n\techo b\n", encoding="utf-8")
    plans = runner.detect(str(tmp_path))
    assert ["make", "build"] in plans["build"]
    assert ["make", "test"] not in plans["test"]


def test_extra_args_after_double_dash(runner, tmp_path, capsys):
    (tmp_path / "go.mod").write_text("module demo\n", encoding="utf-8")
    runner.main([str(tmp_path), "--dry-run", "--", "-run", "TestX"])
    assert "go test ./... -run TestX" in capsys.readouterr().out


def test_npm_style_extra_args_get_separator(runner):
    assert runner.with_extra(["npm", "run", "test"], ["--watch"]) == ["npm", "run", "test", "--", "--watch"]


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX")
def test_timeout_kills_whole_process_tree(runner, tmp_path):
    marker = tmp_path / "survived"
    script = tmp_path / "spawn.sh"
    script.write_text(f"#!/bin/sh\n(sleep 3; touch {marker}) &\nsleep 30\n", encoding="utf-8")
    script.chmod(0o755)
    code, _ = runner.execute([str(script)], str(tmp_path), timeout=1)
    assert code == 124
    time.sleep(3.5)
    assert not marker.exists(), "background child outlived the timeout"


# --- trace.py ------------------------------------------------------------


def test_scope_does_not_leak_into_sibling_directory(tracer, tmp_path, capsys):
    proj, sibling = tmp_path / "proj", tmp_path / "proj2"
    proj.mkdir()
    sibling.mkdir()
    (sibling / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (proj / "main.py").write_text(
        f"import sys\nsys.path.insert(0, {str(sibling)!r})\nimport helper\nhelper.helper()\n", encoding="utf-8"
    )
    tracer.main([str(proj / "main.py")])
    assert "helper" not in capsys.readouterr().out.split("EXCEPTIONS")[0]


def test_reports_exit_code(tracer, tmp_path, capsys):
    (tmp_path / "x.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    tracer.main([str(tmp_path / "x.py")])
    assert "EXIT CODE: 3" in capsys.readouterr().out


def test_distinguishes_caught_from_uncaught(tracer, tmp_path, capsys):
    (tmp_path / "e.py").write_text(
        "def parse(s):\n    return int(s)\n"
        "def safe(s):\n    try:\n        return parse(s)\n    except ValueError:\n        return 0\n"
        "safe('x')\nparse('zz')\n",
        encoding="utf-8",
    )
    tracer.main(["--returns", str(tmp_path / "e.py")])
    out = capsys.readouterr().out
    assert "caught at e.py:6 in safe" in out
    assert "'zz'  [UNCAUGHT]" in out
    assert "<- safe = 0" in out


def test_restores_interpreter_state(tracer, tmp_path):
    (tmp_path / "noop.py").write_text("x = 1\n", encoding="utf-8")
    argv, path = sys.argv[:], sys.path[:]
    tracer.main([str(tmp_path / "noop.py"), "a", "b"])
    assert sys.argv == argv
    assert sys.path == path


# --- trace-rust / trace-go -----------------------------------------------


def test_rust_flags_after_path_are_not_passed_to_program(trace_rust):
    own, prog = trace_rust.split_program_args([".", "--bin", "app", "--", "--port", "1"])
    assert own == [".", "--bin", "app"]
    assert prog == ["--port", "1"]


def test_rust_parses_flamegraph_titles(trace_rust, tmp_path):
    svg = tmp_path / "f.svg"
    svg.write_text(
        "<svg><g><title>app::hot (1,200 samples, 60.00%)</title></g>"
        "<g><title>app::cold (10 samples, 0.50%)</title></g>"
        "<g><title>app::hot (300 samples, 15.00%)</title></g></svg>",
        encoding="utf-8",
    )
    assert trace_rust.hot_frames(str(svg), 5) == [("app::hot", 1500), ("app::cold", 10)]


def test_go_default_regex_scopes_to_module(trace_go, tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/my-app\n\ngo 1.21\n", encoding="utf-8")
    (tmp_path / "cmd").mkdir()
    regex = trace_go.default_regex(str(tmp_path / "cmd"))
    import re

    assert re.search(regex, "main.main")
    assert re.search(regex, "example.com/my-app/internal/db.Open")
    assert not re.search(regex, "runtime.main.func1")
    assert not re.search(regex, "_rt0_amd64_linux")


def test_go_summarizes_calls(trace_go):
    lines = [
        "> goroutine(1): main.add(1, 2)",
        ">> goroutine(1): main.add => (3)",
        "> goroutine(7): main.add(2, 2)",
    ]
    out = "\n".join(trace_go.summarize(lines, 5))
    assert "2  main.add" in out
    assert "goroutines seen: 2" in out


# --- trace-http ----------------------------------------------------------


class _Racy(BaseHTTPRequestHandler):
    balance = 100

    def do_POST(self):
        current = _Racy.balance
        time.sleep(0.05)
        _Racy.balance = current - 10
        body = json.dumps({"balance": _Racy.balance}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send_response(500)
        self.end_headers()
        self.wfile.write(b'{"error": "db down"}')

    def log_message(self, *args):
        pass


@pytest.fixture()
def racy_server():
    _Racy.balance = 100
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Racy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_concurrent_repeat_exposes_lost_updates(trace_http, racy_server, capsys):
    trace_http.main(["POST", racy_server + "/withdraw", "--repeat", "5", "--concurrency", "5"])
    out = capsys.readouterr().out
    assert "200 x5" in out
    assert "lost updates" in out
    assert _Racy.balance > 50, "fixture should have lost updates under concurrency"


def test_error_body_is_shown(trace_http, racy_server, capsys):
    trace_http.main(["GET", racy_server + "/x"])
    assert 'error body: {"error": "db down"}' in capsys.readouterr().out


# --- trace-ui ------------------------------------------------------------


def test_ui_report_survives_failed_navigation(trace_ui, capsys):
    trace_ui.report("x -> navigation error", [], [], [], [], None, None)
    assert "instrumentation unavailable" in capsys.readouterr().out


class _Page(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api"):
            time.sleep(0.3)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"v": 1}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<div id=r></div><script>fetch('/api').then(r=>r.json())"
                         b".then(d=>{document.getElementById('r').textContent=d.v})</script>")

    def log_message(self, *args):
        pass


def test_ui_network_timings_are_real(trace_ui, capsys):
    pytest.importorskip("playwright")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        trace_ui.main([f"http://127.0.0.1:{server.server_port}/", "--duration", "800"])
    finally:
        server.shutdown()
    out = capsys.readouterr().out
    if "UI RUNTIME TRACE" not in out:
        pytest.skip("chromium not available for playwright")
    api = next(line for line in out.splitlines() if line.rstrip().endswith("/api"))
    ms = int(api.split()[2])
    assert 250 <= ms < 5000, api


@pytest.mark.skipif(shutil.which("dlv") is None or shutil.which("go") is None, reason="go + delve not available")
def test_go_trace_end_to_end(trace_go, tmp_path, monkeypatch, capsys):
    (tmp_path / "go.mod").write_text("module example.com/demo\n\ngo 1.21\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(
        'package main\n\nimport "fmt"\n\nfunc add(a, b int) int { return a + b }\n\n'
        "func main() { fmt.Println(add(1, 2)) }\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    code = trace_go.main(["."])
    out = capsys.readouterr().out
    assert code == 0
    assert "main.add(1, 2)" in out
