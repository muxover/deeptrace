# DeepTrace

<div align="center">

[![CI](https://github.com/muxover/DeepTrace/actions/workflows/ci.yml/badge.svg)](https://github.com/muxover/DeepTrace/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

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
- Has four optional add-on skills for security, performance, UI state, and APIs.

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

On a real project the agent runs these tools and reads their output. They are plain Python with nothing to install.

- `recon.py` scans the project and reports its stacks, languages, entry points, biggest files, and TODO/FIXME notes.
- `run.py` finds and runs the project's tests, build, or app (Python, Node, Go, Rust, or Make) and captures the output and exit code. Pass `--dry-run` to see the command first.
- `trace.py` runs a Python entry point under `sys.settrace` and records the call graph, exceptions, and any threads it spawns.
- `trace-node.js` runs a Node or JS entry point under the V8 profiler and prints the call tree and the hottest functions.
- `trace-go.py` uses Delve to trace Go function calls in a program or test.
- `trace-rust.py` profiles a Rust binary or test with `cargo flamegraph`, and falls back to a backtrace run when the profiler is not installed.

Python, JavaScript, Go, and Rust are first-class. For anything else the agent drives that language's own tracer; see [skills/deeptrace/scripts/reference.md](skills/deeptrace/scripts/reference.md). The runner executes your code, so only point it at code you trust.

---

## Examples

Each one is a full analysis in the seven-part output format:

- [race-condition.md](examples/race-condition.md): a check-then-act concurrency bug.
- [security-sql-injection.md](examples/security-sql-injection.md): injection and auth bypass.
- [performance-n-plus-one.md](examples/performance-n-plus-one.md): an N+1 query blowup.
- [ui-stale-closure.md](examples/ui-stale-closure.md): a React stale-closure freeze.
- [api-idempotency.md](examples/api-idempotency.md): a double-charge on retry.

---

## Installation

Each skill is its own folder. Copy the one you want into your skills directory.

Cursor (personal, all projects):

```bash
cp -r skills/deeptrace ~/.cursor/skills/deeptrace
```

Cursor (project, shared via the repo):

```bash
cp -r skills/deeptrace .cursor/skills/deeptrace
```

Claude Code: place the skill folder under your Claude Code skills directory the same way.

Install any expansion skill by swapping the folder name, for example `skills/deeptrace-security`.

---

## Usage

Ask the agent to debug, audit, or trace something and the core `deeptrace` skill loads on its own. The add-on skills only load when you name them, for example "use deeptrace-security on this handler".

---

## Skills

- `deeptrace`: the core skill for tracing, edge cases, and failures. Loaded automatically.
- `deeptrace-security`: injection, auth bypass, input fuzzing, leaked secrets.
- `deeptrace-performance`: complexity, allocations, N+1 queries, lock contention, scaling.
- `deeptrace-ui-simulation`: render and state transitions, async UI races, stale state.
- `deeptrace-api-audit`: request and response shapes, status codes, idempotency, error contracts.

---

## Project Layout

```text
DeepTrace/
├── README.md                              This file
├── LICENSE                                MIT license
├── CONTRIBUTING.md                        Contributor guide
├── .gitignore                             Ignored paths
├── .editorconfig                          Editor defaults
├── .markdownlint.json                     Markdown lint rules
├── pyproject.toml                         Ruff + pytest config
├── requirements-dev.txt                   Dev dependencies (pytest, ruff)
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md           PR template
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md                  Bug report form
│   │   └── feature_request.md             Feature request form
│   └── workflows/
│       └── ci.yml                         Markdown lint on push and PR
├── tests/                                 Pytest suite for the toolkit
├── examples/
│   ├── race-condition.md                  Concurrency trace
│   ├── security-sql-injection.md          Security audit trace
│   ├── performance-n-plus-one.md          Performance trace
│   ├── ui-stale-closure.md                UI state trace
│   └── api-idempotency.md                 API audit trace
└── skills/
    ├── deeptrace/                         Core engine
    │   ├── SKILL.md                       Spec + active investigation workflow
    │   └── scripts/
    │       ├── recon.py                   Static project map
    │       ├── run.py                     Polyglot test/build/run runner
    │       ├── trace.py                   Python runtime tracer
    │       ├── trace-node.js              Node/JS runtime tracer
    │       ├── trace-go.py                Go runtime tracer (Delve)
    │       ├── trace-rust.py              Rust runtime tracer (flamegraph)
    │       └── reference.md               Tool usage + cross-language tracing
    ├── deeptrace-security/SKILL.md        Security and abuse focus
    ├── deeptrace-performance/SKILL.md     Performance and scaling focus
    ├── deeptrace-ui-simulation/SKILL.md   UI state focus
    └── deeptrace-api-audit/SKILL.md       API contract focus
```

---

## Support matrix

The reasoning works for any language. The tooling is first-class for Python, JavaScript, Go, and Rust, and falls back to each language's own tools for the rest.

| Capability | First-class | Via native tools (agent-driven) | Not covered |
|------------|-------------|----------------------------------|-------------|
| Static map (`recon.py`) | ~20 languages, 12 manifests | any text file | semantic/call-graph analysis |
| Run tests/build (`run.py`) | Python, Go, JS, Rust, Make | any `Makefile` target | Bazel, custom toolchains, Docker-only setups |
| Runtime trace | Python (`trace.py`), JS (`trace-node.js`), Go (`trace-go.py`), Rust (`trace-rust.py`) | JVM, Ruby via profilers | PHP, C/C++, C# deep tracing |

Go tracing needs Delve, and Rust call-stack profiles need `cargo flamegraph`. Both are detected automatically, and Rust still runs with a backtrace fallback when the profiler is missing. There is no sandbox, no profiling dashboard, no runtime race detector, and no database or network inspection. The runner executes real code on your machine.

---

## Limitations

DeepTrace is a reasoning skill with a few helper tools, not a full debugger or static analyzer. The runner executes real project code, so only use it on code you trust and where running it is safe. Deterministic line-by-line tracing is Python-only; the other languages use sampling profilers or their own tracers, which can miss very short calls. The analysis is only as good as the code and output it sees, and the confidence score is the model's own estimate rather than a measurement. Check its findings before you act on them.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

Licensed under the [MIT](LICENSE) license.

---

## Links

- Repository: https://github.com/muxover/DeepTrace
- Issues: https://github.com/muxover/DeepTrace/issues

---

<p align="center">Made with ❤️ by Jax (@muxover)</p>
