# Reference

## Workflow Details

### 1. Audit Doc Coverage

**Goal**: Quantify documentation gaps and prioritize what to write.

**Steps**:
1. Run `scripts/doc_coverage.py <directory>` — outputs JSON and a human-readable table.
2. The script inspects all `.py` files and reports:
   - Module-level docstring: present / missing
   - Each public class: docstring present / missing, plus each public method
   - Each public function: docstring present / missing
   - Overall coverage: `documented / total` with percentage
3. "Public" means: name does not start with `_`.
4. Present the results as a markdown table sorted by coverage (lowest first).

**Example output**:
```
Module                          Coverage
------                          --------
pride_ppp/processor.py          3/8 (38%)
pride_ppp/config.py             5/5 (100%)
pride_ppp/output.py             4/7 (57%)
TOTAL                           12/20 (60%)
```

### 2. Generate Missing Docstrings

**Steps**:
1. Run the audit (Workflow 1) to get the gap list.
2. For each undocumented symbol:
   - Read the full function/class body.
   - Read 1-2 callers if the purpose isn't obvious from the name and body alone.
   - Write a Google-style docstring (see Style Guide below).
3. Apply edits file-by-file. After editing each file, verify no syntax errors.
4. Skip:
   - `_private` helpers unless their logic is non-obvious (>15 lines or has subtle edge cases).
   - `__init__` methods that only do `self.x = x` assignments — add a class-level docstring instead.
   - Test functions — test names should be self-documenting.

**Batch strategy**: Edit one file at a time. Read the full file, apply all docstrings for that file in one pass using multi-edit, then move to the next file.

### 3. Standardize Doc Style

**Steps**:
1. Run the audit to get a list of all documented symbols.
2. For each existing docstring, check against the Google style rules below.
3. Common fixes:
   - Convert NumPy-style (Parameters/Returns with dashes) → Google-style (Args/Returns with colons)
   - Convert reST-style (`:param x:`) → Google-style (`Args: x: ...`)
   - Remove type info from docstrings when type annotations exist on the signature
   - Add missing blank line before section headers
   - Fix indentation (4 spaces from the opening quotes)
4. Preserve all semantic content. Do not rewrite descriptions — only change formatting.

### 4. Generate README from Code

**Steps**:
1. Read `pyproject.toml` for: name, version, description, dependencies.
2. Read `__init__.py` for: public API exports.
3. Read existing README if present — preserve any user-written narrative.
4. Draft these sections:

```markdown
# Package Name

One-paragraph description from pyproject.toml or inferred from code.

## Installation

\`\`\`bash
pip install package-name
\`\`\`

## Quick Start

\`\`\`python
# Minimal working example using the primary API
\`\`\`

## API Overview

| Class / Function | Description |
|-----------------|-------------|
| `MainClass`    | One-line from docstring |
| `helper_fn()`  | One-line from docstring |

## Examples

Link to examples/ directory or inline short examples.
```

5. Present draft to user. Do not write until approved.

### 5. Create Usage Examples

**Steps**:
1. Search `test/` for fixtures and test functions that exercise the public API.
2. Search `dev/` and `examples/` for existing scripts.
3. For each key API entry point, create a standalone example:
   - Imports
   - Setup (minimal, with comments)
   - Core usage
   - Expected output (as a comment or print statement)
4. Place examples in `examples/` with descriptive filenames.
5. Each example should be runnable as `python examples/example_name.py` (with appropriate prerequisites noted at the top).

---

## Google Style Guide

### Function Docstring

```python
def resolve_products(date: datetime, constellations: list[str]) -> Resolution:
    """Resolve GNSS products for a given date and constellation set.

    Queries configured product centers and returns the first successful
    resolution. Falls back to rapid products if final are unavailable.

    Args:
        date: The observation date to resolve products for.
        constellations: GNSS constellation codes (e.g., ["G", "R", "E"]).

    Returns:
        A Resolution containing paths to all resolved product files.

    Raises:
        ProductNotFoundError: If no center can provide the required products.

    Example:
        >>> res = resolve_products(datetime(2024, 1, 15), ["G", "E"])
        >>> print(res.orbit_path)
    """
```

### Class Docstring

```python
class PrideProcessor:
    """Concurrent-safe RINEX-to-kinematic-position processing pipeline.

    Owns a private ProductEnvironment and WorkSpace. Each call to process()
    runs in an isolated temporary directory, making concurrent calls safe.

    Attributes:
        output_dir: Directory where final .kin files are written.

    Example:
        >>> proc = PrideProcessor(pride_dir="/opt/pride", output_dir="./out")
        >>> result = proc.process("site0010.obs", site="SITE", date=date(2024, 1, 1))
        >>> print(result.success)
    """
```

### Module Docstring

```python
"""Product resolution and dependency management for GNSS processing."""
```

### Rules Summary

| Rule | Detail |
|------|--------|
| Summary line | Imperative mood, fits on one line, no trailing period if single line |
| Blank lines | One blank line before each section header (`Args:`, `Returns:`, etc.) |
| Args format | `name: Description.` — no type (types go in annotations) |
| Returns | Describe the return value. Start with "A ..." or "True if ..." |
| Raises | List each exception and when it's raised |
| Example | Optional. Use `>>>` doctest format |
| Line width | 80 chars preferred, 100 max |
| Private symbols | Skip `_private` unless logic is non-obvious |
| `__init__` | Document on the class, not on `__init__` unless args need explanation |
| Dataclass | Document as class docstring; skip per-field docstrings unless complex |
| Enum | Class docstring summarizing purpose; individual members only if non-obvious |

---

## Edge Cases

### Overloaded functions
Document the general behavior in the main docstring. Use `Args` to describe all parameter combinations if `@overload` is used.

### Dataclasses
```python
@dataclass(frozen=True)
class ProcessingResult:
    """Result of a single PRIDE-PPP processing run.

    Attributes:
        rinex_path: Path to the input RINEX file.
        kin_path: Path to the output .kin file, or None if processing failed.
        returncode: Subprocess return code from pdp3.
    """
```

### Enums
```python
class Constellations(str, Enum):
    """GNSS constellation identifiers used in PRIDE-PPP configuration."""
    GPS = "G"
    GLONASS = "R"
```

### Properties
Document as if they were attributes — one-line description in the class docstring's `Attributes:` section, or a brief docstring on the property itself.
