---
name: improve-documentation
description: Audit, generate, and standardize code documentation including docstrings, READMEs, API references, and usage examples. Use when user wants to improve docs, audit doc coverage, generate missing docstrings, standardize doc style, create a README from code, write usage examples, or mentions "documentation gaps".
---

# Improve Documentation

## Process

1. **Scope the work** — ask user:
   - Which modules/packages? (or entire workspace)
   - Which doc types? (docstrings, README, API reference, examples)
   - Which workflow? (audit, generate, standardize, README, examples)

2. **Run the appropriate workflow** — see [REFERENCE.md](REFERENCE.md) for detailed steps.

3. **Review with user** — present changes before committing bulk edits.

## Workflows

### Audit doc coverage
Run `scripts/doc_coverage.py` on the target directory. Review the report — it lists every public symbol missing a docstring, every file without a module docstring, and overall coverage percentage. Present results as a prioritized table.

### Generate missing docstrings
1. Run the audit to identify gaps.
2. For each missing docstring, read the function/class, infer intent from usage and naming.
3. Write a Google-style docstring. Include `Args`, `Returns`, `Raises` only when applicable.
4. Apply edits in batches per file. Do NOT add docstrings to private helpers unless they are non-obvious.

### Standardize doc style
1. Run the audit to get the full symbol list.
2. For each existing docstring, check against the style rules in [REFERENCE.md](REFERENCE.md).
3. Rewrite non-conforming docstrings in place. Preserve semantic content — only change format.

### Generate README from code
1. Explore the package: read `__init__.py` exports, `pyproject.toml` metadata, and any existing README.
2. Draft sections: Purpose, Installation, Quick Start, API Overview, Examples.
3. Quick Start must contain a runnable code block. API Overview links to key classes/functions.
4. Present draft to user before writing.

### Create usage examples
1. Search tests and existing scripts for real usage patterns.
2. Extract and simplify into standalone examples.
3. Add narrative comments explaining each step.
4. Place in `examples/` directory or embed in README.

## Style Rules (Google)

- First line: imperative summary, no period if single line.
- Blank line before `Args:`, `Returns:`, `Raises:`, `Example:` sections.
- Args use `name: Description.` format (no type in docstring — types belong in annotations).
- Keep docstrings under 80 chars wide where possible.
- Module docstrings: one-line summary of the module's responsibility.

## Advanced

See [REFERENCE.md](REFERENCE.md) for:
- Detailed workflow checklists
- Style rule examples
- Edge cases (overloads, dataclasses, enums)
- Doc coverage script usage
