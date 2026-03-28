---
name: clean-up-repository
description: Audit and improve repository hygiene — package management, pyproject.toml, pre-commit hooks, CI/CD, linting, formatting, README, license, and other markers of a well-maintained project. Use when user wants to clean up a repo, audit repo health, add pre-commit hooks, fix pyproject.toml, improve repo quality, make a repo "production-ready", or mentions "repo hygiene".
---

# Clean Up Repository

## Process

1. **Audit** — run `scripts/repo_audit.py` on the repo root. Review the report.
2. **Prioritize** — present findings to user as a ranked table (missing → misconfigured → nice-to-have).
3. **Fix** — apply changes category by category, confirming with user before bulk edits.

## Audit Categories

### Package Management
- Identify system: `pyproject.toml` (PEP 621), `setup.py`, `setup.cfg`, `Pipfile`, `requirements.txt`, `environment.yml`
- Prefer `pyproject.toml` with PEP 621 metadata. Flag legacy `setup.py`/`setup.cfg`.
- Check for lock file (`uv.lock`, `poetry.lock`, `Pipfile.lock`).
- Verify `[build-system]` table exists and specifies a backend.

### Pre-commit Hooks
- Check for `.pre-commit-config.yaml`. If missing, generate one.
- Standard hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, ruff, ruff-format.
- Verify `.pre-commit-config.yaml` pin revs (not `main`/`master`).

### Code Quality Tooling
- Linter: ruff, flake8, pylint — consolidate to ruff if multiple.
- Formatter: ruff format, black — prefer ruff format.
- Type checker: mypy, pyright/pylance config present.
- Config location: prefer `pyproject.toml` over standalone config files.

### CI/CD
- Check `.github/workflows/` for test, lint, and publish workflows.
- Flag repos with no CI at all.

### Project Files
- `README.md` — exists and is non-empty.
- `LICENSE` or `LICENSE.md` — exists.
- `.gitignore` — exists and covers language-specific patterns.
- `CHANGELOG.md` or equivalent.
- `CONTRIBUTING.md` for open-source repos.

### pyproject.toml Quality
- Required fields: `name`, `version`, `description`, `requires-python`, `license`, `authors`.
- Optional but recommended: `readme`, `classifiers`, `urls`, `[project.optional-dependencies]` for dev/test.
- Check `[tool.ruff]`, `[tool.pytest]`, `[tool.mypy]` sections.

## Generating Fixes

See [REFERENCE.md](REFERENCE.md) for:
- Starter templates for each missing file
- pyproject.toml migration guide (setup.py → PEP 621)
- Pre-commit config generator
- Ruff consolidation guide
