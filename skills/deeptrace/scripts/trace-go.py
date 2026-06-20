#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys

INSTALL = "go install github.com/go-delve/delve/cmd/dlv@latest"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trace Go function calls for DeepTrace via Delve.")
    parser.add_argument("target", help="package or directory to trace, e.g. ./cmd/app")
    parser.add_argument("--func", default=".", help="regex of function names to trace")
    parser.add_argument("--test", action="store_true", help="trace 'go test' instead of a binary")
    parser.add_argument("--timeout", type=int, default=300, help="timeout in seconds")
    args = parser.parse_args(argv)

    if shutil.which("go") is None:
        print("error: 'go' not found on PATH", file=sys.stderr)
        return 2

    dlv = shutil.which("dlv")
    if dlv is None:
        print("Delve (dlv) is required for Go function tracing.")
        print(f"install: {INSTALL}")
        print("Delve drives function entry/exit tracing on real Go programs and tests.")
        return 1

    cmd = [dlv, "trace"]
    if args.test:
        cmd.append("--test")
    cmd += [args.target, args.func]

    print("$ " + " ".join(cmd))
    try:
        proc = subprocess.run(cmd, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(f"timeout after {args.timeout}s")
        return 124
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
