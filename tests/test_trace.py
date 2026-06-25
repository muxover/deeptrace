def test_captures_calls_args_and_exception(tracer, tmp_path, capsys):
    script = tmp_path / "demo.py"
    script.write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def main():\n"
        "    add(1, 2)\n"
        "    raise ValueError('boom')\n"
        "\n"
        "main()\n",
        encoding="utf-8",
    )

    code = tracer.main(["--args", str(script)])
    out = capsys.readouterr().out

    assert code == 0
    assert "add(a=1, b=2)" in out
    assert "ValueError: boom" in out
    assert "UNCAUGHT: ValueError: boom" in out


def test_traces_spawned_threads(tracer, tmp_path, capsys):
    script = tmp_path / "threaded.py"
    script.write_text(
        "import threading\n"
        "\n"
        "def worker():\n"
        "    return 42\n"
        "\n"
        "t = threading.Thread(target=worker, name='W1')\n"
        "t.start()\n"
        "t.join()\n",
        encoding="utf-8",
    )

    tracer.main([str(script)])
    out = capsys.readouterr().out

    assert "worker" in out
    assert "[W1]" in out


def test_missing_target_returns_two(tracer, tmp_path):
    code = tracer.main([str(tmp_path / "nope.py")])
    assert code == 2
