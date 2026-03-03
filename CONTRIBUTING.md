# Contributing

Thanks for contributing to `token-governor`.

## Before You Start

- Use Python virtual environment:
  - `python3 -m venv venv`
  - `source venv/bin/activate`
- Install dependencies:
  - `pip install -r requirements.txt`

## Report Issues

When opening an issue, include:

- What you expected
- What happened
- Reproduction steps
- Relevant command and arguments
- Relevant logs or stack traces

For strategy-related issues, please include:

- strategy mode (`--opt-strategy` or `--auto-strategy`)
- generated `auto_strategy_reasons` if available
- a sample of the affected task prompt

## Pull Request Guidelines

- Keep PRs focused and small.
- Update docs if behavior or CLI changes.
- Add or update tests when practical.
- Run a quick local check before PR:
  - `python3 -m compileall baseline governor main.py metrics docs`

Recommended smoke test:

- `venv/bin/python main.py --mode governor --auto-strategy --limit 1`

## Commit Message Style

Use conventional-style prefixes when possible:

- `feat:`
- `fix:`
- `docs:`
- `refactor:`
- `test:`
- `chore:`

Example:

- `feat(governor): add auto strategy recommendation metadata`
