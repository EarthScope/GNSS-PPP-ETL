import os
import sys

# Add all package src directories to path for autodoc
sys.path.insert(0, os.path.abspath("../packages/gnss-product-management/src"))
sys.path.insert(0, os.path.abspath("../packages/pride-ppp/src"))
sys.path.insert(0, os.path.abspath("../packages/gpm-specs/src"))
sys.path.insert(0, os.path.abspath("../packages/gpm-cli/src"))

project = "GNSSommelier"
author = "EarthScope"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # Google docstring support
    "sphinx.ext.viewcode",  # links to source
    "sphinx.ext.intersphinx",  # cross-links to Python stdlib docs
    "sphinxcontrib.autodoc_pydantic",  # proper Pydantic v2 model docs
    "myst_parser",  # Markdown support
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Napoleon — Google-style docstrings only
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True

# Intersphinx — link to Python docs
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# autodoc defaults
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"

# autodoc-pydantic: clean rendering of Pydantic v2 models
autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_field_summary = False
autodoc_pydantic_model_member_order = "bysource"
autodoc_pydantic_field_list_validators = False

# Suppress duplicate-object warnings from Pydantic field descriptors
# being documented more than once (Sphinx 9 + Pydantic v2 interaction).
suppress_warnings = ["py.duplicate"]


def setup(app):  # noqa: D401
    """Resolve Pydantic forward-reference models before autodoc runs."""
    from gnss_product_management.factories.models import Resolution
    from gnss_product_management.lockfile import DependencyLockFile  # noqa: F401

    Resolution.model_rebuild()
