def test_dry_run_detects_pytest(runner, tmp_path):
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    code = runner.main([str(tmp_path), "--what", "test", "--dry-run"])

    assert code == 0


def test_dry_run_detects_npm_test(runner, tmp_path, capsys):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}', encoding="utf-8")

    code = runner.main([str(tmp_path), "--what", "test", "--dry-run"])
    out = capsys.readouterr().out

    assert code == 0
    assert "test" in out


def test_no_command_returns_one(runner, tmp_path):
    code = runner.main([str(tmp_path), "--what", "test", "--dry-run"])
    assert code == 1


def test_detect_go_build(runner, tmp_path):
    (tmp_path / "go.mod").write_text("module demo\n", encoding="utf-8")
    plans = runner.detect(str(tmp_path))
    assert ["go", "build", "./..."] in plans["build"]
