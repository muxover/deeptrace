#!/usr/bin/env python3
import argparse
import sys

INSTALL = "pip install playwright && playwright install chromium"

# Framework-agnostic instrumentation, injected before any app script runs.
# A MutationObserver counts DOM churn per element (works for any UI); the React
# DevTools hook is patched to count commits when React happens to be present.
INIT_SCRIPT = r"""
(() => {
  window.__DT__ = { mutations: 0, nodes: {}, commits: 0, react: false };
  const bump = (key) => { window.__DT__.nodes[key] = (window.__DT__.nodes[key] || 0) + 1; };
  const describe = (node) => {
    if (!node || !node.nodeName) return "node";
    let d = node.nodeName.toLowerCase();
    if (node.id) d += "#" + node.id;
    else if (typeof node.className === "string" && node.className.trim()) {
      d += "." + node.className.trim().split(/\s+/).slice(0, 2).join(".");
    }
    return d;
  };
  const observer = new MutationObserver((records) => {
    for (const r of records) { window.__DT__.mutations++; bump(describe(r.target)); }
  });
  const start = () => observer.observe(document.documentElement, {
    subtree: true, childList: true, attributes: true, characterData: true,
  });
  if (document.documentElement) start();
  else document.addEventListener("DOMContentLoaded", start);

  const hook = window.__REACT_DEVTOOLS_GLOBAL_HOOK__ || {};
  const origInject = hook.inject;
  Object.assign(hook, {
    supportsFiber: true,
    renderers: hook.renderers || new Map(),
    inject(r) { window.__DT__.react = true; return origInject ? origInject.call(hook, r) : 1; },
    onCommitFiberRoot() { window.__DT__.commits++; },
    onCommitFiberUnmount() {},
    onPostCommitFiberRoot() {},
  });
  Object.defineProperty(window, "__REACT_DEVTOOLS_GLOBAL_HOOK__", { value: hook, configurable: true });
})();
"""


def report(nav, console, errors, network, failures, activity, output):
    out = ["UI RUNTIME TRACE", "=" * 16, "", f"NAVIGATION: {nav}", ""]

    out.append("CONSOLE")
    loud = [(t, m) for t, m in console if t in ("error", "warning")]
    if loud:
        for level, message in loud[:40]:
            out.append(f"  [{level}] {message}")
    quiet = len(console) - len(loud)
    out.append(f"  ({len(loud)} warning/error, {quiet} info/log)" if console else "  (none)")
    out.append("")

    out.append("PAGE ERRORS")
    out.extend([f"  {e}" for e in errors[:20]] or ["  (none)"])
    out.append("")

    out.append("NETWORK")
    if network:
        for method, status, url, ms in network[:50]:
            timing = f"{ms:.0f} ms" if ms is not None else "  -  "
            out.append(f"  {str(status or '---'):>3} {method:<6} {timing:>8}  {url}")
        slow = max((r for r in network if r[3] is not None), key=lambda r: r[3], default=None)
        if slow:
            out.append(f"  slowest: {slow[3]:.0f} ms  {slow[2]}")
    else:
        out.append("  (no requests captured)")
    if failures:
        out.append("  failed:")
        out.extend([f"    {m} {u}  ({f})" for m, u, f in failures[:20]])
    out.append("")

    out.append("DOM ACTIVITY")
    if not activity:
        activity = {"mutations": 0, "nodes": {}, "commits": 0, "react": False}
        out.append("  (instrumentation unavailable: the page did not load)")
    out.append(f"  {activity['mutations']} mutations during observation")
    hot = sorted(activity["nodes"].items(), key=lambda kv: kv[1], reverse=True)
    out.extend([f"  {n:>5}  {sel}" for sel, n in hot[:15]])
    if activity["react"]:
        out.append(f"  React commits: {activity['commits']}")
    out.append("")

    text = "\n".join(out).rstrip()
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"trace written to {output}")
    else:
        print(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trace a running UI for DeepTrace via a real browser.")
    parser.add_argument("url", help="page URL to load, e.g. http://localhost:3000")
    parser.add_argument("--click", action="append", help="CSS selector to click after load (repeatable)")
    parser.add_argument("--duration", type=int, default=3000, help="ms to observe after load and clicks")
    parser.add_argument("--timeout", type=int, default=30, help="navigation timeout in seconds")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--output", help="write the trace to a file instead of stdout")
    parser.add_argument("--screenshot", help="save a full-page screenshot to this path after observation")
    args = parser.parse_args(argv)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is required to trace a running UI in a real browser.")
        print(f"install: {INSTALL}")
        print("It drives the DOM so renders, async races, and network waterfalls come from a real run.")
        return 1

    console, errors, network, failures = [], [], [], []

    def on_finished(request):
        # Playwright reports responseEnd already relative to startTime (startTime itself is epoch ms).
        timing = request.timing or {}
        end = timing.get("responseEnd", -1)
        ms = end if end is not None and end >= 0 else None
        resp = request.response()
        network.append((request.method, resp.status if resp else None, request.url, ms))

    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=not args.headed)
            except Exception as exc:
                if "playwright install" in str(exc).lower() or "executable doesn" in str(exc).lower():
                    print("Chromium is not installed for Playwright.")
                    print("install: playwright install chromium")
                    return 1
                raise
            page = browser.new_page()
            page.add_init_script(INIT_SCRIPT)
            def on_console(msg):
                loc = msg.location or {}
                where = f"  ({loc.get('url')}:{loc.get('lineNumber', 0) + 1})" if loc.get("url") else ""
                console.append((msg.type, f"{msg.text}{where}"))

            def on_pageerror(err):
                stack = getattr(err, "stack", None) or str(err)
                errors.append("\n    ".join(stack.strip().splitlines()[:4]))

            page.on("console", on_console)
            page.on("pageerror", on_pageerror)
            page.on("requestfinished", on_finished)
            page.on("requestfailed", lambda r: failures.append((r.method, r.url, r.failure)))

            nav = "ok"
            try:
                resp = page.goto(args.url, wait_until="load", timeout=args.timeout * 1000)
                nav = f"{args.url} -> {resp.status if resp else 'no response'}"
            except Exception as exc:
                nav = f"{args.url} -> navigation error: {exc}"

            for selector in args.click or []:
                try:
                    page.click(selector, timeout=5000)
                    page.wait_for_timeout(300)
                except Exception as exc:
                    errors.append(f"click {selector!r} failed: {exc}")

            page.wait_for_timeout(args.duration)
            try:
                activity = page.evaluate("() => window.__DT__ || null")
            except Exception:
                activity = None
            if args.screenshot:
                try:
                    page.screenshot(path=args.screenshot, full_page=True)
                except Exception as exc:
                    errors.append(f"screenshot failed: {exc}")
            browser.close()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report(nav, console, errors, network, failures, activity, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
