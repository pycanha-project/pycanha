"""Shared pytest configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import pycanha as pc

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True, scope="session")
def _no_log_files() -> Iterator[None]:
    """Keep the suite from writing under the directory pytest was started in.

    The log file and the diagnostics files both land in ``logs/`` relative to
    the working directory, and readers run in almost every test module, so
    without this a plain ``pytest`` leaves hundreds of files in the checkout.
    Records still reach the console and the buffer, which is all any test
    asserts on; a test that wants files turns them back on inside a tmp_path.
    """
    pc.log.set_file_output(False)
    yield
    pc.log.set_file_output(True)
