.. pycanha documentation master file

pycanha
=======

pycanha is a thermal analysis package for Python. It builds, solves and
exchanges thermal models mainly related to spacecraft systems. The models are based
on the lumped parameter formulation, where networks of nodes are connected through
conductive and radiative couplings.

The core algorithms are implemented in `pycanha-core
<https://github.com/pycanha-project/pycanha-core>`_, a C++ library. This
package is the Python API on top of it.

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Getting started
      :link: getting_started/index
      :link-type: doc

      Installation and a first model, solved end to end.

   .. grid-item-card:: User guide
      :link: user_guide/index
      :link-type: doc

      Nodes and couplings, geometry, conduction from geometry, steady-state
      and transient solving, parameters and callbacks.

   .. grid-item-card:: Import / export
      :link: import_export/index
      :link-type: doc

      Reading and writing ESATAN-TMS and STEP-TAS files, and what each
      conversion costs.

   .. grid-item-card:: API reference
      :link: api/index
      :link-type: doc

      Every public class and function of pycanha and of the pycanha-core
      backend.

   .. grid-item-card:: Examples
      :link: auto_examples/index
      :link-type: doc

      Runnable examples with their output, including interactive 3D scenes.

.. toctree::
   :maxdepth: 2
   :hidden:

   getting_started/index
   user_guide/index
   import_export/index
   api/index
   auto_examples/index
