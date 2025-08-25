# Contributing

Thank you for your interest in contributing!

## Development Setup

- Python 3.11+ required
- Recommended: [uv](https://github.com/astral-sh/uv) for environment management

```bash
uv venv
uv sync
```

- Fallback:
```bash
pip install -r requirements.txt
```

## Coding Standards

- Code style: [Ruff](https://github.com/charliermarsh/ruff)
- Type checking: [mypy](http://mypy-lang.org/)
- Security lint: [bandit](https://bandit.readthedocs.io/)

Run checks with:

```bash
make lint
```

## Submitting Changes

1. Fork and branch off `main`.
2. Ensure lint/tests pass (`make test lint`).
3. Update docs (README, CHANGELOG).
4. Submit a PR.

---

This project may adopt a DCO/CLA in the future.


### Quickstart scripts

If you don't want to use Make:

- Windows PowerShell:
```powershell
./setup-venv.ps1
```

- Linux/macOS:
```bash
./setup-venv.sh
```

These scripts will try **uv** first (if installed), else fall back to `python -m venv` and pip installs.


## Security Linting

We use [Bandit](https://bandit.readthedocs.io/) for static security checks.

- Config: in `pyproject.toml` under `[tool.bandit]`
- Run locally with `make security`


## Pre-commit Hooks

We use [pre-commit](https://pre-commit.com/) to run Ruff (lint/format) and Bandit (security linting) automatically on staged files.

### Setup

Install pre-commit (using pip or uv):
```bash
pip install pre-commit
# or: uv pip install pre-commit
```

Enable the hooks:
```bash
pre-commit install
```

Now, every time you commit, Ruff and Bandit will run automatically on the files you changed.
