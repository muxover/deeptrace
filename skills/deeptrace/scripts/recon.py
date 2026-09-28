#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from collections import Counter

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "target", ".next", ".turbo", ".pytest_cache", ".ruff_cache", ".idea",
    ".vscode", ".cursor", "coverage", ".mypy_cache", "vendor", ".gradle",
}

LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".cs": "C#", ".swift": "Swift", ".scala": "Scala", ".sh": "Shell",
    ".sql": "SQL", ".vue": "Vue", ".svelte": "Svelte",
}

MANIFESTS = {
    "package.json": "Node",
    "deno.json": "Deno",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "setup.py": "Python",
    "setup.cfg": "Python",
    "Pipfile": "Python",
    "go.mod": "Go",
    "go.work": "Go (workspace)",
    "Cargo.toml": "Rust",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "build.gradle.kts": "Java/Kotlin (Gradle)",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "Makefile": "Make",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
    "compose.yml": "Docker Compose",
    "compose.yaml": "Docker Compose",
}

ENTRY_HINTS = (
    "main.py", "__main__.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts", "main.js", "main.ts",
    "main.go", "main.rs",
)

MINIFIED = (".min.js", ".bundle.js", ".min.css")

MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\b")
PY_MAIN_RE = re.compile(r"""^if\s+__name__\s*==\s*['"]__main__['"]\s*:""", re.M)
GO_MAIN_RE = re.compile(r"^package\s+main\b[\s\S]*?^func\s+main\s*\(", re.M)
RS_MAIN_RE = re.compile(r"^\s*(pub\s+)?(async\s+)?fn\s+main\s*\(", re.M)

MAX_READ_BYTES = 2_000_000


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def read_text(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_READ_BYTES)
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="ignore")


def declared_entries(root, rel_dir, base, text):
    found = []
    here = rel_dir if rel_dir != "." else ""
    if base == "package.json":
        try:
            pkg = json.loads(text)
        except ValueError:
            return found
        if isinstance(pkg.get("main"), str):
            found.append(os.path.normpath(os.path.join(here, pkg["main"])))
        bins = pkg.get("bin")
        if isinstance(bins, str):
            found.append(os.path.normpath(os.path.join(here, bins)))
        elif isinstance(bins, dict):
            found.extend(os.path.normpath(os.path.join(here, v)) for v in bins.values() if isinstance(v, str))
        scripts = pkg.get("scripts") or {}
        for key in ("start", "dev", "serve"):
            if isinstance(scripts.get(key), str):
                found.append(f"npm script '{key}': {scripts[key]}")
    elif base == "pyproject.toml" and tomllib is not None:
        try:
            data = tomllib.loads(text)
        except (ValueError, tomllib.TOMLDecodeError):
            return found
        for name, target in ((data.get("project") or {}).get("scripts") or {}).items():
            found.append(f"console script '{name}': {target}")
        poetry = ((data.get("tool") or {}).get("poetry") or {}).get("scripts") or {}
        for name, target in poetry.items():
            found.append(f"console script '{name}': {target}")
    elif base == "Cargo.toml" and tomllib is not None:
        try:
            data = tomllib.loads(text)
        except (ValueError, tomllib.TOMLDecodeError):
            return found
        for binary in data.get("bin") or []:
            if isinstance(binary, dict) and binary.get("path"):
                found.append(os.path.normpath(os.path.join(here, binary["path"])))
    return found


def scan(root):
    languages = Counter()
    loc = Counter()
    manifests = []
    entry_points = set()
    markers = []
    file_sizes = []
    total_files = 0

    for path in walk(root):
        total_files += 1
        rel = os.path.relpath(path, root)
        base = os.path.basename(path)
        ext = os.path.splitext(base)[1].lower()

        if base in MANIFESTS:
            manifests.append((rel, MANIFESTS[base]))
            text = read_text(path)
            if text is not None:
                entry_points.update(declared_entries(root, os.path.dirname(rel) or ".", base, text))
        if base in ENTRY_HINTS:
            entry_points.add(rel)

        lang = LANG_BY_EXT.get(ext)
        if not lang or base.endswith(MINIFIED):
            continue
        text = read_text(path)
        if text is None:
            continue
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        languages[lang] += 1
        loc[lang] += lines
        file_sizes.append((lines, rel))
        scan_markers(text, rel, markers)
        if (lang == "Python" and PY_MAIN_RE.search(text)) or (lang == "Go" and GO_MAIN_RE.search(text)) or (
            lang == "Rust" and RS_MAIN_RE.search(text)
        ):
            entry_points.add(rel)

    file_sizes.sort(key=lambda item: (-item[0], item[1]))
    return {
        "root": os.path.realpath(root),
        "total_files": total_files,
        "languages": dict(languages.most_common()),
        "loc": dict(loc.most_common()),
        "manifests": manifests,
        "entry_points": sorted(entry_points),
        "largest_files": file_sizes[:10],
        "markers": markers[:50],
        "marker_count": len(markers),
    }


def scan_markers(text, rel, markers):
    for n, line in enumerate(text.splitlines(), 1):
        match = MARKER_RE.search(line)
        if match:
            markers.append((rel, n, match.group(1), line.strip()[:120]))


def render(report):
    out = []
    out.append(f"Project: {report['root']}")
    out.append(f"Files scanned: {report['total_files']}")

    out.append("\nStacks detected:")
    if report["manifests"]:
        for rel, kind in report["manifests"]:
            out.append(f"  {kind:<24} {rel}")
    else:
        out.append("  none detected from manifests")

    out.append("\nLanguages (files / lines):")
    for lang, files in report["languages"].items():
        out.append(f"  {lang:<14} {files:>5} files  {report['loc'].get(lang, 0):>8} loc")

    out.append("\nEntry points (by name, manifest, or main function):")
    if report["entry_points"]:
        for rel in report["entry_points"]:
            out.append(f"  {rel}")
    else:
        out.append("  none found")

    out.append("\nLargest source files (complexity hotspots):")
    for lines, rel in report["largest_files"]:
        out.append(f"  {lines:>6} loc  {rel}")

    out.append(f"\nMarkers (TODO/FIXME/HACK/XXX/BUG): {report['marker_count']}")
    for rel, n, marker, text in report["markers"][:20]:
        out.append(f"  {rel}:{n}  {marker}  {text}")

    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Static reconnaissance of a project for DeepTrace.")
    parser.add_argument("path", nargs="?", default=".", help="project root to scan")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.path):
        print(f"error: {args.path} is not a directory", file=sys.stderr)
        return 2

    report = scan(args.path)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
