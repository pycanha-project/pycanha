"""Sphinx configuration for pycanha documentation."""

import os
import shutil
import subprocess
import sys
import time
from datetime import date
from importlib.metadata import PackageNotFoundError, version as _pkg_version

import pyvista
from pyvista.plotting.utilities.sphinx_gallery import DynamicScraper

# -- Headless 3D rendering for the GMM examples ------------------------------
# The GMM gallery examples render with pyvista. On a build server (Read the
# Docs / CI) there is no display, so we render off-screen and, on Linux, into a
# virtual framebuffer. ``BUILDING_GALLERY`` makes ``Plotter.show()`` capture a
# screenshot *and* an interactive vtk.js scene (``export_vtksz``) that
# ``DynamicScraper`` embeds in the page, so rotate/zoom works on the static site.
pyvista.OFF_SCREEN = True
pyvista.BUILDING_GALLERY = True


def _start_xvfb(display: int = 99, wait: float = 3.0) -> None:
    """Start an Xvfb virtual display (pyvista dropped ``start_xvfb`` in 0.48).

    No-op off Linux, when a display is already configured, or when Xvfb is
    unavailable (e.g. local Windows builds).
    """
    if not sys.platform.startswith("linux") or os.environ.get("DISPLAY"):
        return
    if shutil.which("Xvfb") is None:
        return
    subprocess.Popen(  # noqa: S603 - fixed, trusted argv; needed for headless GL
        ["Xvfb", f":{display}", "-screen", "0", "1920x1080x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = f":{display}"
    time.sleep(wait)


_start_xvfb()

# -- Project information -----------------------------------------------------
project = "pycanha"
author = "Javier Piqueras Carreño"
copyright = f"{date.today().year}, {author}"  # noqa: A001

# Single source of truth: the installed package version (from pyproject.toml via
# the build backend). ``release`` is the full version, ``version`` its X.Y part.
try:
    release = _pkg_version("pycanha")
except PackageNotFoundError:  # not installed (e.g. a bare checkout) - degrade gracefully
    release = "0.0.0"
version = ".".join(release.split(".")[:2])

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
    # Renders the interactive vtk.js scenes (``.. offlineviewer::``) that the
    # pyvista DynamicScraper emits for the GMM examples; needs sphinx_design
    # (above) for the Static/Interactive tab-set.
    "pyvista.ext.viewer_directive",
    "numpydoc",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    # Gallery source READMEs are section headers consumed by sphinx-gallery, not
    # standalone documents.
    "examples/README.rst",
    "examples/**/README.rst",
]

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
    # Capture matplotlib figures and pyvista scenes. DynamicScraper embeds the
    # pyvista scenes as interactive vtk.js (rotate/zoom on the static site).
    "image_scrapers": ("matplotlib", DynamicScraper()),
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
