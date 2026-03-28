# Reference

## Starter Templates

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=1000']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

**After creating**: run `pre-commit install` and `pre-commit run --all-files` to verify.

### Minimal pyproject.toml (PEP 621)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "package-name"
version = "0.1.0"
description = "One-line description."
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "Name", email = "email@example.com"}]
readme = "README.md"

dependencies = []

[project.optional-dependencies]
dev = ["ruff", "pre-commit", "pytest"]

[project.urls]
Repository = "https://github.com/owner/repo"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### .gitignore (Python)

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
.env
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.so
.DS_Store
```

### GitHub Actions — Test Workflow

```yaml
name: Test
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest
```

### GitHub Actions — Lint Workflow

```yaml
name: Lint
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .
```

---

## Migration Guides

### setup.py / setup.cfg → pyproject.toml

1. Read `setup.py` / `setup.cfg` to extract: name, version, description, author, dependencies, entry points.
2. Map fields to PEP 621:
   - `install_requires` → `dependencies`
   - `extras_require` → `[project.optional-dependencies]`
   - `entry_points.console_scripts` → `[project.scripts]`
   - `python_requires` → `requires-python`
   - `packages=find_packages()` → handled by build backend (hatchling auto-discovers)
3. Choose a build backend:
   - **hatchling** — zero-config, auto-discovers packages.
   - **setuptools** — if existing infra depends on it, use `[tool.setuptools.packages.find]`.
   - **flit-core** — lightweight, good for pure-Python packages.
4. Move tool configs (`[tool.pytest]`, `[tool.ruff]`, `[tool.mypy]`) into `pyproject.toml`.
5. Delete `setup.py`, `setup.cfg`, `MANIFEST.in` (hatchling handles includes automatically).
6. Verify: `pip install -e .` still works.

### Consolidating Linters to Ruff

1. Identify current tools: flake8, isort, black, pylint, pycodestyle, bandit.
2. Map to ruff rule codes:
   - flake8 → `E`, `F`, `W`
   - isort → `I`
   - pyupgrade → `UP`
   - flake8-bugbear → `B`
   - flake8-simplify → `SIM`
   - bandit → `S`
   - pylint → `PL`
3. Add `[tool.ruff.lint] select = [...]` with the mapped codes.
4. Remove old config files: `.flake8`, `.isort.cfg`, `pycodestyle.cfg`.
5. Remove old deps from `[project.optional-dependencies]`.
6. Update pre-commit config to use `ruff` and `ruff-format` hooks.
7. Run `ruff check . --fix` and `ruff format .` to apply.

### Adding Type Checking

```toml
[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

Start non-strict. Tighten gradually:
1. `ignore_missing_imports = true` initially — avoids blocking on untyped deps.
2. Add `disallow_untyped_defs = true` per-module as coverage improves.
3. Add a CI step: `mypy src/` once baseline passes.

---

## Audit Checklist

Use this as a manual checklist when the script isn't sufficient:

### Must Have
- [ ] `pyproject.toml` with `[build-system]` and PEP 621 metadata
- [ ] `README.md` — non-empty, has install + quickstart sections
- [ ] `LICENSE` — exists and matches `pyproject.toml` license field
- [ ] `.gitignore` — covers `__pycache__/`, `.venv/`, `dist/`, `*.egg-info/`
- [ ] No secrets or credentials committed (check `.env`, config files)
- [ ] No large binary files tracked (check for `.csv`, `.pkl`, `.h5`, `.zip`)

### Should Have
- [ ] `.pre-commit-config.yaml` with pinned revs
- [ ] Linter configured (ruff preferred)
- [ ] Formatter configured (ruff format preferred)
- [ ] CI workflow for tests
- [ ] CI workflow for linting
- [ ] Lock file for reproducible installs

### Nice to Have
- [ ] `CHANGELOG.md`
- [ ] `CONTRIBUTING.md`
- [ ] Type checker configured (mypy or pyright)
- [ ] Test coverage reporting
- [ ] `SECURITY.md` or security policy
- [ ] `py.typed` marker for typed packages
- [ ] `[project.urls]` with repository, docs, issues links
- [ ] EditorConfig (`.editorconfig`)
- [ ] Dependabot or Renovate config for dependency updates
