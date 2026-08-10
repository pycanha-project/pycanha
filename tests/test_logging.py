"""The pycanha.log surface: thresholds, the record buffer, and the file switch.

The machinery itself belongs to pycanha-core and is tested there.  What is
tested here is what layer 3 adds: that a record made in Python reaches the same
stream as one made in C++, that the cached record threshold stays in step with
the core's, and that the stdlib ``logging`` bridge is live without a setup call.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pycanha_core as pcc
import pytest

import pycanha as pc
from pycanha import log

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def restore_levels() -> Iterator[None]:
    """Put both thresholds back, so an assertion mid-test cannot leak them."""
    record, display = log.record_level(), log.display_level()
    yield
    log.set_record_level(record)
    log.set_display_level(display)


def test_the_log_module_is_reachable_from_the_package_root() -> None:
    assert pc.log is log
    assert pc.LogLevel is log.LogLevel


def test_a_python_record_lands_in_the_shared_buffer() -> None:
    log.clear_records()
    log.warning("a layer-3 record")

    (record,) = log.records(1)
    assert record.message == "a layer-3 record"
    assert record.level is log.LogLevel.WARN
    # One stream, two origins: this is what tells them apart.
    assert record.origin == "pycanha"


def test_a_core_record_lands_in_the_same_buffer() -> None:
    """Both origins share one buffer, one clock and one ordering.

    Removing a parameter that is not there is a void mutator refusing, so the
    record is the caller's only signal -- and it is made in C++, which is what
    makes it useful here.
    """
    log.clear_records()
    model = pc.ThermalModel()
    model.parameters.remove_parameter("no-such-parameter")

    (record,) = log.records(1)
    assert record.origin == "pycanha-core"
    assert record.level is log.LogLevel.WARN
    assert record.timestamp > 0.0
    assert record.pid > 0


def test_both_origins_order_against_each_other() -> None:
    log.clear_records()
    log.warning("before")
    pc.ThermalModel().parameters.remove_parameter("no-such-parameter")
    log.warning("after")

    origins = [record.origin for record in log.records(3)]
    assert origins == ["pycanha", "pycanha-core", "pycanha"]


def test_records_below_the_threshold_never_cross(restore_levels: None) -> None:
    log.set_record_level(log.LogLevel.ERROR)
    log.clear_records()

    log.warning("dropped")
    log.info("also dropped")
    assert log.records(10) == []

    log.error("kept")
    assert [r.message for r in log.records(10)] == ["kept"]


def test_should_log_tracks_the_record_threshold(restore_levels: None) -> None:
    log.set_record_level(log.LogLevel.WARN)
    assert log.should_log(log.LogLevel.ERROR) is True
    assert log.should_log(log.LogLevel.WARN) is True
    assert log.should_log(log.LogLevel.INFO) is False


def test_the_cached_threshold_is_refreshed_after_a_core_side_change(
    restore_levels: None,
) -> None:
    """Reaching past pycanha.log needs the explicit refresh, and gets it right."""
    log.set_record_level(log.LogLevel.INFO)
    pcc.log.set_record_level(log.LogLevel.ERROR)

    # Stale until asked: this is the cost of not crossing on every call.
    assert log.should_log(log.LogLevel.INFO) is True
    log.refresh_thresholds()
    assert log.should_log(log.LogLevel.INFO) is False


def test_the_record_threshold_cannot_go_below_what_was_compiled_in() -> None:
    floor = log.compiled_level_floor()
    if floor is log.LogLevel.TRACE:
        pytest.skip("this build compiled in everything, so there is no floor to hit")
    with pytest.raises(ValueError, match=r"(?i)level"):
        log.set_record_level(log.LogLevel.TRACE)


def test_the_logging_bridge_is_installed_without_being_asked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``pip install pycanha`` gets ecosystem integration with no setup call."""
    with caplog.at_level(logging.WARNING, logger="pycanha"):
        log.warning("visible to caplog")
        log.flush()  # delivery is deferred; this is the explicit drain point

    assert "visible to caplog" in caplog.text
    assert caplog.records[-1].name == "pycanha"


def test_the_bridge_prints_nothing_of_its_own() -> None:
    """A NullHandler is what stops a record appearing twice.

    The console belongs to the C++ sink; a handler on the Python side would be
    a second destination nobody asked for.
    """
    handlers = logging.getLogger("pycanha").handlers
    assert handlers
    assert all(isinstance(handler, logging.NullHandler) for handler in handlers)


def test_file_output_is_a_master_switch(tmp_path: Path) -> None:
    log.set_log_directory(str(tmp_path / "logs"))
    try:
        log.set_file_output(False)
        log.error("not written anywhere")
        log.flush()
        assert log.current_log_file() is None
        assert not (tmp_path / "logs").exists()

        log.set_file_output(True)
        log.error("written this time")
        log.flush()
        written = log.current_log_file()
        assert written is not None
        assert "written this time" in written.read_text(encoding="utf-8")
    finally:
        log.set_file_output(False)
        log.set_log_directory("logs")
