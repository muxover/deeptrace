# Contributing

DeepTrace is a single Markdown agent skill plus a few helper scripts. If you can make the reasoning sharper, the output cleaner, or extend a domain lens to cover something it misses, please send it.

## Getting started

Clone the repo. There is no build step. The skill is the `SKILL.md` file under `skills/deeptrace/`.

```bash
git clone https://github.com/muxover/deeptrace.git
cd deeptrace
```

## Code style

Markdown is checked with [markdownlint](https://github.com/DavidAnson/markdownlint-cli2) using the rules in `.markdownlint.json`, and the scripts are checked with [ruff](https://docs.astral.sh/ruff/). Run both before you open a PR:

```bash
npx markdownlint-cli2 "**/*.md"
ruff check .
```

Keep emoji out of headers, and keep the skill text short. Every line takes up room in the model's context.

## Running tests

There is a pytest suite for the scripts (recon, the runner, and the tracers). Tests that need Go with Delve or Playwright with Chromium run when those are installed and skip otherwise; CI installs all of them.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

When you fix a bug in a tool, add a regression test in `tests/test_regressions.py` that fails without the fix.

## Changing the skill

- The skill lives in `skills/deeptrace/SKILL.md` with valid YAML frontmatter (`name`, `description`).
- A new domain lens should cover something the existing lenses do not, not repeat them.
- Keep the same output format so results read the same every time.

## Submitting changes

For anything bigger than a typo, open an issue first. Branch from `main`, keep one change per PR, and say what it improves.

## Reporting bugs

Use the issue templates. Include the DeepTrace version, your OS, the exact command or prompt, the error output, and what you expected instead.
