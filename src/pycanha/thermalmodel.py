"""Top-level thermal model owner."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Self

import pycanha_core as pcc

from pycanha.gmm import GeometryModel
from pycanha.tmm.thermalmathematicalmodel import ThermalMathematicalModel


class ThermalModel(pcc.tmm.ThermalModel):
    def __init__(
        self,
        name: str = "",
        tmm: ThermalMathematicalModel | None = None,
        gmm: GeometryModel | None = None,
    ) -> None:
        if (tmm is None) != (gmm is None):
            msg = "tmm and gmm must be provided together"
            raise ValueError(msg)

        if tmm is None:
            tmm = ThermalMathematicalModel(name)
            gmm = GeometryModel(name)
        elif gmm is None:
            msg = "tmm and gmm must be provided together"
            raise ValueError(msg)

        super().__init__(name, tmm, gmm)

        self._tmm = tmm
        self._gmm = gmm
        tmm._set_root_model(self)

    # The compiled base declares these as returning the pycanha-core classes.
    # Return the objects handed to the base constructor instead, so a caller
    # always gets the pycanha subclass, by construction rather than by
    # convention. The base getter returns these same objects today; going
    # through the stored reference is what keeps that guaranteed.
    @property
    def tmm(self) -> ThermalMathematicalModel:
        return self._tmm

    @property
    def gmm(self) -> GeometryModel:
        return self._gmm

    def explore(self) -> Any:
        """Open the interactive viewer on this model and block until it closes.

        The primary entry point of :mod:`pycanha.plot`: the geometry comes from
        :attr:`gmm` and the results panel from :attr:`tmm`, so this form is the
        one that can show both. Returns the window. See
        :func:`pycanha.plot.explore`.
        """
        # Imported on use, so a headless script that never opens a window does
        # not pay for the Qt widgets.
        return import_module("pycanha.plot.window").explore(self)

    def read_tmd(
        self,
        filepath: str,
        verbose: bool = False,
        **kwargs: object,
    ) -> None:
        self.tmm.read_tmd(filepath, verbose=verbose, **kwargs)

    def load_tmd(
        self,
        filepath: str,
        *,
        engine: str = "cpp",
        verbose: bool = False,
    ) -> Self:
        self.read_tmd(filepath, engine=engine, verbose=verbose)
        return self

    @classmethod
    def from_esatan_tmd(
        cls,
        filepath: str,
        name: str = "",
        *,
        engine: str = "cpp",
        verbose: bool = False,
    ) -> Self:
        model = cls(name=name)
        return model.load_tmd(filepath, engine=engine, verbose=verbose)
