"""Top-level thermal model owner."""

from __future__ import annotations

from typing import Self

import pycanha_core as pcc

from pycanha.tmm.thermalmathematicalmodel import ThermalMathematicalModel


class ThermalModel(pcc.tmm.ThermalModel):
    def __init__(
        self,
        name: str = "",
        tmm: ThermalMathematicalModel | None = None,
        gmm: pcc.gmm.GeometryModel | None = None,
    ) -> None:
        if (tmm is None) != (gmm is None):
            msg = "tmm and gmm must be provided together"
            raise ValueError(msg)

        if tmm is None:
            tmm = ThermalMathematicalModel(name)
            gmm = pcc.gmm.GeometryModel(name)

        assert gmm is not None
        super().__init__(name, tmm, gmm)

        self._tmm = tmm
        self._gmm = gmm
        tmm._set_root_model(self)

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