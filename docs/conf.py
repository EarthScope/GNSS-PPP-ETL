import os
import sys

# Add all package src directories to path for autodoc
sys.path.insert(0, os.path.abspath("../packages/gnss-product-management/src"))
sys.path.insert(0, os.path.abspath("../packages/pride-ppp/src"))
sys.path.insert(0, os.path.abspath("../packages/gnss-management-specs/src"))

project = "GNSSommelier"
author = "EarthScope"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # Google/NumPy docstring support
    "sphinx.ext.viewcode",  # links to source
    "sphinx.ext.intersphinx",  # cross-links to Python stdlib docs
    "myst_parser",  # Markdown support
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Napoleon settings (matches your existing docstring style)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# Intersphinx — link to Python docs
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# autodoc: show members and inherited members by default
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

# Suppress duplicate object warnings from re-exports through __init__.py
suppress_warnings = ["autodoc.duplicate_object"]
