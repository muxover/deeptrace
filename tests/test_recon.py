def test_detects_languages_manifests_and_markers(recon, tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "echo hi"}}', encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1  # TODO fix this\n", encoding="utf-8")
    (tmp_path / "util.go").write_text("package main\n", encoding="utf-8")

    report = recon.scan(str(tmp_path))

    assert report["languages"].get("Python") == 1
    assert report["languages"].get("Go") == 1
    kinds = {kind for _, kind in report["manifests"]}
    assert "Node" in kinds
    assert report["marker_count"] >= 1
    assert "app.py" in report["entry_points"]


def test_ignores_vendor_directories(recon, tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("module.exports = 1\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")

    report = recon.scan(str(tmp_path))

    assert report["languages"].get("JavaScript") is None
    assert report["languages"].get("Python") == 1


def test_json_mode_runs(recon, tmp_path, capsys):
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    code = recon.main([str(tmp_path), "--json"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"languages"' in out
