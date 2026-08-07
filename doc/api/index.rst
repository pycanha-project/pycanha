API reference
=============

pycanha is the Python layer. pycanha_core is the compiled C++ backend it is
built on. Most pycanha classes derive from a pycanha_core class, and some are
re-exported from it unchanged. Each page states which case applies.

.. toctree::
   :maxdepth: 2
   :caption: pycanha

   pycanha
   pycanha.tmm
   pycanha.gmm
   pycanha.conduction
   pycanha.parameters
   pycanha.solvers
   pycanha.io

.. toctree::
   :maxdepth: 2
   :caption: pycanha_core

   pycanha_core
   pycanha_core.tmm
   pycanha_core.gmm
   pycanha_core.parameters
   pycanha_core.solvers
