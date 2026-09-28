# DeepTrace — maintainer notes

## What this is

DeepTrace is an agent skill that makes an AI agent investigate a real project by mapping it, running it, and tracing what actually executes before it reports bugs. It ships as one skill folder (`skills/deeptrace/`) with a small toolkit of recon, runner, and tracer scripts, and installs as a plugin in Claude Code, Codex, and Cursor, or in any skills-aware agent through `npx skills add muxover/deeptrace`.

## Stack & layout

- Skill: `skills/deeptrace/SKILL.md` (method, workflow, domain lenses, output format).
- Tools: `skills/deeptrace/scripts/` — Python 3.9+ standard library: `recon.py`, `run.py`, `trace.py`, `trace-go.py`, `trace-rust.py`, `trace-http.py`, `trace-ui.py`. Optional dependencies: Playwright + Chromium (UI), Delve (Go), `cargo flamegraph` (Rust). Node is profiled with `node --cpu-prof`.
- Tool reference: `skills/deeptrace/scripts/reference.md`.
- Plugin manifests, all at the same version and all with a marketplace named `deeptrace` whose source is the repo root:
  - Claude Code: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
  - Codex: `plugin.json`, `.agents/plugins/marketplace.json`
  - Cursor: `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json`
- Tests: `tests/` (pytest). `tests/test_regressions.py` holds one test per fixed tool bug, including end-to-end Delve and browser runs; `tests/test_manifests.py` keeps manifest versions, the changelog, and release notes in step.
- CI: `.github/workflows/ci.yml` — markdownlint, ruff + pytest on Python 3.9/3.11/3.13, and a live-tracers job with Delve and Chromium. `.github/workflows/release.yml` runs CI on a `v*` tag, then creates the GitHub release named from `release-notes/vX.Y.Z.md`.

## Decisions

- 2026-09-28: Skill calls its tools through `${CLAUDE_SKILL_DIR}/scripts`, because the agent's working directory is the project under investigation, not the skill folder. Other agents follow the fallback note and use the folder that holds `SKILL.md`.
- 2026-09-28: Go tracer defaults to the module's own functions; tracing everything breaks Delve on runtime startup code.
- 2026-09-28: `trace-http.py --repeat/--concurrency` is the race and idempotency tool for live services.
- 2026-09-28: `trace.py` labels each exception caught, uncaught, or exit, so handled errors are not reported as crashes.
- 2026-09-28: `trace-node.js` removed in 0.3.0. `node --cpu-prof` handles `process.exit()`, top-level `await`, and `tsx`, which the wrapper did not.
- 2026-09-28: Marketplaces are named `deeptrace` in every agent (install id `deeptrace@deeptrace`), matching js-view.
- 2026-09-28: Every version gets release notes and a GitHub release; published versions never change.

## Status

- v0.3.0 installs through the Claude Code CLI, the Codex CLI, and `npx skills add`. The Cursor plugin import has not been tried in Cursor itself.
- Every shipped tool is covered by tests, including real Delve and Chromium runs in CI.

## Next

- To release: bump `version` in the three `plugin.json` files, add a CHANGELOG entry and `release-notes/vX.Y.Z.md` (`tests/test_manifests.py` fails if they drift), sign the commit, push `main`, then push the tag.

## Open questions

- None.
