# DeepTrace tools

A handful of small scripts that let the agent dig into a real project instead of guessing from a snippet. The Python tools need only the standard library (Python 3.9+); the UI tracer adds Playwright, the Go tracer Delve, and the Rust profiler `cargo flamegraph`; Node uses its own built-in profiler. Each one says exactly what to install when a dependency is missing.

The scripts live in this folder (`${CLAUDE_SKILL_DIR}/scripts` in Claude Code). Call them by that path and point them at the project; they do not need to be copied into it.

## recon.py

Builds a picture of the project before anything runs.

```bash
python recon.py /path/to/project
python recon.py /path/to/project --json
```

It reports the stacks it found from the manifests, the files and lines per language, the entry points, the ten largest source files, and every TODO, FIXME, HACK, XXX, or BUG marker with its location (whole words only, so `DEBUG` is not a hit). Entry points come from common file names, from manifests (`package.json` `main`/`bin`/start scripts, `pyproject.toml` console scripts, `Cargo.toml` `[[bin]]`), and from code that defines a real entry (`if __name__ == "__main__"`, Go `package main` + `func main`, Rust `fn main`). Minified bundles are skipped so they do not pose as hotspots.

## run.py

Works out how the project runs its tests, build, or app, runs that command, and keeps the output and exit code. Commands are looked up on PATH and run without a shell.

```bash
python run.py /path/to/project --what test
python run.py /path/to/project --what build
python run.py /path/to/project --dry-run
python run.py /path/to/project -- -k test_login        # args after -- go to the test command
```

It knows Node, Python, Go, Rust (cargo), and Make:

- Node uses the package manager the project declares (`packageManager` in `package.json`) or whose lockfile is present (pnpm, yarn, bun, npm).
- Python uses the project's own virtualenv (`.venv`, `venv`, `env`) when there is one, pytest when it is installed there, and `unittest discover` otherwise.
- Make targets are only used when the Makefile actually defines them.

Run `--dry-run` first to see the command. `--timeout` caps each one (300s by default) and kills the whole process tree when it fires, so nothing is left running. Output (stdout and stderr interleaved) is trimmed to the last `--max-lines` lines (400 by default), since the end is where failures are; `--log FILE` keeps the full output. With several commands you get a summary of exit codes and durations at the end.

Pass `--race` to turn on the data-race detector where the stack supports it. Go runs under `-race`. Other stacks have no native flag, so the runner says so and points at the alternatives: miri or loom for Rust, `trace.py` thread tags for Python, and concurrent requests with `trace-http.py --repeat N --concurrency C` for services.

This runs the project's code. Only run code you trust, and use `--dry-run` on a repo you do not know.

## trace.py

Runs a Python entry point under `sys.settrace` and records the call graph for the project, along with any exceptions raised on the way.

```bash
python trace.py --args app/main.py
python trace.py --lines --max-depth 6 app/main.py arg1 arg2
python trace.py --root /path/to/project --output trace.txt app/main.py
python trace.py --args --returns -m mypackage.cli serve   # like python -m
```

Put DeepTrace flags before the target; anything after the target is handed to the target as its own arguments. You get:

- An indented call trace (`-> file:line function(args)`, plus `<- function = value` with `--returns`).
- Every exception, with where it was raised and what happened to it: `caught at file:line in func`, `UNCAUGHT`, `exit`, or `propagated out of project code`. That separates handled errors from real crashes.
- Call counts per function and the program's exit code.

`--lines` adds line-level events, `--max-depth` cuts noise, and `--max-events` caps memory (200000 by default). `--root` sets the scope (the target's directory by default, or the working directory with `-m`), and `--exclude DIR` drops a directory from it. Threads the program spawns are traced too and tagged with the thread name, which is usually how races and ordering bugs show up.

## Node, JavaScript, and TypeScript

There is no bundled Node tracer; Node's built-in CPU profiler does the job and works in every case a wrapper can break: CommonJS and ES modules, top-level `await`, programs that end with `process.exit()`, and TypeScript through `tsx`.

```bash
node --cpu-prof --cpu-prof-dir=/tmp/prof app/server.js arg1
node --import tsx --cpu-prof --cpu-prof-dir=/tmp/prof src/index.ts
node --cpu-prof --cpu-prof-interval 100 --cpu-prof-dir=/tmp/prof app.js    # finer sampling (microseconds)
```

Each run writes a `.cpuprofile` file when the process exits. It is JSON: `nodes` is the sampled call tree, and each node has a `callFrame` (`functionName`, `url`, `lineNumber`, zero-based) and a `hitCount` (samples taken while that function itself was running). To find the hot path, keep the nodes whose `url` is inside the project, add up `hitCount` per function, and walk `children` to see who called what. The same file opens in Chrome DevTools (Performance panel) for a visual flame chart.

Sampling misses very short functions. When that matters, give the code path more work, or step through it with `node --inspect-brk`. A long-running server writes its profile only when it exits, so stop it with Ctrl+C (SIGINT) once the traffic you care about has run.

## trace-http.py

Fires real HTTP requests against a running service and records the request/response contract: status, timing, content type, body size, and the JSON shape of the response. Stdlib only, nothing to install. Redirects are reported, not followed, so you see the real status.

```bash
python trace-http.py GET http://localhost:8080/users/1
python trace-http.py POST http://localhost:8080/orders --json '{"item":"x"}' --header "Authorization: Bearer t"
python trace-http.py --requests calls.json
```

```bash
python trace-http.py POST http://localhost:8080/withdraw --json '{"amount":10}' --repeat 20 --concurrency 10
```

`--header` is repeatable (`'Key: Value'`), `--json` sends a JSON body and sets the content type, and `--data` sends a raw body. Error responses (4xx/5xx) show the start of their body, `--show-headers` prints the response headers, and `--insecure` accepts a local self-signed certificate.

For a sequence, `--requests` takes a JSON file holding a list of `{method, url, headers, json|body}` objects and replays them in order. That covers retry, duplicate-submission, and idempotency checks.

`--repeat N --concurrency C` fires each request N times with C in flight at once and summarizes the result: status counts, latency percentiles, and how many distinct response bodies came back. This is how you test races and idempotency on a live service. Be careful with what the summary means for a state-changing call. N identical results can mean lost updates, and different results can mean duplicate side effects, so read the resulting state before you conclude anything.

This sends real traffic to whatever URL you point it at.

## trace-ui.py

Loads a running UI in a real browser (Playwright + Chromium) and reports what actually happened: console warnings and errors, uncaught page errors, the network waterfall with status and timing, and DOM activity. DOM mutations are counted per element for any framework; React commit counts are added when React is present.

```bash
python trace-ui.py http://localhost:3000
python trace-ui.py http://localhost:3000 --click "#submit" --click ".load-more" --duration 4000
python trace-ui.py http://localhost:5173 --headed --output ui-trace.txt
```

`--click` is a CSS selector clicked after load (repeatable, in order), `--duration` is how long to observe afterward, `--headed` shows the window, and `--screenshot FILE` saves a full-page screenshot at the end so you can see the rendered state. Console messages carry their source location, and page errors carry the top of their stack. It needs Playwright (`pip install playwright && playwright install chromium`); when either the package or the browser is missing, the script says exactly what to install rather than failing silently. This drives a real browser against the URL you give it.

## trace-go.py

Uses Delve to trace function entry and exit in a real Go program or test.

```bash
python trace-go.py ./cmd/app
python trace-go.py ./cmd/app --func 'Handle.*' --stack 3
python trace-go.py ./internal/store --test
python trace-go.py ./cmd/app -- --port 8080     # program args after --
```

It needs Delve (`go install github.com/go-delve/delve/cmd/dlv@latest`) and prints that command if it cannot find it. By default it traces only your own code: `main.*` plus everything under the module path from the nearest `go.mod`. Tracing every function (`--func '.'`) also hooks the runtime's startup code, which breaks the run, so avoid it.

`--func` is a regex of function names, `--test` traces `go test` rather than a binary, and `--stack N` adds a stack trace to each traced call. Output is capped at `--max-lines` (300) and followed by call counts per function and the number of goroutines seen. `--output FILE` keeps the full raw trace.

## trace-rust.py

Profiles a Rust binary or test. If `cargo flamegraph` is installed you get a sampled call-stack flamegraph. If it is not, it runs the program with `RUST_BACKTRACE=full` so you still get panics and the path that ran, with nothing extra to install.

```bash
python trace-rust.py /path/to/crate --bin app
python trace-rust.py /path/to/crate --unit-test
python trace-rust.py /path/to/crate --bin app -- arg1 arg2
```

Install the profiler once with `cargo install flamegraph` for the call-stack view; the script reminds you when it is missing. When it runs, the SVG goes to `target/deeptrace-flamegraph.svg` and the hottest frames are also printed as text, so the agent can read them directly. On Linux the profiler needs `perf`; if the profile fails, the script falls back to the backtrace run.

DeepTrace flags go before `--` and program arguments after it. `--unit-test` runs the unit tests (profiled, or as `cargo test` with full backtraces in the fallback) instead of a binary.

## Other languages

When there is no bundled tracer, drive the language's own tooling from the shell and read the output:

- Java and Kotlin: async-profiler or `jstack` for call trees.
- Ruby: `tracepoint`, or `rbspy record`.
- Anything else: run it through `run.py --what test` with verbose flags and read the captured output for the path that ran and where it failed.
