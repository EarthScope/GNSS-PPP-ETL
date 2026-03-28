#!/usr/bin/env python3
"""Audit docstring coverage for Python modules.

Scans a directory for .py files and reports which public symbols
(modules, classes, functions, methods) have docstrings.

Usage:
    python doc_coverage.py <directory> [--json] [--missing-only]

Examples:
    python doc_coverage.py src/pride_ppp
    python doc_coverage.py src/pride_ppp --json
    python doc_coverage.py src/pride_ppp --missing-only
"""

import argparse
import ast
import json
import sys
from pathlib import Path


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _has_docstring(node: ast.AST) -> bool:
    if not (hasattr(node, "body") and node.body):
        return False
    first = node.body[0]
    return isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)


def audit_file(filepath: Path) -> dict:
    """Audit a single Python file for docstring coverage.

    Args:
        filepath: Path to the .py file.

    Returns:
        Dict with 'file', 'module_docstring', 'symbols' list, 'documented', 'total'.
    """
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return {
            "file": str(filepath),
            "module_docstring": False,
            "symbols": [],
            "documented": 0,
            "total": 0,
            "error": "SyntaxError",
        }

    module_has_doc = _has_docstring(tree)
    symbols = []
    documented = 1 if module_has_doc else 0
    total = 1  # module itself counts

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _is_public(node.name):
                has_doc = _has_docstring(node)
                symbols.append({"name": node.name, "kind": "function", "has_docstring": has_doc, "line": node.lineno})
                total += 1
                documented += has_doc

        elif isinstance(node, ast.ClassDef):
            if _is_public(node.name):
                has_doc = _has_docstring(node)
                symbols.append({"name": node.name, "kind": "class", "has_docstring": has_doc, "line": node.lineno})
                total += 1
                documented += has_doc

                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        if _is_public(item.name):
                            method_has_doc = _has_docstring(item)
                            symbols.append({
                                "name": f"{node.name}.{item.name}",
                                "kind": "method",
                                "has_docstring": method_has_doc,
                                "line": item.lineno,
                            })
                            total += 1
                            documented += method_has_doc

    return {
        "file": str(filepath),
        "module_docstring": module_has_doc,
        "symbols": symbols,
        "documented": documented,
        "total": total,
    }


def audit_directory(directory: Path) -> list[dict]:
    """Audit all .py files in a directory recursively.

    Args:
        directory: Root directory to scan.

    Returns:
        List of per-file audit results.
    """
    results = []
    for filepath in sorted(directory.rglob("*.py")):
        if "__pycache__" in filepath.parts:
            continue
        results.append(audit_file(filepath))
    return results


def print_table(results: list[dict], missing_only: bool = False) -> None:
    """Print a human-readable coverage table.

    Args:
        results: List of audit results from audit_directory.
        missing_only: If True, only show files with missing docstrings.
    """
    total_doc = 0
    total_all = 0

    rows = []
    for r in results:
        total_doc += r["documented"]
        total_all += r["total"]
        pct = (r["documented"] / r["total"] * 100) if r["total"] > 0 else 100
        if missing_only and r["documented"] == r["total"]:
            continue
        rows.append((r["file"], f"{r['documented']}/{r['total']}", f"{pct:.0f}%"))

    if not rows:
        print("All public symbols are documented!")
        return

    max_file = max(len(row[0]) for row in rows)
    max_cov = max(len(row[1]) for row in rows)
    header = f"{'Module':<{max_file}}  {'Coverage':>{max_cov}}  Pct"
    print(header)
    print("-" * len(header))
    for file, cov, pct in rows:
        print(f"{file:<{max_file}}  {cov:>{max_cov}}  {pct}")

    total_pct = (total_doc / total_all * 100) if total_all > 0 else 100
    print("-" * len(header))
    total_str = f"{total_doc}/{total_all}"
    print(f"{'TOTAL':<{max_file}}  {total_str:>{max_cov}}  {total_pct:.0f}%")

    # Print missing symbols
    missing = []
    for r in results:
        if not r["module_docstring"]:
            missing.append((r["file"], "(module)", "module"))
        for sym in r["symbols"]:
            if not sym["has_docstring"]:
                missing.append((r["file"], sym["name"], sym["kind"]))

    if missing:
        print(f"\nMissing docstrings ({len(missing)}):")
        for file, name, kind in missing:
            print(f"  {file}: {name} ({kind})")


def main():
    parser = argparse.ArgumentParser(description="Audit Python docstring coverage.")
    parser.add_argument("directory", type=Path, help="Directory to scan.")
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    parser.add_argument("--missing-only", action="store_true", help="Only show files with gaps.")
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory.", file=sys.stderr)
        sys.exit(1)

    results = audit_directory(args.directory)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results, missing_only=args.missing_only)


if __name__ == "__main__":
    main()
