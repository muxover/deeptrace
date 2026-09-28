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
