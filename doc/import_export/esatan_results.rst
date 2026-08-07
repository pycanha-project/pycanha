ESATAN-TMS results and analysis files
=====================================

Two ESATAN-TMS file types build or fill a TMM. A ``.TMD`` file holds the
results of a run and the network they were computed on. A ``.d`` file holds the
analysis source: the declarative blocks that define the network, and the
imperative blocks that drive it.

Neither is written by pycanha.

.. important::

   Both readers are in active development. The APIs are not stable.


Building a model from a TMD file
--------------------------------

:meth:`~pycanha.ThermalModel.from_esatan_tmd` builds a complete TMM: the nodes
with their temperatures, thermal capacities and heat loads, and both the
conductive and the radiative couplings. The result is solvable.

.. code-block:: python

   import pycanha as pc

   model = pc.ThermalModel.from_esatan_tmd("DISCTR_STEADY.TMD", name="disc")

   print(model.tmm.nodes.num_nodes)
   print(model.tmm.conductive_couplings.get_coupling_value(1000, 1001))

The temperatures stored in the file are the solution of the run that produced
it, and they are loaded as they are.

To read into a model that already exists, use
:meth:`~pycanha.ThermalModel.read_tmd`, or
:meth:`~pycanha.ThermalModel.load_tmd` for the same call returning the model:

.. code-block:: python

   model = pc.ThermalModel("disc")
   model.read_tmd("DISCTR_STEADY.TMD")

Two engines read the same file:

``engine="cpp"``
   The default. The reader in the compiled core.

``engine="python"``
   The h5py reader in :class:`~pycanha.io.ESATANReader`. Slower, and useful
   when the file has to be inspected or the reading adapted.

Nodes marked inactive in the file are skipped by both engines.


Reading transient results without building a model
--------------------------------------------------

:meth:`~pycanha.tmm.ThermalMathematicalModel.read_tmd_transient` reads the time
dependent results into a named data model inside
:class:`~pycanha.tmm.ThermalData`. It does not create nodes or couplings.

.. code-block:: python

   model = pc.ThermalModel("disc")
   node_numbers = model.tmm.read_tmd_transient("DISCTR_TRANSIENT.TMD", "transient")

   data = model.tmm.thermal_data.models.get_model("transient")
   times = data.T.times                 # time samples [s]
   temperatures = data.T.values         # (n_steps, n_nodes)

The returned list gives the node number of every column, in column order. The
ESATAN-TMS user-defined time dependent constants come with the results, in
their three types:

.. code-block:: python

   constants = data.constants

   constants.real_names
   constants.int_names
   constants.char_names
   constants.times                      # [s]

   constants.real_values                # (n_steps, n_real)
   constants.char_value(step, index)

``model_name`` names the data model. ``overwrite=True`` replaces one that
already exists. ``attributes`` selects which attributes to read instead of all
of them.


Reading an analysis file
------------------------

:class:`~pycanha.io.ESATANReader` parses a ``.d`` file. The declarative blocks
populate the model. The imperative blocks are translated to Python on a best
effort basis and never change the model.

.. code-block:: python

   from pycanha.io import ESATANReader

   model = pc.ThermalModel()
   reader = ESATANReader(model)
   reader.parse_analysis_file("model.d")

``$LOCALS``, ``$CONSTANTS``, ``$ARRAYS``, ``$NODES`` and ``$CONDUCTORS`` are
processed in that fixed order, whatever order the file uses. Node and conductor
values that are expressions instead of numbers become parameters and formulas,
attached once the whole network exists. ``$ARRAYS`` are also registered as
lookup tables on ``model.tmm.thermal_data.tables``.

``$EVENTS``, ``$SUBROUTINES``, ``$INITIAL``, ``$EXECUTION``, ``$VARIABLES1``,
``$VARIABLES2`` and ``$OUTPUTS`` are translated to Python.
``emit_python_script=True`` writes the translation next to the source file:

.. code-block:: python

   reader.parse_analysis_file("model.d", emit_python_script=True)

Submodels and supernodes raise :class:`~pycanha.io.esatan.errors.EsatanParseError`.

Every parsing method also accepts raw text, so one block can be reprocessed on
its own:

.. code-block:: python

   reader.parse_constants("$CONSTANTS\n$REAL\n  k = 0.5;\n")
   reader.parse_conductors("GL(1,2) = k * 2;", conductor_type="GL")

Three accessors expose what the last parse produced: ``reader.locals``,
``reader.arrays`` and ``reader.block_texts``, the last holding the raw text of
every block found.
