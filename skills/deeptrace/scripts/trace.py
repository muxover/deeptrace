#!/usr/bin/env python3
import argparse
import os
import runpy
import sys
import threading
from collections import Counter


def short(value, limit=40):
    try:
        text = repr(value)
    except Exception:
        return "<unrepr>"
    return text if len(text) <= limit else text[:limit] + "..."


def within(path, root):
    # commonpath, not startswith: /proj must not match /proj2
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def build_tracer(root, include_lines, max_depth, show_args, max_events, events, exceptions, calls,
                 show_returns=False, exclude=()):
    depths = {}
    main_ident = threading.get_ident()
    state = {"truncated": False}
    scope_cache = {}
    inflight = {}  # thread ident -> {"exc", "frame", "entry"} for an exception still unwinding

    def label():
        if threading.get_ident() == main_ident:
            return ""
        return f"[{threading.current_thread().name}] "

    def in_scope(filename):
        cached = scope_cache.get(filename)
        if cached is not None:
            return cached
        ok = False
        if filename and not filename.startswith("<"):
            try:
                real = os.path.realpath(filename)
                ok = within(real, root) and not any(within(real, ex) for ex in exclude)
            except OSError:
                ok = False
        scope_cache[filename] = ok
        return ok

    def record(text):
        if len(events) >= max_events:
            state["truncated"] = True
            return
        events.append(text)

    def tracer(frame, event, arg):
        filename = frame.f_code.co_filename
        if not in_scope(filename):
            return None
        ident = threading.get_ident()
        rel = os.path.relpath(filename, root)

        if event == "call":
            depth = depths.get(ident, 0)
            if max_depth is None or depth <= max_depth:
                name = frame.f_code.co_name
                argpart = ""
                if show_args:
                    code = frame.f_code
                    count = code.co_argcount + code.co_kwonlyargcount
                    names = code.co_varnames[:count]
                    argpart = "(" + ", ".join(f"{n}={short(frame.f_locals.get(n))}" for n in names) + ")"
                record(f"{label()}{'  ' * depth}-> {rel}:{frame.f_code.co_firstlineno} {name}{argpart}")
                calls[f"{name} ({rel})"] += 1
            depths[ident] = depth + 1
            return tracer

        if event == "return":
            depth = max(0, depths.get(ident, 0) - 1)
            depths[ident] = depth
            flight = inflight.get(ident)
            unwinding = flight is not None and flight["frame"] is frame
            if show_returns and not unwinding and (max_depth is None or depth <= max_depth):
                record(f"{label()}{'  ' * depth}<- {frame.f_code.co_name} = {short(arg)}")
            return tracer

        if event == "line":
            flight = inflight.get(ident)
            if flight is not None and flight["frame"] is frame:
                # execution resumed in the frame that saw it, so it was caught here
                flight["entry"]["status"] = f"caught at {rel}:{frame.f_lineno} in {frame.f_code.co_name}"
                del inflight[ident]
            if include_lines:
                depth = depths.get(ident, 0)
                if max_depth is None or depth <= max_depth:
                    record(f"{label()}{'  ' * depth}   {rel}:{frame.f_lineno}")
            return tracer

        if event == "exception":
            exc_type, exc_value, _ = arg
            flight = inflight.get(ident)
            if flight is not None and flight["exc"] is exc_value:
                flight["frame"] = frame  # same exception unwinding into a caller
                return tracer
            message = str(exc_value)
            if len(message) > 80:
                message = message[:80] + "..."
            entry = {
                "where": f"{label()}{rel}:{frame.f_lineno} in {frame.f_code.co_name}",
                "what": f"{exc_type.__name__}: {message}",
                "status": "propagated out of project code",
                "exc": exc_value,
            }
            exceptions.append(entry)
            inflight[ident] = {"exc": exc_value, "frame": frame, "entry": entry}
            return tracer

        return tracer

    return tracer, state


def render_exception(entry):
    if isinstance(entry, str):
        return entry
    return f"{entry['where']}  {entry['what']}  [{entry['status']}]"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Trace runtime execution of a Python program for DeepTrace.",
        epilog="DeepTrace flags go before the target; everything after the target is passed to it.",
    )
    parser.add_argument("target", help="python file to execute and trace (or a module name with -m)")
    parser.add_argument("target_args", nargs=argparse.REMAINDER, help="arguments passed to the target")
    parser.add_argument("-m", "--module", action="store_true", help="treat target as a module, like python -m")
    parser.add_argument("--root", help="project root scope (default: target's directory, or cwd with -m)")
    parser.add_argument("--exclude", action="append", default=[], help="directory to leave out of scope (repeatable)")
    parser.add_argument("--lines", action="store_true", help="record line events, not just calls")
    parser.add_argument("--args", action="store_true", help="record argument values at each call")
    parser.add_argument("--returns", action="store_true", help="record return values")
    parser.add_argument("--max-depth", type=int, default=None, help="limit recorded call depth")
    parser.add_argument("--max-events", type=int, default=200000, help="cap recorded events to bound memory")
    parser.add_argument("--output", help="write the trace to a file instead of stdout")
    args = parser.parse_args(argv)

    if args.module:
        target = args.target
        root = os.path.realpath(args.root or os.getcwd())
        run_dir = os.getcwd()
    else:
        target = os.path.realpath(args.target)
        if not os.path.isfile(target):
            print(f"error: {args.target} not found", file=sys.stderr)
            return 2
        root = os.path.realpath(args.root) if args.root else os.path.dirname(target)
        run_dir = os.path.dirname(target)

    exclude = [os.path.realpath(p) for p in args.exclude]
    here = os.path.dirname(os.path.realpath(__file__))
    exclude.append(here)  # never trace DeepTrace itself if it lives inside the project

    events, exceptions, calls = [], [], Counter()
    tracer, state = build_tracer(
        root, args.lines, args.max_depth, args.args, args.max_events, events, exceptions, calls,
        show_returns=args.returns, exclude=exclude,
    )

    saved_argv, saved_path = sys.argv[:], sys.path[:]
    sys.argv = [target] + args.target_args
    sys.path.insert(0, run_dir)
    failure, failure_exc, exit_code = None, None, 0

    threading.settrace(tracer)
    sys.settrace(tracer)
    try:
        if args.module:
            runpy.run_module(target, run_name="__main__", alter_sys=True)
        else:
            runpy.run_path(target, run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        exit_code = code if isinstance(code, int) else (0 if code is None else 1)
        failure_exc = exc
    except BaseException as exc:
        failure = f"{type(exc).__name__}: {exc}"
        failure_exc = exc
        exit_code = 1
    finally:
        sys.settrace(None)
        threading.settrace(None)
        sys.argv, sys.path[:] = saved_argv, saved_path

    for entry in exceptions:
        if entry["exc"] is failure_exc:
            entry["status"] = "exit" if isinstance(failure_exc, SystemExit) else "UNCAUGHT"

    lines = ["EXECUTION TRACE", "=" * 15, ""]
    lines.extend(events if events else ["(no in-scope calls recorded)"])
    if state["truncated"]:
        lines.append(f"... trace truncated at {args.max_events} events (raise --max-events)")
    lines.append("")
    lines.append("EXCEPTIONS (where raised, and what happened to it)")
    lines.extend([f"  {render_exception(e)}" for e in exceptions] or ["  (none)"])
    lines.append("")
    lines.append("CALL COUNTS")
    for name, n in calls.most_common(20):
        lines.append(f"  {n:>5}  {name}")
    lines.append("")
    if failure:
        lines.append(f"UNCAUGHT: {failure}")
    lines.append(f"EXIT CODE: {exit_code}")

    text = "\n".join(lines)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"trace written to {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
