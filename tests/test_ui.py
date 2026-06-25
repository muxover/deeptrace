import pytest


def test_help_exits_zero(trace_ui):
    with pytest.raises(SystemExit) as exc:
        trace_ui.main(["--help"])
    assert exc.value.code == 0


def test_missing_playwright_hints_install(trace_ui, monkeypatch, capsys):
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("no playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    code = trace_ui.main(["http://localhost:3000"])
    out = capsys.readouterr().out

    assert code == 1
    assert "playwright install" in out


def test_report_formats_sections(trace_ui, capsys):
    trace_ui.report(
        nav="http://localhost:3000 -> 200",
        console=[("error", "boom"), ("log", "noise")],
        errors=["TypeError: x is undefined"],
        network=[("GET", 200, "http://localhost:3000/api", 12.0)],
        failures=[],
        activity={"mutations": 5, "nodes": {"div#root": 5}, "commits": 3, "react": True},
        output=None,
    )
    out = capsys.readouterr().out

    assert "UI RUNTIME TRACE" in out
    assert "[error] boom" in out
    assert "React commits: 3" in out
