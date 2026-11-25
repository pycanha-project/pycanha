# Licenses

pycanha is released under the [MIT License](../LICENSE). It is pure Python and
bundles no third-party code, so this folder holds no license files of its own.

## The compiled core

pycanha cannot run without its compiled core, which comes from two other
pycanha repositories, both MIT-licensed:

- [pycanha-core](https://github.com/pycanha-project/pycanha-core), the C++
  library. Several third-party libraries are compiled into it (Eigen, HDF5,
  SymEngine, Manifold and others); they are listed, with their license files,
  in its [`LICENSES/`](https://github.com/pycanha-project/pycanha-core/tree/main/LICENSES)
  folder.
- [pycanha-core-python](https://github.com/pycanha-project/pycanha-core-python),
  the Python bindings, published on PyPI as `pycanha-core`. Its wheel contains
  the C++ library and carries the license files above.

## Python dependencies

Installed by pip as separate packages, each with its own license:

| Package | License |
|---|---|
| h5py | BSD-3-Clause |
| lark | MIT |
| matplotlib | Matplotlib License (PSF-based) |
| numpy | BSD-3-Clause |
| PySide6-Essentials (Qt) | LGPL-3.0-only (or GPL) |
| pyvista, pyvistaqt | MIT |
| scipy | BSD-3-Clause |

Qt for Python is used under the LGPL: pycanha only imports it, and it is
installed as its own package, which users can replace with another build.

## Keeping this up to date

When `pyproject.toml` gains or loses a runtime dependency, update the table.
When pycanha-core adds a library compiled into it, nothing changes here: that
list lives in pycanha-core.
