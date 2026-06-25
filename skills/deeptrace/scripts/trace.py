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


def build_tracer(root, include_lines, max_depth, show_args, max_events, events, exceptions, calls):
    depths = {}
    main_ident = threading.get_ident()
    state = {"truncated": False}

    def label():
        if threading.get_ident() == main_ident:
            return ""
        return f"[{threading.current_thread().name}] "

    def in_scope(filename):
        if not filename or filename.startswith("<"):
            return False
        try:
            return os.path.realpath(filename).startswith(root)
        except OSError:
            return False

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
                    names = frame.f_code.co_varnames[: frame.f_code.co_argcount]
                    argpart = "(" + ", ".join(f"{n}={short(frame.f_locals.get(n))}" for n in names) + ")"
                record(f"{label()}{'  ' * depth}-> {rel}:{frame.f_lineno} {name}{argpart}")
                calls[name] += 1
            depths[ident] = depth + 1
            return tracer

        if event == "return":
            depths[ident] = max(0, depths.get(ident, 0) - 1)
            return tracer

        if event == "line" and include_lines:
            depth = depths.get(ident, 0)
            if max_depth is None or depth <= max_depth:
                record(f"{label()}{'  ' * depth}   {rel}:{frame.f_lineno}")
            return tracer

        if event == "exception":
            exc_type, exc_value, _ = arg
            message = str(exc_value)
            if len(message) > 80:
                message = message[:80] + "..."
            exceptions.append(f"{label()}{rel}:{frame.f_lineno}  {exc_type.__name__}: {message}")
            return tracer

        return tracer

    return tracer, state


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trace runtime execution of a Python script for DeepTrace.")
    parser.add_argument("target", help="python file to execute and trace")
    parser.add_argument("target_args", nargs=argparse.REMAINDER, help="arguments passed to the target")
    parser.add_argument("--root", help="project root scope (default: target's directory)")
    parser.add_argument("--lines", action="store_true", help="record line events, not just calls")
    parser.add_argument("--args", action="store_true", help="record argument values at each call")
    parser.add_argument("--max-depth", type=int, default=None, help="limit recorded call depth")
    parser.add_argument("--max-events", type=int, default=200000, help="cap recorded events to bound memory")
    parser.add_argument("--output", help="write the trace to a file instead of stdout")
    args = parser.parse_args(argv)

    target = os.path.realpath(args.target)
    if not os.path.isfile(target):
        print(f"error: {args.target} not found", file=sys.stderr)
        return 2

    root = os.path.realpath(args.root) if args.root else os.path.dirname(target)
    events, exceptions, calls = [], [], Counter()
    tracer, state = build_tracer(
        root, args.lines, args.max_depth, args.args, args.max_events, events, exceptions, calls
    )

    sys.argv = [target] + args.target_args
    sys.path.insert(0, os.path.dirname(target))
    failure = None

    threading.settrace(tracer)
    sys.settrace(tracer)
    try:
        runpy.run_path(target, run_name="__main__")
    except SystemExit:
        pass
    except BaseException as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        sys.settrace(None)
        threading.settrace(None)

    lines = ["EXECUTION TRACE", "=" * 14, ""]
    lines.extend(events if events else ["(no in-scope calls recorded)"])
    if state["truncated"]:
        lines.append(f"... trace truncated at {args.max_events} events (raise --max-events)")
    lines.append("")
    lines.append("EXCEPTIONS")
    lines.extend(exceptions if exceptions else ["(none)"])
    lines.append("")
    lines.append("CALL COUNTS")
    for name, n in calls.most_common(20):
        lines.append(f"  {n:>5}  {name}")
    if failure:
        lines.append("")
        lines.append(f"UNCAUGHT: {failure}")

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
