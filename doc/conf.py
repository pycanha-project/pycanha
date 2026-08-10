"""Sphinx configuration for pycanha documentation."""

import os
import shutil
import subprocess
import sys
import time
from datetime import date
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import pyvista
from pyvista.plotting.utilities.sphinx_gallery import DynamicScraper

import pycanha as pc
from pycanha.io.esatan.geometry import coverage

# -- Logging during the build ------------------------------------------------
# Gallery examples read models, and a read writes a log file and a diagnostics
# file under the working directory. A docs build should leave the tree it was
# run in exactly as it found it, so nothing goes to disk; the console still
# shows anything at WARN or above, which is what a build wants to surface.
pc.log.set_file_output(False)

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


def _interactive_scenes_work(timeout: float = 120.0) -> bool:
    """Whether ``export_vtksz`` can produce an interactive scene here.

    That export stands up a trame server, so it depends on a whole aiohttp /
    Jupyter stack that the rendering itself does not need. When any piece of it
    is broken -- a trame release that ships without its client assets is enough
    -- the first export raises and *every export after it blocks forever*: the
    docs build then hangs until the build server's timeout kills it, with no
    error to explain why. One throwaway export in a subprocess buys an answer
    that cannot hang the build and cannot leave a half-started server behind.
    """
    probe = (
        "import pyvista\n"
        "pyvista.OFF_SCREEN = True\n"
        "p = pyvista.Plotter(off_screen=True)\n"
        "p.add_mesh(pyvista.Sphere())\n"
        "p.export_vtksz(filename=None)\n"
    )
    try:
        completed = subprocess.run(  # noqa: S603 - fixed, trusted argv
            [sys.executable, "-c", probe],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    return completed.returncode == 0


# Interactive scenes are a bonus: without them the gallery still gets its
# screenshots, which is much better than a build that never finishes.
_INTERACTIVE_SCENES = _interactive_scenes_work()
if not _INTERACTIVE_SCENES:
    # ``show()`` exports the scene itself, and tolerates the export being
    # *absent* but not being broken -- so take it away rather than let it run.
    # Turning ``BUILDING_GALLERY`` off instead would be worse than useless: it
    # is also what makes ``show()`` keep the screenshot, so the gallery would
    # end up with no images at all.
    pyvista.Plotter.export_vtksz = lambda *_args, **_kwargs: None
    # Printed rather than logged: Sphinx has not started its own logging yet.
    print(
        "WARNING: pyvista cannot export interactive scenes here; the gallery "
        "will show static screenshots only."
    )

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
    # pyvista scenes as interactive vtk.js (rotate/zoom on the static site); the
    # plain ``"pyvista"`` scraper is the screenshot-only fallback, and pairing
    # DynamicScraper with scenes that were never exported only produces broken
    # ``offlineviewer`` blocks.
    "image_scrapers": ("matplotlib", DynamicScraper() if _INTERACTIVE_SCENES else "pyvista"),
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


# -- Generated content -------------------------------------------------------


def _write_esatan_coverage() -> None:
    """Regenerate the ESATAN construct-coverage table from the reader itself.

    The table states what the reader does with every construct of the ESATAN
    geometry language.  Deriving it here, on every build, is what stops the
    published version drifting from the code: a checked-in copy would only be
    as current as the last person who remembered to refresh it.

    The ``fixture`` column comes from reading the committed feature models, so
    it too is a fact about the tree rather than a claim about it.
    """
    # Resolved: Sphinx does not promise an absolute ``__file__``, and a relative
    # one walks to the wrong place silently -- the table still renders, with the
    # two columns that come from the feature models mysteriously blank.
    here = Path(__file__).resolve().parent
    fixtures = here.parent / "tests" / "data" / "esatan" / "FEATURES"
    if not fixtures.is_dir():
        msg = f"cannot generate the ESATAN coverage table: no feature models at {fixtures}"
        raise FileNotFoundError(msg)

    target = here / "import_export" / "esatan-coverage.csv"
    target.write_text(coverage.to_csv(coverage.rows(fixtures)), encoding="utf-8")


_write_esatan_coverage()
