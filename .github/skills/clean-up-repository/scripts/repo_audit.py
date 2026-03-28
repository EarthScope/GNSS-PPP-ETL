#!/usr/bin/env python3
"""Audit repository hygiene and report on project health indicators.

Scans a repository root for package management, pre-commit hooks, CI/CD,
code quality tooling, and standard project files.

Usage:
    python repo_audit.py <repo_root> [--json]

Examples:
    python repo_audit.py .
    python repo_audit.py /path/to/repo --json
"""

import argparse
import json
import sys
from pathlib import Path

# Status constants
FOUND = "found"
MISSING = "missing"
WARN = "warning"


def _exists(root: Path, *paths: str) -> str:
    for p in paths:
        if (root / p).exists():
            return FOUND
    return MISSING


def _first_match(root: Path, *paths: str) -> str | None:
    for p in paths:
        if (root / p).exists():
            return p
    return None


def audit_package_management(root: Path) -> list[dict]:
    results = []

    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        results.append({"item": "pyproject.toml", "status": FOUND, "detail": str(pyproject.relative_to(root))})

        if "[build-system]" in text:
            results.append({"item": "build-system table", "status": FOUND})
        else:
            results.append({"item": "build-system table", "status": MISSING, "detail": "pyproject.toml has no [build-system]"})

        has_pep621 = "[project]" in text
        results.append({
            "item": "PEP 621 metadata",
            "status": FOUND if has_pep621 else WARN,
            "detail": "Uses [project] table" if has_pep621 else "No [project] table — may use legacy format",
        })
    else:
        results.append({"item": "pyproject.toml", "status": MISSING})

    # Legacy files
    for legacy in ("setup.py", "setup.cfg"):
        if (root / legacy).exists():
            results.append({"item": legacy, "status": WARN, "detail": "Legacy — migrate to pyproject.toml"})

    # Lock file
    lock = _first_match(root, "uv.lock", "poetry.lock", "Pipfile.lock", "pdm.lock")
    results.append({
        "item": "lock file",
        "status": FOUND if lock else MISSING,
        "detail": lock or "No lock file for reproducible installs",
    })

    return results


def audit_precommit(root: Path) -> list[dict]:
    results = []
    cfg = root / ".pre-commit-config.yaml"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8")
        results.append({"item": ".pre-commit-config.yaml", "status": FOUND})

        # Check for unpinned revs
        for bad_rev in ("rev: main", "rev: master", "rev: HEAD"):
            if bad_rev in text:
                results.append({"item": "pre-commit rev pinning", "status": WARN, "detail": f"Found unpinned '{bad_rev}'"})
                break
        else:
            results.append({"item": "pre-commit rev pinning", "status": FOUND})

        # Check for ruff hook
        has_ruff = "ruff" in text
        results.append({
            "item": "ruff in pre-commit",
            "status": FOUND if has_ruff else MISSING,
            "detail": None if has_ruff else "Consider adding ruff lint + format hooks",
        })
    else:
        results.append({"item": ".pre-commit-config.yaml", "status": MISSING})

    return results


def audit_code_quality(root: Path) -> list[dict]:
    results = []

    # Read pyproject.toml for tool configs
    pyproject = root / "pyproject.toml"
    pyproject_text = pyproject.read_text(encoding="utf-8") if pyproject.exists() else ""

    # Linter
    has_ruff = "[tool.ruff" in pyproject_text or (root / "ruff.toml").exists() or (root / ".ruff.toml").exists()
    has_flake8 = (root / ".flake8").exists() or (root / "setup.cfg").exists() and "flake8" in (root / "setup.cfg").read_text(encoding="utf-8")
    if has_ruff:
        results.append({"item": "linter (ruff)", "status": FOUND})
        if has_flake8:
            results.append({"item": "legacy linter (flake8)", "status": WARN, "detail": "Consolidate to ruff"})
    elif has_flake8:
        results.append({"item": "linter (flake8)", "status": FOUND, "detail": "Consider migrating to ruff"})
    else:
        results.append({"item": "linter", "status": MISSING})

    # Formatter
    has_ruff_fmt = "ruff-format" in pyproject_text or "ruff format" in pyproject_text
    has_black = "[tool.black" in pyproject_text or (root / ".black.toml").exists()
    if has_ruff_fmt or has_ruff:
        results.append({"item": "formatter (ruff)", "status": FOUND})
    elif has_black:
        results.append({"item": "formatter (black)", "status": FOUND, "detail": "Consider migrating to ruff format"})
    else:
        results.append({"item": "formatter", "status": MISSING})

    # Type checker
    has_mypy = "[tool.mypy" in pyproject_text or (root / "mypy.ini").exists() or (root / ".mypy.ini").exists()
    has_pyright = "[tool.pyright" in pyproject_text or (root / "pyrightconfig.json").exists()
    if has_mypy or has_pyright:
        name = "mypy" if has_mypy else "pyright"
        results.append({"item": f"type checker ({name})", "status": FOUND})
    else:
        results.append({"item": "type checker", "status": MISSING, "detail": "Consider adding mypy or pyright"})

    # Test config
    has_pytest = "[tool.pytest" in pyproject_text or (root / "pytest.ini").exists() or (root / "conftest.py").exists()
    results.append({"item": "pytest config", "status": FOUND if has_pytest else MISSING})

    return results


def audit_ci(root: Path) -> list[dict]:
    results = []
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        yamls = list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml"))
        results.append({"item": "GitHub Actions workflows", "status": FOUND, "detail": f"{len(yamls)} workflow(s)"})
    else:
        results.append({"item": "CI/CD", "status": MISSING, "detail": "No .github/workflows/ found"})

    return results


def audit_project_files(root: Path) -> list[dict]:
    results = []

    # README
    readme = _first_match(root, "README.md", "README.rst", "README.txt", "README")
    if readme:
        size = (root / readme).stat().st_size
        if size < 50:
            results.append({"item": "README", "status": WARN, "detail": f"{readme} exists but is nearly empty ({size} bytes)"})
        else:
            results.append({"item": "README", "status": FOUND, "detail": readme})
    else:
        results.append({"item": "README", "status": MISSING})

    # License
    lic = _first_match(root, "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md")
    results.append({"item": "LICENSE", "status": FOUND if lic else MISSING, "detail": lic})

    # .gitignore
    results.append({"item": ".gitignore", "status": _exists(root, ".gitignore")})

    # Changelog
    cl = _first_match(root, "CHANGELOG.md", "CHANGELOG.rst", "CHANGES.md", "HISTORY.md")
    results.append({"item": "CHANGELOG", "status": FOUND if cl else MISSING, "detail": cl})

    # Contributing
    contrib = _first_match(root, "CONTRIBUTING.md", "CONTRIBUTING.rst", ".github/CONTRIBUTING.md")
    results.append({"item": "CONTRIBUTING", "status": FOUND if contrib else MISSING, "detail": contrib})

    # Security
    sec = _first_match(root, "SECURITY.md", ".github/SECURITY.md")
    results.append({"item": "SECURITY", "status": FOUND if sec else MISSING, "detail": sec})

    # EditorConfig
    results.append({"item": ".editorconfig", "status": _exists(root, ".editorconfig")})

    return results


def audit_repo(root: Path) -> dict:
    return {
        "root": str(root.resolve()),
        "categories": {
            "Package Management": audit_package_management(root),
            "Pre-commit Hooks": audit_precommit(root),
            "Code Quality": audit_code_quality(root),
            "CI/CD": audit_ci(root),
            "Project Files": audit_project_files(root),
        },
    }


def print_report(audit: dict) -> None:
    counts = {FOUND: 0, MISSING: 0, WARN: 0}

    for category, items in audit["categories"].items():
        print(f"\n## {category}")
        for item in items:
            status = item["status"]
            counts[status] = counts.get(status, 0) + 1
            icon = {"found": "+", "missing": "-", "warning": "!"}[status]
            line = f"  [{icon}] {item['item']}"
            if item.get("detail"):
                line += f"  ({item['detail']})"
            print(line)

    total = counts[FOUND] + counts[MISSING] + counts[WARN]
    print(f"\n## Summary")
    print(f"  Found: {counts[FOUND]}/{total}")
    print(f"  Missing: {counts[MISSING]}/{total}")
    print(f"  Warnings: {counts[WARN]}/{total}")

    score = counts[FOUND] / total * 100 if total > 0 else 0
    print(f"  Health score: {score:.0f}%")


def main():
    parser = argparse.ArgumentParser(description="Audit repository hygiene.")
    parser.add_argument("root", type=Path, help="Repository root directory.")
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"Error: {args.root} is not a directory.", file=sys.stderr)
        sys.exit(1)

    audit = audit_repo(args.root)

    if args.json:
        print(json.dumps(audit, indent=2))
    else:
        print(f"Repository audit: {audit['root']}")
        print_report(audit)


if __name__ == "__main__":
    main()
