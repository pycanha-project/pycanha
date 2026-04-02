Installation
============

Requirements
------------

* Python 3.13 or later
* Windows, Linux or macOS (Apple Silicon)

Install from PyPI
-----------------

The recommended way to install **pycanha** is with ``pip``:

.. code-block:: bash

   pip install pycanha

This will automatically install ``pycanha-core`` (the compiled C++ backend)
and ``matplotlib`` as dependencies.

Optional: Intel MKL acceleration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, **pycanha** uses MKL in Windows and Linux versions. 
If you don't want to use MKL, the option is available, but you will need to build pycanha-core from source.
MacOS version is shipped without MKL.

Development install
-------------------

To install for development (editable mode with dev tools):

.. code-block:: bash

   git clone https://github.com/pycanha-project/pycanha.git
   cd pycanha
   pip install -e .                 # Install pycanha in editable mode
   pip install -e ".[doc]"          # For documentation dependencies
   pip install -e ".[dev]"          # For development dependencies


Verifying the installation
--------------------------

.. code-block:: python

   import pycanha_core
   pycanha_core.print_package_info()

   from pycanha.tmm import ThermalMathematicalModel
   tmm = ThermalMathematicalModel("test")
   print(f"Model name: {tmm.name}")
