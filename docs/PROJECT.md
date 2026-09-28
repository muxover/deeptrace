# DeepTrace — project state

## What this is

DeepTrace is an agent skill for Claude Code and Cursor that makes the agent investigate a real project by mapping it, running it, and tracing what actually executes before it reports bugs. It ships as one skill folder (`skills/deeptrace/`) with a small toolkit of recon, runner, and tracer scripts, and installs as a Claude Code plugin from this repo.

## Stack & layout

- Skill: `skills/deeptrace/SKILL.md` (method, workflow, domain lenses, output format).
- Tools: `skills/deeptrace/scripts/` — Python 3.9+ standard library (`recon.py`, `run.py`, `trace.py`, `trace-go.py`, `trace-rust.py`, `trace-http.py`, `trace-ui.py`), plus `trace-node.js` for Node. Optional dependencies: Playwright + Chromium (UI), Delve (Go), `cargo flamegraph` (Rust).
- Tool reference: `skills/deeptrace/scripts/reference.md`.
- Plugin: `.claude-plugin/plugin.json` (version lives here) and `.claude-plugin/marketplace.json` (marketplace `muxover`, plugin `deeptrace`).
- Tests: `tests/` (pytest). `tests/test_regressions.py` holds one test per fixed tool bug, including end-to-end Delve and browser runs.
- CI: `.github/workflows/ci.yml` — markdownlint, ruff + pytest on Python 3.9/3.11/3.13, and a live-tracers job with Delve and Chromium.

## Decisions

- 2026-09-28: Skill calls its tools through `${CLAUDE_SKILL_DIR}/scripts`, because the agent's working directory is the project under investigation, not the skill folder.
- 2026-09-28: Distributed as a Claude Code plugin from this repo (`/plugin marketplace add muxover/deeptrace`); manual copy stays documented for Cursor.
- 2026-09-28: No GitHub Releases. Versions are git tags plus the `version` in `plugin.json` and a CHANGELOG entry.
- 2026-09-28: Go tracer defaults to the module's own functions; tracing everything breaks Delve on runtime startup code.
- 2026-09-28: `trace-http.py --repeat/--concurrency` is the race and idempotency tool for live services.
- 2026-09-28: `trace.py` labels each exception caught, uncaught, or exit, so handled errors are not reported as crashes.

## Status

- v0.2.0: all tools except `trace-node.js` were exercised against real fixtures and fixed; 47 tests pass.
- `trace-node.js` is unchanged from v0.1.0. Known limits are documented in `reference.md`: the report is lost on `process.exit()`, ESM with top-level `await` may not run, `tsx` loading fails on Node 22+, and hot functions are split per call site.

## Next

- Bring `trace-node.js` to the level of the other tracers.
- On every change: bump `version` in `.claude-plugin/plugin.json`, add a CHANGELOG entry, tag `vX.Y.Z`.

## Open questions

- `SECURITY.md` points to `contact@muxover.com`, which goes live once the muxover.com domain and inbox are set up.
