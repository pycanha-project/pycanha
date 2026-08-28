:mod:`pycanha.conduction` — Conduction from geometry
====================================================

.. currentmodule:: pycanha.conduction

Builds the conductive network of a TMM from the GMM. It creates one node per
face that carries a node number on a side either active-side selector picks,
and the in-plane and through-thickness couplings the *conductively* active ones
imply. See :doc:`/user_guide/conduction` for the split between the two.

Radiative couplings, parameters, formulas and thermal data are left untouched.
The build refuses to run on a TMM that already holds nodes or conductive
couplings.

.. code-block:: python

   import pycanha as pc

   model = pc.ThermalModel()
   ...                                    # build the geometry, number the faces
   report = model.build_tmm_from_gmm()
   print(pc.conduction.summary(report))

The builder is re-exported from :mod:`pycanha_core.conduction` unchanged:

* :class:`~pycanha_core.conduction.TmmBuildOptions`, what to generate and the
  conductance below which a coupling is dropped
* :func:`~pycanha_core.conduction.build_tmm_from_gmm`, the same build as
  :meth:`pycanha.ThermalModel.build_tmm_from_gmm`
* :class:`~pycanha_core.conduction.TmmBuildReport`,
  :class:`~pycanha_core.conduction.BuildDiagnostic`,
  :class:`~pycanha_core.conduction.DiagnosticCode` and
  :func:`~pycanha_core.conduction.diagnostic_code_name`, what the build
  produced and what it had to skip or approximate
* :func:`~pycanha_core.conduction.intra_primitive_links`,
  :class:`~pycanha_core.conduction.FacePairLink` and
  :func:`~pycanha_core.conduction.through_thickness_conductance`, the same
  conductances one item at a time, without a model
* :func:`~pycanha_core.conduction.profile_of` and
  :class:`~pycanha_core.conduction.MeridianProfile`, the parametrisation each
  primitive's conductances are integrated over

Reading a build report
----------------------

These render the build report in the same form the file readers produce, so
code that branches on :class:`~pycanha.io.diagnostics.Diagnostic` works for
both.

.. autofunction:: diagnostics

.. autofunction:: summary
