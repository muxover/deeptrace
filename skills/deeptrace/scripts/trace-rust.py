#!/usr/bin/env python3
import argparse
import html
import os
import re
import shutil
import subprocess
import sys

INSTALL = "cargo install flamegraph"
TITLE_RE = re.compile(r"<title>(.*?) \(([\d,]+) samples?, ([\d.]+)%\)</title>")


def split_program_args(argv):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def passthrough(prog_args):
    if prog_args and prog_args[0] != "--":
        return ["--"] + prog_args
    return prog_args


def run(cmd, root, timeout, env=None):
    print("$ " + " ".join(cmd))
    sys.stdout.flush()
    try:
        proc = subprocess.run(cmd, cwd=root, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        print(f"timeout after {timeout}s")
        return 124
    print(f"exit code: {proc.returncode}")
    return proc.returncode


def hot_frames(svg_path, top):
    # a frame appears once per stack it sits in; sum those for its inclusive total
    try:
        with open(svg_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return []
    totals = {}
    for name, samples, _ in TITLE_RE.findall(text):
        name = html.unescape(name)
        totals[name] = totals.get(name, 0) + int(samples.replace(",", ""))
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:top]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Profile/trace a Rust program for DeepTrace.",
        epilog="Pass program arguments after --, e.g. trace-rust.py . --bin app -- --port 8080",
    )
    parser.add_argument("path", nargs="?", default=".", help="cargo project root")
    parser.add_argument("--bin", help="binary target name (cargo --bin)")
    parser.add_argument("--unit-test", action="store_true", help="profile/run the unit tests instead of a binary")
    parser.add_argument("--output", default=os.path.join("target", "deeptrace-flamegraph.svg"),
                        help="flamegraph output path, relative to the project root")
    parser.add_argument("--top", type=int, default=25, help="hot frames to list from the flamegraph")
    parser.add_argument("--timeout", type=int, default=600, help="timeout in seconds")
    own, prog_args = split_program_args(argv)
    args = parser.parse_args(own)

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
        cmd += passthrough(prog_args)
        code = run(cmd, root, args.timeout)
        svg = os.path.join(root, args.output)
        if code == 0 and os.path.isfile(svg):
            print(f"flamegraph (sampled call stacks) written to {svg}")
            frames = hot_frames(svg, args.top)
            if frames:
                print("\nHOT FRAMES (inclusive samples)")
                for name, samples in frames:
                    print(f"  {samples:>8}  {name}")
            return 0
        print("cargo flamegraph failed (on Linux it needs 'perf' and permission to use it).")
        print("Falling back to a backtrace-instrumented run.")
    else:
        print("cargo-flamegraph not found; install it for sampled call-stack profiles:")
        print(f"install: {INSTALL}")
        print("Falling back to a backtrace-instrumented run (captures panics and the executed path).")

    env = dict(os.environ, RUST_BACKTRACE="full")
    if args.unit_test:
        cmd = ["cargo", "test"]
        if args.bin:
            cmd += ["--bin", args.bin]
    else:
        cmd = ["cargo", "run"]
        if args.bin:
            cmd += ["--bin", args.bin]
    cmd += passthrough(prog_args)
    return run(cmd, root, args.timeout, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
