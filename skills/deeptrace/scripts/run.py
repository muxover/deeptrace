#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def detect(root):
    plans = {"test": [], "build": [], "run": []}

    pkg_path = os.path.join(root, "package.json")
    if os.path.isfile(pkg_path):
        scripts = read_json(pkg_path).get("scripts", {})
        runner = "npm"
        for tool in ("pnpm", "yarn", "bun"):
            if shutil.which(tool) and os.path.isfile(os.path.join(root, f"{tool}-lock.yaml")):
                runner = tool
        if "test" in scripts:
            plans["test"].append([runner, "test"])
        if "build" in scripts:
            plans["build"].append([runner, "run", "build"])
        if "start" in scripts:
            plans["run"].append([runner, "start"])
        elif "dev" in scripts:
            plans["run"].append([runner, "run", "dev"])

    if any(os.path.isfile(os.path.join(root, f)) for f in ("pyproject.toml", "setup.py", "requirements.txt")):
        if shutil.which("pytest") or os.path.isdir(os.path.join(root, "tests")):
            plans["test"].append([sys.executable, "-m", "pytest", "-q"])

    if os.path.isfile(os.path.join(root, "go.mod")):
        plans["test"].append(["go", "test", "./..."])
        plans["build"].append(["go", "build", "./..."])

    if os.path.isfile(os.path.join(root, "Cargo.toml")):
        plans["test"].append(["cargo", "test"])
        plans["build"].append(["cargo", "build"])
        plans["run"].append(["cargo", "run"])

    if os.path.isfile(os.path.join(root, "Makefile")):
        plans["test"].append(["make", "test"])
        plans["build"].append(["make", "build"])

    return plans


def with_race(cmd):
    if len(cmd) >= 2 and cmd[0] == "go" and cmd[1] in ("test", "build"):
        return [cmd[0], cmd[1], "-race"] + cmd[2:]
    return None


def resolve(cmd):
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    return [exe] + cmd[1:]


def execute(cmd, root, timeout):
    resolved = resolve(cmd)
    if resolved is None:
        print(f"skip: {cmd[0]!r} not found on PATH")
        return None
    print(f"$ {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            resolved, cwd=root, timeout=timeout,
            capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired:
        print(f"timeout after {timeout}s")
        return 124
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    print(f"exit code: {proc.returncode}")
    return proc.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detect and run a project's commands for DeepTrace.")
    parser.add_argument("path", nargs="?", default=".", help="project root")
    parser.add_argument("--what", choices=["test", "build", "run"], default="test")
    parser.add_argument("--timeout", type=int, default=300, help="per-command timeout in seconds")
    parser.add_argument("--race", action="store_true", help="enable the data-race detector where the stack supports it")
    parser.add_argument("--dry-run", action="store_true", help="print detected commands without running")
    args = parser.parse_args(argv)

    root = os.path.realpath(args.path)
    plans = detect(root)
    commands = plans[args.what]

    if not commands:
        print(f"no {args.what} command detected for this project")
        return 1

    if args.race:
        raced, applied = [], False
        for cmd in commands:
            variant = with_race(cmd)
            raced.append(variant or cmd)
            applied = applied or variant is not None
        commands = raced
        if not applied:
            print("note: --race has no native flag for this stack. Go uses -race; "
                  "for Node lean on trace.py thread tags, for Rust on miri or loom.")

    if args.dry_run:
        print(f"detected {args.what} commands:")
        for cmd in commands:
            print(f"  {' '.join(cmd)}")
        return 0

    worst = 0
    for cmd in commands:
        code = execute(cmd, root, args.timeout)
        if code:
            worst = code
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
