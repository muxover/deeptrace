#!/usr/bin/env python3
import argparse
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

MAX_BODY = 10 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_headers(items):
    headers = {}
    for item in items or []:
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def kind(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def shape(text, ctype):
    if "json" not in (ctype or "").lower():
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if isinstance(data, dict):
        fields = ", ".join(f"{k}: {kind(v)}" for k, v in list(data.items())[:20])
        return "{ " + fields + (", ..." if len(data) > 20 else "") + " }"
    if isinstance(data, list):
        return f"list[{len(data)}] of {kind(data[0]) if data else 'empty'}"
    return kind(data)


def do_request(method, url, headers, body, timeout, insecure=False):
    handlers = [NoRedirect]
    if insecure:
        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, data=body, method=method.upper(), headers=headers or {})
    start = time.perf_counter()
    try:
        resp = opener.open(req, timeout=timeout)
        status, reason, hdrs, content = resp.status, resp.reason, resp.headers, resp.read(MAX_BODY)
    except urllib.error.HTTPError as exc:
        status, reason, hdrs, content = exc.code, exc.reason, exc.headers, exc.read(MAX_BODY)
    except urllib.error.URLError as exc:
        return {"method": method.upper(), "url": url, "error": str(exc.reason)}
    except OSError as exc:  # timeouts, resets
        return {"method": method.upper(), "url": url, "error": str(exc)}
    elapsed = (time.perf_counter() - start) * 1000
    ctype = hdrs.get("Content-Type", "")
    return {
        "method": method.upper(),
        "url": url,
        "status": status,
        "reason": reason,
        "elapsed": elapsed,
        "ctype": ctype,
        "bytes": len(content),
        "location": hdrs.get("Location"),
        "shape": shape(content.decode("utf-8", "replace"), ctype),
        "digest": hashlib.sha1(content).hexdigest()[:10],
        "preview": content[:300].decode("utf-8", "replace"),
        "headers": dict(hdrs.items()),
    }


def format_result(result, show_headers=False):
    if "error" in result:
        return [f"{result['method']} {result['url']}", f"  failed: {result['error']}"]
    lines = [
        f"{result['method']} {result['url']}",
        f"  -> {result['status']} {result['reason']}  ({result['elapsed']:.0f} ms, {result['bytes']} bytes)",
    ]
    if result["ctype"]:
        lines.append(f"  content-type: {result['ctype']}")
    if result["location"]:
        lines.append(f"  location: {result['location']}")
    if result["shape"]:
        lines.append(f"  body: {result['shape']}")
    if show_headers:
        lines.extend(f"  < {k}: {v}" for k, v in result["headers"].items())
    if result["status"] >= 400 and result["preview"].strip():
        lines.append(f"  error body: {result['preview'].strip()[:300]}")
    return lines


def percentile(values, pct):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def burst(request, repeat, concurrency, timeout, insecure):
    method, url, headers, body = request
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        results = list(pool.map(lambda _: do_request(method, url, headers, body, timeout, insecure), range(repeat)))
    ok = [r for r in results if "error" not in r]
    lines = [f"{method.upper()} {url}  x{repeat} (concurrency {concurrency})"]
    statuses = Counter(r["status"] for r in ok)
    lines.append("  statuses: " + ", ".join(f"{s} x{n}" for s, n in sorted(statuses.items())))
    errors = Counter(r["error"] for r in results if "error" in r)
    for err, n in errors.items():
        lines.append(f"  failed x{n}: {err}")
    if ok:
        times = [r["elapsed"] for r in ok]
        lines.append(f"  latency ms: min {min(times):.0f}  p50 {percentile(times, 50):.0f}  "
                     f"p95 {percentile(times, 95):.0f}  max {max(times):.0f}")
        bodies = Counter(r["digest"] for r in ok)
        verdict = "all identical" if len(bodies) == 1 else "responses diverged under repetition"
        lines.append(f"  distinct response bodies: {len(bodies)} ({verdict})")
        if method.upper() not in ("GET", "HEAD", "OPTIONS"):
            lines.append("  note: for a state-changing call, identical results can mean lost updates and different "
                         "ones can mean duplicate side effects. Read the resulting state before concluding.")
    return lines, [r.get("status") for r in results]


def load_sequence(path):
    with open(path, encoding="utf-8") as fh:
        items = json.load(fh)
    requests = []
    for item in items:
        body = None
        if "json" in item:
            body = json.dumps(item["json"]).encode("utf-8")
            item.setdefault("headers", {})["Content-Type"] = "application/json"
        elif "body" in item:
            body = item["body"].encode("utf-8")
        requests.append((item.get("method", "GET"), item["url"], item.get("headers", {}), body))
    return requests


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture real HTTP request/response pairs for DeepTrace.")
    parser.add_argument("method", nargs="?", help="HTTP method (GET, POST, ...)")
    parser.add_argument("url", nargs="?", help="request URL")
    parser.add_argument("--header", action="append", help="request header 'Key: Value' (repeatable)")
    parser.add_argument("--data", help="raw request body")
    parser.add_argument("--json", dest="json_body", help="JSON request body (sets content-type)")
    parser.add_argument("--requests", help="JSON file with a list of requests to replay in order")
    parser.add_argument("--timeout", type=int, default=30, help="per-request timeout in seconds")
    parser.add_argument("--output", help="write the report to a file instead of stdout")
    parser.add_argument("--repeat", type=int, default=1, help="send each request N times (idempotency/race checks)")
    parser.add_argument("--concurrency", type=int, default=1, help="with --repeat, how many requests in flight at once")
    parser.add_argument("--show-headers", action="store_true", help="print response headers")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification (local self-signed certs)")
    args = parser.parse_args(argv)

    if args.requests:
        requests = load_sequence(args.requests)
    elif args.method and args.url:
        headers = parse_headers(args.header)
        body = None
        if args.json_body is not None:
            body = args.json_body.encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif args.data is not None:
            body = args.data.encode("utf-8")
        requests = [(args.method, args.url, headers, body)]
    else:
        parser.error("provide METHOD and URL, or --requests FILE")

    out = ["HTTP CAPTURE", "=" * 12, ""]
    statuses = []
    for method, url, headers, body in requests:
        if args.repeat > 1:
            lines, codes = burst((method, url, headers, body), args.repeat, args.concurrency, args.timeout,
                                 args.insecure)
            out.extend(lines)
            statuses.extend(codes)
        else:
            result = do_request(method, url, headers, body, args.timeout, args.insecure)
            out.extend(format_result(result, args.show_headers))
            statuses.append(result.get("status"))
        out.append("")

    ok = sum(1 for s in statuses if s and 200 <= s < 400)
    dist = ", ".join(f"{s if s else 'failed'} x{n}" for s, n in Counter(statuses).most_common())
    out.append(f"SUMMARY: {len(statuses)} request(s), {ok} under 400 ({dist})")

    text = "\n".join(out)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"capture written to {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
