#!/usr/bin/env python3
import argparse
import json
import os
import sys
from collections import Counter

IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "target", ".next", ".turbo", ".pytest_cache", ".ruff_cache", ".idea",
    ".vscode", ".cursor", "coverage", ".mypy_cache", "vendor", ".gradle",
}

LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".cs": "C#", ".swift": "Swift", ".scala": "Scala", ".sh": "Shell",
    ".sql": "SQL", ".vue": "Vue", ".svelte": "Svelte",
}

MANIFESTS = {
    "package.json": "Node",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "setup.py": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "Makefile": "Make",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
}

ENTRY_HINTS = (
    "main.py", "__main__.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts", "main.js", "main.ts",
    "main.go", "main.rs",
)

MARKERS = ("TODO", "FIXME", "HACK", "XXX", "BUG")


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for name in filenames:
            yield os.path.join(dirpath, name)


def count_lines(path):
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def scan(root):
    languages = Counter()
    loc = Counter()
    manifests = []
    entry_points = []
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
        if base in ENTRY_HINTS:
            entry_points.append(rel)

        lang = LANG_BY_EXT.get(ext)
        if lang:
            lines = count_lines(path)
            languages[lang] += 1
            loc[lang] += lines
            file_sizes.append((lines, rel))
            scan_markers(path, rel, markers)

    file_sizes.sort(reverse=True)
    return {
        "root": os.path.realpath(root),
        "total_files": total_files,
        "languages": dict(languages.most_common()),
        "loc": dict(loc.most_common()),
        "manifests": manifests,
        "entry_points": sorted(set(entry_points)),
        "largest_files": file_sizes[:10],
        "markers": markers[:50],
        "marker_count": len(markers),
    }


def scan_markers(path, rel, markers):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for n, line in enumerate(fh, 1):
                for marker in MARKERS:
                    if marker in line:
                        markers.append((rel, n, marker, line.strip()[:120]))
                        break
    except OSError:
        pass


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

    out.append("\nEntry points:")
    if report["entry_points"]:
        for rel in report["entry_points"]:
            out.append(f"  {rel}")
    else:
        out.append("  none matched common entry names")

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
