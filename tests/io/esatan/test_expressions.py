"""Tests for the ESATAN safe arithmetic evaluator (``$CONSTANTS`` folding)."""

from __future__ import annotations

import pytest

from pycanha.io.esatan.expressions import SafeEvalError, safe_arithmetic


class TestSafeArithmetic:
    def test_basic(self) -> None:
        assert safe_arithmetic("1 + 2 * 3") == 7.0

    def test_with_parameters(self) -> None:
        assert safe_arithmetic("k * 2", parameters={"k": 0.5}) == 1.0

    def test_unary_minus(self) -> None:
        assert safe_arithmetic("-5 + 3") == -2.0

    def test_power(self) -> None:
        assert safe_arithmetic("2 ** 3") == 8.0

    def test_undefined_name_raises(self) -> None:
        with pytest.raises(SafeEvalError):
            safe_arithmetic("missing")

    def test_attribute_access_rejected(self) -> None:
        with pytest.raises(SafeEvalError):
            safe_arithmetic("a.b", parameters={"a": 1.0})

    def test_function_call_rejected(self) -> None:
        with pytest.raises(SafeEvalError):
            safe_arithmetic("abs(-1)")
