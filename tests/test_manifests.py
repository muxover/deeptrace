import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def changelog_versions():
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as fh:
        return re.findall(r"^## \[(\d+\.\d+\.\d+)\]", fh.read(), re.M)


def test_manifest_versions_match_latest_changelog_entry():
    latest = changelog_versions()[0]
    versions = {
        "plugin.json": load("plugin.json")["version"],
        ".claude-plugin/plugin.json": load(".claude-plugin", "plugin.json")["version"],
        ".cursor-plugin/plugin.json": load(".cursor-plugin", "plugin.json")["version"],
    }
    assert set(versions.values()) == {latest}, versions


def test_every_version_has_release_notes():
    for version in changelog_versions():
        path = os.path.join(ROOT, "release-notes", f"v{version}.md")
        assert os.path.isfile(path), path
        with open(path, encoding="utf-8") as fh:
            assert fh.readline().startswith(f"# DeepTrace v{version} — ")


def test_marketplaces_point_at_the_repo_root():
    claude = load(".claude-plugin", "marketplace.json")
    cursor = load(".cursor-plugin", "marketplace.json")
    codex = load(".agents", "plugins", "marketplace.json")
    assert claude["plugins"][0]["source"] == "./"
    assert cursor["plugins"][0]["source"] == "./"
    assert codex["plugins"][0]["source"]["path"] == "./"
    for market in (claude, cursor, codex):
        assert market["name"] == "deeptrace"
        assert market["plugins"][0]["name"] == "deeptrace"


def test_skill_ships_only_documented_tools():
    scripts = sorted(os.listdir(os.path.join(ROOT, "skills", "deeptrace", "scripts")))
    with open(os.path.join(ROOT, "skills", "deeptrace", "scripts", "reference.md"), encoding="utf-8") as fh:
        reference = fh.read()
    for name in scripts:
        if name.endswith((".py", ".js")):
            assert f"## {name}" in reference, name
