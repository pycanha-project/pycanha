"""Sphinx configuration for pycanha documentation."""

import os
import sys
from datetime import date

# -- Project information -----------------------------------------------------
project = "pycanha"
author = "Javier Piqueras Carreño"
copyright = f"{date.today().year}, {author}"  # noqa: A001
release = "0.8.0"
version = "0.8"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_gallery.gen_gallery",
    "sphinx_copybutton",
    "sphinx_design",
    "numpydoc",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "examples/README.rst"]

# -- autodoc -----------------------------------------------------------------
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "inherited-members": True,
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"

# Avoid documenting __dict__, __weakref__, etc.
autodoc_default_flags = ["members"]

# -- autosummary -------------------------------------------------------------
autosummary_generate = True

# -- napoleon / numpydoc -----------------------------------------------------
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_use_param = False
napoleon_use_rtype = False
numpydoc_show_class_members = False  # let autodoc handle members

# -- sphinx-gallery ----------------------------------------------------------
sphinx_gallery_conf = {
    "examples_dirs": ["examples"],
    "gallery_dirs": ["auto_examples"],
    "filename_pattern": r"[\\/]plot_",
    "download_all_examples": True,
    "remove_config_comments": True,
    "plot_gallery": "True",
    "min_reported_time": 1,
}

# -- intersphinx -------------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "matplotlib": ("https://matplotlib.org/stable", None),
}

# -- HTML output -------------------------------------------------------------
html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme_options = {
    "github_url": "https://github.com/pycanha-project/pycanha",
    "logo": {
        "text": "pycanha",
    },
    "navigation_with_keys": False,
    "show_toc_level": 2,
    "navbar_align": "left",
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "secondary_sidebar_items": ["page-toc", "edit-this-page"],
    "footer_start": ["copyright"],
    "footer_end": ["theme-version"],
    "use_edit_page_button": True,
    "icon_links": [
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/pycanha/",
            "icon": "fa-solid fa-box",
        },
    ],
}

html_context = {
    "github_user": "pycanha-project",
    "github_repo": "pycanha",
    "github_version": "main",
    "doc_path": "doc",
}

html_show_sourcelink = False
