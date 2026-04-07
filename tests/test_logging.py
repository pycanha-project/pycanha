import pycanha as pc


def test_get_logger_roundtrip() -> None:
    logger = pc.get_logger()
    assert logger.name == "pycanha-core"

    pc.set_logger_level(pc.LogLevel.DEBUG)
    assert logger.level == pc.LogLevel.DEBUG
    assert logger.should_log(pc.LogLevel.INFO) is True


def test_get_python_logger_roundtrip() -> None:
    logger = pc.get_python_logger()
    assert logger.name == "pycanha-python"

    pc.set_python_logger_level(pc.LogLevel.INFO)
    assert logger.level == pc.LogLevel.INFO

    logger.info("python logger smoke test")
    logger.flush()
