Installation
============

Requirements
------------

* Python 3.13 or later
* Windows, Linux or macOS on Apple Silicon

Install from PyPI
-----------------

.. code-block:: bash

   pip install pycanha

This pulls in ``pycanha-core``, the compiled backend, and the runtime
dependencies.

Intel MKL
^^^^^^^^^

The Windows and Linux wheels use MKL. The macOS wheels do not. Building without
MKL is possible and requires building ``pycanha-core`` from source.

Development install
-------------------

.. code-block:: bash

   git clone https://github.com/pycanha-project/pycanha.git
   cd pycanha
   pip install -e ".[dev]"          # development tools
   pip install -e ".[doc]"          # documentation tools

Checking the installation
-------------------------

.. code-block:: python

   import pycanha as pc
   import pycanha_core

   pycanha_core.print_package_info()

   tm = pc.ThermalModel("test")
   print(f"Model name: {tm.name}")
