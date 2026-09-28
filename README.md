# DeepTrace

<div align="center">

[![CI](https://github.com/muxover/deeptrace/actions/workflows/ci.yml/badge.svg)](https://github.com/muxover/deeptrace/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8B5CF6.svg)](#installation)

**Deep, evidence-based debugging skill for AI agents.**

</div>

---

DeepTrace is an agent skill for Cursor and Claude Code. Most code review skims the text and guesses what happens at runtime. DeepTrace makes the agent look instead. It maps the project, runs it, and traces what actually executes before it draws a conclusion. The skill comes with a few small tools: a project scanner, a test and build runner, and runtime tracers for Python, JavaScript, Go, and Rust. Because of those tools, the findings come from real behavior rather than from how the code reads, and the report follows the same shape every time.

---

## Features

- Maps, runs, and traces a real project instead of reading pasted snippets.
- Works through six levels of analysis, from plain logic down to real failures.
- Walks execution step by step: inputs, state changes, output, and where it breaks.
- Reads the code as a developer, a user, an attacker, and under load.
- Says "not defined in provided context" rather than inventing behavior it cannot see.
- Reports findings in a fixed format with severities and a confidence score.
- Carries security, performance, API, and UI lenses in one skill, so it traces any tool or interface.

---

## How it works

Each analysis tries to reach six levels of depth:

1. Syntax and direct logic
2. Control flow
3. State and data flow
4. Edge cases
5. System stress
6. Real-world failure simulation

It traces what actually runs instead of describing it in the abstract:

```mermaid
flowchart LR
    input[Input enters system] --> exec[Step-by-step execution]
    exec --> state[State changes tracked]
    state --> output[Output generated]
    output --> fail[Failure points identified]
```

If several components talk to each other, it follows the flow across them too.

---

## Toolkit

On a real project the agent runs these tools and reads their output. The Python tools use only the standard library; the UI, Go, and Rust tracers need Playwright, Delve, and `cargo flamegraph`, and each one prints the exact install command when its dependency is missing.

| Tool | What it gives the agent |
|------|-------------------------|
| `recon.py` | Stacks, languages, entry points (from names, manifests, and real `main` functions), biggest files, TODO/FIXME markers |
| `run.py` | Runs tests, build, or app with the project's own package manager or virtualenv. Kills the whole process tree on timeout, passes extra args after `--`, and `--race` enables Go's race detector |
| `trace.py` | Python call graph with arguments and return values, threads, and every exception labeled caught, uncaught, or exit |
| `trace-node.js` | Sampled V8 call tree and hottest functions for Node and JavaScript |
| `trace-go.py` | Delve function tracing scoped to your module, with call counts and goroutines seen |
| `trace-rust.py` | `cargo flamegraph` with the hot frames printed as text, or a full-backtrace run of the binary or tests |
| `trace-http.py` | Real request/response contract, sequence replay, and parallel repeats (`--repeat`, `--concurrency`) for race and idempotency checks |
| `trace-ui.py` | Real browser run: console errors with source lines, network waterfall with real timings, DOM and React render activity, screenshots |

Full usage is in [skills/deeptrace/scripts/reference.md](skills/deeptrace/scripts/reference.md). These tools execute your code and send real traffic, so only point them at targets you trust.

---

## Examples

Each one is a full analysis in the DeepTrace output format:

- [race-condition.md](examples/race-condition.md): a check-then-act concurrency bug.
- [security-sql-injection.md](examples/security-sql-injection.md): injection and auth bypass.
- [performance-n-plus-one.md](examples/performance-n-plus-one.md): an N+1 query blowup.
- [ui-stale-closure.md](examples/ui-stale-closure.md): a React stale-closure freeze.
- [api-idempotency.md](examples/api-idempotency.md): a double-charge on retry.

---

## Installation

### Claude Code (plugin)

```text
/plugin marketplace add muxover/deeptrace
/plugin install deeptrace@muxover
```

Or from your shell: `claude plugin marketplace add muxover/deeptrace && claude plugin install deeptrace@muxover`.

### Claude Code (manual)

```bash
git clone https://github.com/muxover/deeptrace.git
cp -r deeptrace/skills/deeptrace ~/.claude/skills/deeptrace      # all projects
cp -r deeptrace/skills/deeptrace .claude/skills/deeptrace        # this project only
```

### Cursor

```bash
cp -r deeptrace/skills/deeptrace ~/.cursor/skills/deeptrace      # all projects
cp -r deeptrace/skills/deeptrace .cursor/skills/deeptrace        # this project only
```

The skill is one self-contained folder, so any agent that reads `SKILL.md`-style skills can use it the same way.

---

## Usage

Ask the agent to debug, audit, or trace something and the `deeptrace` skill loads on its own. In Claude Code, call it directly with `/deeptrace` (or `/deeptrace:deeptrace` when installed as a plugin).

It carries four domain lenses (security, performance, API, and UI) and leads with whichever the task points to. Name one to steer it:

- "use deeptrace on the checkout flow, something double-charges on retry"
- "use the security lens on this handler"
- "why does this page freeze after the second click?"

---

## Project Layout

```text
DeepTrace/
├── README.md                              This file
├── LICENSE                                MIT license
├── CONTRIBUTING.md                        Contributor guide
├── SECURITY.md                            Vulnerability reporting
├── .gitignore                             Ignored paths
├── .editorconfig                          Editor defaults
├── .markdownlint.json                     Markdown lint rules
├── pyproject.toml                         Ruff + pytest config
├── requirements-dev.txt                   Dev dependencies (pytest, ruff)
├── CHANGELOG.md                           Release notes
├── .claude-plugin/
│   ├── plugin.json                        Claude Code plugin manifest
│   └── marketplace.json                   One-command install
├── docs/
│   └── PROJECT.md                         Project state: decisions, status, next steps
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md           PR template
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md                  Bug report form
│   │   └── feature_request.md             Feature request form
│   └── workflows/
│       └── ci.yml                         Lint, tests, and live tracer runs
├── tests/                                 Pytest suite, including end-to-end tracer runs
├── examples/
│   ├── race-condition.md                  Concurrency trace
│   ├── security-sql-injection.md          Security audit trace
│   ├── performance-n-plus-one.md          Performance trace
│   ├── ui-stale-closure.md                UI state trace
│   └── api-idempotency.md                 API audit trace
└── skills/
    └── deeptrace/                         The skill
        ├── SKILL.md                       Method, workflow, and domain lenses
        └── scripts/
            ├── recon.py                   Static project map
            ├── run.py                     Polyglot test/build/run runner
            ├── trace.py                   Python runtime tracer
            ├── trace-node.js              Node/JS runtime tracer
            ├── trace-go.py                Go runtime tracer (Delve)
            ├── trace-rust.py              Rust runtime tracer (flamegraph)
            ├── trace-http.py              HTTP request/response capture
            ├── trace-ui.py                Browser UI runtime tracer (Playwright)
            └── reference.md               Tool usage + cross-language tracing
```

---

## Support matrix

The reasoning works for any language. The tooling is first-class for Python, JavaScript, Go, and Rust, and falls back to each language's own tools for the rest.

| Capability | First-class | Via native tools (agent-driven) | Not covered |
|------------|-------------|----------------------------------|-------------|
| Static map (`recon.py`) | ~20 languages, 12 manifests | any text file | semantic/call-graph analysis |
| Run tests/build (`run.py`) | Python, Go, JS, Rust, Make | any `Makefile` target | Bazel, custom toolchains, Docker-only setups |
| Runtime trace | Python (`trace.py`), JS/TS (`trace-node.js`), Go (`trace-go.py`), Rust (`trace-rust.py`) | JVM, Ruby via profilers | PHP, C/C++, C# deep tracing |
| HTTP contract (`trace-http.py`) | any HTTP service | — | gRPC, WebSocket capture |
| UI runtime (`trace-ui.py`) | any web UI via Chromium | other browsers via Playwright | native/mobile UIs |
| Race detection | Go (`run.py --race`), live services (`trace-http.py --concurrency`) | Rust via miri/loom, Python via thread-tagged traces | Node in-process races |

Go tracing needs Delve, Rust call-stack profiles need `cargo flamegraph`, and UI tracing needs Playwright with Chromium. Each is detected automatically, with Rust falling back to a backtrace run and the UI and TypeScript tracers printing the exact install command when a dependency is missing. There is no sandbox and no profiling dashboard. These tools execute real code and send real traffic from your machine.

---

## Limitations

DeepTrace is a reasoning skill with a few helper tools, not a full debugger or static analyzer. The runner executes real project code, so only use it on code you trust and where running it is safe. Deterministic line-by-line tracing is Python-only; the other languages use sampling profilers or their own tracers, which can miss very short calls. The Node tracer has known gaps (programs that end in `process.exit()`, ESM with top-level `await`, and TypeScript on Node 22+), listed with workarounds in the reference. The analysis is only as good as the code and output it sees, and the confidence score is the model's own estimate rather than a measurement. Check its findings before you act on them.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

Licensed under the [MIT](LICENSE) license.

---

## Links

- Repository: https://github.com/muxover/deeptrace
- Issues: https://github.com/muxover/deeptrace/issues
- Changelog: [CHANGELOG.md](CHANGELOG.md)

---

<p align="center">Made with ❤️ by Jax (@muxover)</p>
