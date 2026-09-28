#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

LOCKFILES = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
    ("package-lock.json", "npm"),
)

MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", re.M)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def node_runner(root, pkg):
    wanted = None
    declared = pkg.get("packageManager")
    if isinstance(declared, str) and declared:
        wanted = declared.split("@", 1)[0]
    if wanted is None:
        for lockfile, tool in LOCKFILES:
            if os.path.isfile(os.path.join(root, lockfile)):
                wanted = tool
                break
    if wanted and wanted != "npm" and shutil.which(wanted) is None:
        print(f"note: project uses {wanted} but it is not on PATH; falling back to npm")
        return "npm"
    return wanted or "npm"


def python_exe(root):
    # the project's own venv, so tests see its dependencies
    for venv in (".venv", "venv", "env"):
        for rel in (("bin", "python"), ("Scripts", "python.exe")):
            candidate = os.path.join(root, venv, *rel)
            if os.path.isfile(candidate):
                return candidate
    return sys.executable


def has_module(python, module):
    try:
        proc = subprocess.run([python, "-c", f"import {module}"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def make_targets(root):
    try:
        with open(os.path.join(root, "Makefile"), encoding="utf-8", errors="ignore") as fh:
            return set(MAKE_TARGET_RE.findall(fh.read()))
    except OSError:
        return set()


def detect(root):
    plans = {"test": [], "build": [], "run": []}

    pkg_path = os.path.join(root, "package.json")
    if os.path.isfile(pkg_path):
        pkg = read_json(pkg_path)
        scripts = pkg.get("scripts") or {}
        runner = node_runner(root, pkg)
        if "test" in scripts:
            plans["test"].append([runner, "run", "test"])
        if "build" in scripts:
            plans["build"].append([runner, "run", "build"])
        if "start" in scripts:
            plans["run"].append([runner, "run", "start"])
        elif "dev" in scripts:
            plans["run"].append([runner, "run", "dev"])

    python_markers = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile")
    if any(os.path.isfile(os.path.join(root, f)) for f in python_markers):
        python = python_exe(root)
        if has_module(python, "pytest"):
            plans["test"].append([python, "-m", "pytest", "-q"])
        elif os.path.isdir(os.path.join(root, "tests")) or os.path.isdir(os.path.join(root, "test")):
            plans["test"].append([python, "-m", "unittest", "discover"])
        for entry in ("main.py", "app.py"):
            if os.path.isfile(os.path.join(root, entry)):
                plans["run"].append([python, entry])
                break

    if os.path.isfile(os.path.join(root, "go.mod")):
        plans["test"].append(["go", "test", "./..."])
        plans["build"].append(["go", "build", "./..."])
        if os.path.isfile(os.path.join(root, "main.go")):
            plans["run"].append(["go", "run", "."])

    if os.path.isfile(os.path.join(root, "Cargo.toml")):
        plans["test"].append(["cargo", "test"])
        plans["build"].append(["cargo", "build"])
        plans["run"].append(["cargo", "run"])

    if os.path.isfile(os.path.join(root, "Makefile")):
        targets = make_targets(root)
        for what in ("test", "build", "run"):
            if what in targets:
                plans[what].append(["make", what])

    return plans


def with_race(cmd):
    if len(cmd) >= 2 and cmd[0] == "go" and cmd[1] in ("test", "build", "run"):
        return [cmd[0], cmd[1], "-race"] + cmd[2:]
    return None


def with_extra(cmd, extra):
    # npm-style runners need a -- before args meant for the script
    if not extra:
        return cmd
    if cmd[0] in ("npm", "pnpm", "yarn", "bun") and len(cmd) >= 2 and cmd[1] == "run":
        return cmd + ["--"] + extra
    return cmd + extra


def resolve(cmd):
    exe = cmd[0] if os.path.isabs(cmd[0]) else shutil.which(cmd[0])
    if exe is None:
        return None
    return [exe] + cmd[1:]


def kill_tree(proc):
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    except (OSError, ProcessLookupError):
        pass  # group already exited
    proc.kill()


def show(output, max_lines, log_path):
    lines = output.rstrip("\n").splitlines()
    if log_path:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(output)
    if max_lines and len(lines) > max_lines:
        hidden = len(lines) - max_lines
        where = f"; full output in {log_path}" if log_path else "; raise --max-lines or use --log"
        print(f"... {hidden} earlier line(s) omitted{where} ...")
        lines = lines[-max_lines:]
    if lines:
        print("\n".join(lines))


def execute(cmd, root, timeout, max_lines=400, log_path=None):
    # returns (exit code, or None when skipped; seconds)
    resolved = resolve(cmd)
    if resolved is None:
        print(f"skip: {cmd[0]!r} not found on PATH")
        return None, 0.0
    print(f"$ {' '.join(cmd)}")
    sys.stdout.flush()
    kwargs = {"start_new_session": True} if os.name == "posix" else {
        "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    }
    start = time.monotonic()
    proc = subprocess.Popen(
        resolved, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, text=True, errors="replace", **kwargs,
    )
    try:
        output, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        output, _ = proc.communicate()
        show(output or "", max_lines, log_path)
        elapsed = time.monotonic() - start
        print(f"timeout after {timeout}s (process tree killed)")
        return 124, elapsed
    elapsed = time.monotonic() - start
    show(output or "", max_lines, log_path)
    print(f"exit code: {code}  ({elapsed:.1f}s)")
    return code, elapsed


def split_extra(argv):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Detect and run a project's commands for DeepTrace.",
        epilog="Arguments after -- are passed to every detected command, e.g. -- -k test_login",
    )
    parser.add_argument("path", nargs="?", default=".", help="project root")
    parser.add_argument("--what", choices=["test", "build", "run"], default="test")
    parser.add_argument("--timeout", type=int, default=300, help="per-command timeout in seconds")
    parser.add_argument("--race", action="store_true", help="enable the data-race detector where the stack supports it")
    parser.add_argument("--dry-run", action="store_true", help="print detected commands without running")
    parser.add_argument("--max-lines", type=int, default=400, help="show only the last N output lines (0 = all)")
    parser.add_argument("--log", help="also append full output to this file")
    own, extra = split_extra(argv)
    args = parser.parse_args(own)

    root = os.path.realpath(args.path)
    if not os.path.isdir(root):
        print(f"error: {args.path} is not a directory", file=sys.stderr)
        return 2
    commands = detect(root)[args.what]

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
            print("note: --race has no native flag for this stack. Go uses -race; for Rust use miri or loom; "
                  "for Python use trace.py (it tags events by thread); for services, hit them concurrently "
                  "with trace-http.py --repeat N --concurrency C.")

    commands = [with_extra(cmd, extra) for cmd in commands]

    if args.dry_run:
        print(f"detected {args.what} commands:")
        for cmd in commands:
            print(f"  {' '.join(cmd)}")
        return 0

    results = []
    for cmd in commands:
        code, elapsed = execute(cmd, root, args.timeout, args.max_lines, args.log)
        results.append((cmd, code, elapsed))

    if len(results) > 1:
        print("\nSUMMARY")
        for cmd, code, elapsed in results:
            status = "skipped" if code is None else f"exit {code}"
            print(f"  {status:<9} {elapsed:>6.1f}s  {' '.join(cmd)}")

    worst = 0
    for _, code, _ in results:
        if code:
            worst = code
    if all(code is None for _, code, _ in results):
        return 127
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
