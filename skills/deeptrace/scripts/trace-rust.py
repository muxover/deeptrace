#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys

INSTALL = "cargo install flamegraph"


def passthrough(prog_args):
    if prog_args and prog_args[0] != "--":
        return ["--"] + prog_args
    return prog_args


def run(cmd, root, timeout, env=None):
    print("$ " + " ".join(cmd))
    try:
        proc = subprocess.run(cmd, cwd=root, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        print(f"timeout after {timeout}s")
        return 124
    return proc.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description="Profile/trace a Rust program for DeepTrace.")
    parser.add_argument("path", nargs="?", default=".", help="cargo project root")
    parser.add_argument("--bin", help="binary target name (cargo --bin)")
    parser.add_argument("--unit-test", action="store_true", help="profile the unit-test binary")
    parser.add_argument("--output", default="flamegraph.svg", help="flamegraph output path")
    parser.add_argument("--timeout", type=int, default=600, help="timeout in seconds")
    parser.add_argument("prog_args", nargs=argparse.REMAINDER, help="args after -- passed to the program")
    args = parser.parse_args(argv)

    root = os.path.realpath(args.path)
    if shutil.which("cargo") is None:
        print("error: 'cargo' not found on PATH", file=sys.stderr)
        return 2

    if shutil.which("cargo-flamegraph"):
        cmd = ["cargo", "flamegraph", "-o", args.output]
        if args.bin:
            cmd += ["--bin", args.bin]
        if args.unit_test:
            cmd.append("--unit-test")
        cmd += passthrough(args.prog_args)
        code = run(cmd, root, args.timeout)
        if code == 0:
            print(f"flamegraph (sampled call stacks) written to {args.output}")
        return code

    print("cargo-flamegraph not found; install it for sampled call-stack profiles:")
    print(f"install: {INSTALL}")
    print("Falling back to a backtrace-instrumented run (captures panics and the executed path).")
    env = dict(os.environ, RUST_BACKTRACE="full")
    cmd = ["cargo", "run"]
    if args.bin:
        cmd += ["--bin", args.bin]
    cmd += passthrough(args.prog_args)
    return run(cmd, root, args.timeout, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
