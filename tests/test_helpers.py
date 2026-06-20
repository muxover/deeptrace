import os
import shutil
import subprocess

import pytest


def test_rust_passthrough_prefixes_separator(trace_rust):
    assert trace_rust.passthrough(["arg"]) == ["--", "arg"]
    assert trace_rust.passthrough(["--", "arg"]) == ["--", "arg"]
    assert trace_rust.passthrough([]) == []


def test_go_help_exits_zero(trace_go):
    with pytest.raises(SystemExit) as exc:
        trace_go.main(["--help"])
    assert exc.value.code == 0


def test_rust_help_exits_zero(trace_rust):
    with pytest.raises(SystemExit) as exc:
        trace_rust.main(["--help"])
    assert exc.value.code == 0


def test_node_tracer_runs(scripts_dir, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")

    script = tmp_path / "demo.js"
    script.write_text(
        "function work() { let s = 0; for (let i = 0; i < 2000000; i++) s += i; return s; }\nwork();\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [node, os.path.join(scripts_dir, "trace-node.js"), str(script)],
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 0
    assert "EXECUTION TRACE" in result.stdout
