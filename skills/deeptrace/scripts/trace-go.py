#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

INSTALL = "go install github.com/go-delve/delve/cmd/dlv@latest"
CALL_RE = re.compile(r"^> goroutine\((\d+)\): (?:\[\d+\] )?([^\s(]+)\(")
RET_RE = re.compile(r"^>> goroutine\((\d+)\): (?:\[\d+\] )?(\S+) => ")


def split_program_args(argv):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def find_module(start):
    here = os.path.realpath(start if os.path.isdir(start) else os.path.dirname(start) or ".")
    while True:
        gomod = os.path.join(here, "go.mod")
        if os.path.isfile(gomod):
            try:
                with open(gomod, encoding="utf-8") as fh:
                    for line in fh:
                        parts = line.split()
                        if len(parts) >= 2 and parts[0] == "module":
                            return parts[1].strip('"')
            except OSError:
                return None
            return None
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def default_regex(target):
    # tracing everything ('.') hooks runtime entry stubs and breaks the run
    module = find_module(target)
    parts = [r"main\."]
    if module:
        parts.append(re.escape(module) + r"[./]")
    return "^(" + "|".join(parts) + ")"


def summarize(lines, top):
    calls, goroutines = Counter(), set()
    for line in lines:
        match = CALL_RE.match(line)
        if match:
            goroutines.add(match.group(1))
            calls[match.group(2)] += 1
    out = ["", "CALL COUNTS"]
    out.extend(f"  {n:>6}  {name}" for name, n in calls.most_common(top))
    if not calls:
        out.append("  (no traced calls; widen --func or check the program ran)")
    out.append(f"goroutines seen: {len(goroutines)}")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Trace Go function calls for DeepTrace via Delve.",
        epilog="Program arguments go after --, e.g. trace-go.py ./cmd/app -- --port 8080",
    )
    parser.add_argument("target", nargs="?", default=".", help="package or directory to trace, e.g. ./cmd/app")
    parser.add_argument("--func", help="regex of function names to trace (default: this module's code)")
    parser.add_argument("--test", action="store_true", help="trace 'go test' instead of a binary")
    parser.add_argument("--stack", type=int, help="show a stack trace of this depth at each traced call")
    parser.add_argument("--max-lines", type=int, default=300, help="trace lines to print (0 = all)")
    parser.add_argument("--output", help="also write the full raw trace to this file")
    parser.add_argument("--top", type=int, default=25, help="functions to list in the call counts")
    parser.add_argument("--timeout", type=int, default=300, help="timeout in seconds")
    own, prog_args = split_program_args(argv)
    args = parser.parse_args(own)

    if shutil.which("go") is None:
        print("error: 'go' not found on PATH", file=sys.stderr)
        return 2

    dlv = shutil.which("dlv")
    if dlv is None:
        print("Delve (dlv) is required for Go function tracing.")
        print(f"install: {INSTALL}")
        print("Delve drives function entry/exit tracing on real Go programs and tests.")
        return 1

    regex = args.func or default_regex(args.target)
    cmd = [dlv, "trace"]
    if args.test:
        cmd.append("--test")
    if args.stack:
        cmd += ["--stack", str(args.stack)]
    cmd += [args.target, regex]
    if prog_args:
        cmd += ["--"] + prog_args

    print("$ " + " ".join(cmd))
    sys.stdout.flush()
    try:
        proc = subprocess.run(cmd, timeout=args.timeout, capture_output=True, text=True, errors="replace")
        output, code = (proc.stdout or "") + (proc.stderr or ""), proc.returncode
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        partial += exc.stderr or b""
        output = partial.decode("utf-8", "replace") if isinstance(partial, bytes) else partial
        code = 124
        output += f"\ntimeout after {args.timeout}s"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"full trace written to {args.output}")

    lines = output.splitlines()
    shown = lines if not args.max_lines or len(lines) <= args.max_lines else lines[: args.max_lines]
    print("\n".join(shown))
    if len(shown) < len(lines):
        print(f"... {len(lines) - len(shown)} more line(s); narrow --func or use --output")
    print("\n".join(summarize(lines, args.top)))
    print(f"exit code: {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
