:mod:`pycanha.conduction` — GMM → TMM conduction
================================================

.. currentmodule:: pycanha.conduction

Builds a thermal model's conductive network from its geometry: one node per
conductively active face slot that carries a node number, plus the in-plane and
through-thickness conductors those slots imply.

Whether a side takes part is :attr:`~pycanha_core.gmm.ThermalMesh.conductive_active_side`,
which is independent of the radiative selector — a surface can conduct without
radiating, and the other way round.  Radiative couplings, parameters, formulas
and thermal data are left untouched, and a build refuses to run on a tmm that
already holds nodes or conductive couplings.

.. code-block:: python

   import pycanha as pc

   model = pc.ThermalModel()
   ...                                    # build the gmm, number the faces
   report = model.build_tmm_from_gmm()
   print(pc.conduction.summary(report))

The builder itself is re-exported verbatim from :mod:`pycanha_core.conduction`:

* :class:`~pycanha_core.conduction.TmmBuildOptions` — what to generate, and the
  conductance below which a conductor is dropped
* :func:`~pycanha_core.conduction.build_tmm_from_gmm` — the same build as
  :meth:`pycanha.ThermalModel.build_tmm_from_gmm`
* :class:`~pycanha_core.conduction.TmmBuildReport`,
  :class:`~pycanha_core.conduction.BuildDiagnostic`,
  :class:`~pycanha_core.conduction.DiagnosticCode` and
  :func:`~pycanha_core.conduction.diagnostic_code_name` — what the build
  produced and what it had to skip or approximate
* :func:`~pycanha_core.conduction.intra_primitive_links`,
  :class:`~pycanha_core.conduction.CellLink` and
  :func:`~pycanha_core.conduction.through_thickness_conductance` — the same
  conductances one item at a time, without a model
* :func:`~pycanha_core.conduction.profile_of` and
  :class:`~pycanha_core.conduction.MeridianProfile` — the parametrisation a
  primitive's conductances are integrated over

Reading a build report
----------------------

A report carries its diagnostics as the builder's own objects.  These render
them in the vocabulary the file readers use, so code that already branches on
:class:`~pycanha.io.diagnostics.Diagnostic` works unchanged.

.. autofunction:: diagnostics

.. autofunction:: summary
