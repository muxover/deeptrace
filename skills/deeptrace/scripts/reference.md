# DeepTrace tools

A handful of small scripts that let the agent dig into a real project instead of guessing from a snippet. Most are plain Python with nothing to install. Run them from inside the project you are looking at.

## recon.py

Builds a picture of the project before anything runs.

```bash
python recon.py /path/to/project
python recon.py /path/to/project --json
```

It reports the stacks it found from the manifests, the files and lines per language, the common entry points, the ten largest source files, and every TODO, FIXME, HACK, XXX, or BUG it sees with its location.

## run.py

Works out how the project runs its tests, build, or app, runs that command, and keeps the output and exit code. Commands are looked up on PATH and run without a shell.

```bash
python run.py /path/to/project --what test
python run.py /path/to/project --what build
python run.py /path/to/project --dry-run
```

It knows Node (npm, pnpm, yarn, bun), Python (pytest), Go, Rust (cargo), and Make. Run `--dry-run` first to see the command; `--timeout` caps each one (300s by default).

This runs the project's code. Only run code you trust, and use `--dry-run` on a repo you do not know.

## trace.py

Runs a Python entry point under `sys.settrace` and records the call graph for the project, along with any exceptions raised on the way.

```bash
python trace.py --args app/main.py
python trace.py --lines --max-depth 6 app/main.py arg1 arg2
python trace.py --root /path/to/project --output trace.txt app/main.py
```

Put DeepTrace flags before the target; anything after the target path is handed to the target as its own arguments. You get an indented call trace (`-> file:line function(args)`), the list of exceptions, and call counts. `--lines` adds line-level events, `--max-depth` cuts noise, `--max-events` caps memory (200000 by default), and `--root` sets the scope (the target's directory by default). Threads it spawns are traced too and tagged with the thread name, which is usually how races and ordering bugs show up.

## trace-node.js

Runs a Node entry point under the V8 sampling profiler (the built-in `inspector` module, nothing to install) and prints the project's call tree, the busiest functions, and any uncaught error.

```bash
node trace-node.js app/server.js
node trace-node.js --top 50 --output trace.txt app/server.js arg1
node trace-node.js --root /path/to/project src/index.js
```

Flags go before the target, target arguments after. It handles both CommonJS and ESM entry points. The trace is sampled rather than exact, so a function that runs very briefly may not show up. When that matters, give it more work to do or step through it with `node --inspect-brk`. For TypeScript, compile to JS first or run it through a loader.

## trace-go.py

Uses Delve to trace function entry and exit in a real Go program or test.

```bash
python trace-go.py ./cmd/app --func 'Handle.*'
python trace-go.py ./... --test --func '.'
```

It needs Delve (`go install github.com/go-delve/delve/cmd/dlv@latest`) and prints that command if it cannot find it. `--func` is a regex of the functions to trace, and `--test` traces `go test` rather than a binary.

## trace-rust.py

Profiles a Rust binary or test. If `cargo flamegraph` is installed you get a sampled call-stack flamegraph. If it is not, it runs the program with `RUST_BACKTRACE=full` so you still get panics and the path that ran, with nothing extra to install.

```bash
python trace-rust.py /path/to/crate --bin app
python trace-rust.py /path/to/crate --unit-test
python trace-rust.py /path/to/crate --bin app -- arg1 arg2
```

Install the profiler once with `cargo install flamegraph` for the call-stack view; the script reminds you when it is missing. Program arguments go after `--`.

## Other languages

When there is no bundled tracer, drive the language's own tooling from the shell and read the output:

- Java and Kotlin: async-profiler or `jstack` for call trees.
- Ruby: `tracepoint`, or `rbspy record`.
- Anything else: run it through `run.py --what test` with verbose flags and read the captured output for the path that ran and where it failed.
