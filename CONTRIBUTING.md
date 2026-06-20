# Contributing

DeepTrace is a set of Markdown agent skills plus a few helper scripts. If you can make the reasoning sharper, the output cleaner, or add an add-on skill that does something the core skill does not, please send it.

## Getting started

Clone the repo. There is no build step. Every skill is a `SKILL.md` file under `skills/`.

```bash
git clone https://github.com/muxover/DeepTrace.git
cd DeepTrace
```

## Code style

Markdown is checked with [markdownlint](https://github.com/DavidAnson/markdownlint-cli2) using the rules in `.markdownlint.json`, and the scripts are checked with [ruff](https://docs.astral.sh/ruff/). Run both before you open a PR:

```bash
npx markdownlint-cli2 "**/*.md"
ruff check .
```

Keep emoji out of headers, and keep the skill text short. Every line takes up room in the model's context.

## Running tests

There is a pytest suite for the scripts (recon, the runner, and the tracers):

```bash
pip install -r requirements-dev.txt
pytest
```

## Adding or changing a skill

- Each skill lives in `skills/<name>/SKILL.md` with valid YAML frontmatter (`name`, `description`).
- A new add-on skill should cover something the core `deeptrace` skill does not, not repeat it.
- Keep the same output format so results read the same across skills.

## Submitting changes

For anything bigger than a typo, open an issue first. Branch from `main`, keep one change per PR, and say what it improves.

## Reporting bugs

Use the issue templates. Include the skill name, the input you gave the agent, the output you got, and what you expected instead.
