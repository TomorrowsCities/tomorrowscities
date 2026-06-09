import logging
from typing import Callable, List, Optional, Tuple


logger = logging.getLogger(__name__)
_log_sink: Optional[Callable[[str, str], None]] = None
_log_buffer: List[Tuple[str, str]] = []


def set_log_sink(sink: Optional[Callable[[str, str], None]]):
    global _log_sink
    _log_sink = sink


def clear_log_buffer():
    _log_buffer.clear()


def get_log_buffer() -> List[Tuple[str, str]]:
    return list(_log_buffer)


def _emit(level: str, message):
    text = str(message)
    _log_buffer.append((level, text))
    if _log_sink is not None:
        _log_sink(level, text)
    if level == "info":
        logger.info(text)
    elif level == "warning":
        logger.warning(text)
    elif level == "error":
        logger.error(text)
    else:
        logger.log(logging.INFO, text)


def log_info(message):
    _emit("info", message)


def log_warning(message):
    _emit("warning", message)


def log_error(message):
    _emit("error", message)
