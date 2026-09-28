# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-28

### Added

- Claude Code plugin and marketplace manifests: install with `/plugin marketplace add muxover/deeptrace`.
- `trace-http.py --repeat N --concurrency C` fires a request in parallel and summarizes statuses, latency percentiles, and distinct response bodies, for live race and idempotency checks.
- `trace-http.py` shows the body of error responses, and adds `--show-headers` and `--insecure`.
- `trace.py` labels every exception as caught (with where), uncaught, or exit, and reports the program's exit code.
- `trace.py --returns` records return values, `-m` traces a module like `python -m`, and `--exclude` trims the scope.
- `trace-ui.py --screenshot`, plus source locations on console messages and stacks on page errors.
- `trace-go.py` prints call counts and goroutines seen, and adds `--stack`, `--max-lines`, `--output`, and program args after `--`.
- `trace-rust.py` prints the flamegraph's hot frames as text.
- `run.py` passes args after `--` to the command, trims output to the last `--max-lines` lines, keeps full output with `--log`, and ends with a summary.
- `recon.py` finds entry points from manifests and from real `main` functions.
- The skill adds a verify-the-fix step: rerun the evidence after a change.
- A regression suite, with end-to-end runs against a real browser and Delve in CI.

### Fixed

- Script paths in the skill resolved against the project instead of the skill folder; they now use `${CLAUDE_SKILL_DIR}`.
- `trace-ui.py` network timings were meaningless (an epoch timestamp was subtracted from a relative value).
- `trace-ui.py` crashed when the page failed to load.
- `trace-go.py` traced every function by default, which broke the run; it now scopes to the project's module.
- `trace-rust.py` passed flags placed after the project path to the program, and `--unit-test` ran the binary instead of the tests in the fallback.
- `run.py` ran yarn and bun projects with npm, ran `make test` when no such target existed, and left child processes running after a timeout.
- `trace.py` also traced sibling directories whose names start with the project's name (`/proj` matched `/proj2`), and did not restore `sys.argv`/`sys.path`.
- `recon.py` counted every `DEBUG` as a `BUG` marker.

## [0.1.0] - 2026-06-25

### Added

- The DeepTrace skill: six analysis levels, execution simulation, and a fixed report format with severities and confidence.
- Security, performance, API, and UI domain lenses.
- Toolkit: `recon.py`, `run.py`, and tracers for Python, Node, Go, Rust, live HTTP services, and browser UIs.
- Five worked examples.

[Unreleased]: https://github.com/muxover/deeptrace/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/muxover/deeptrace/releases/tag/v0.2.0
[0.1.0]: https://github.com/muxover/deeptrace/releases/tag/v0.1.0
