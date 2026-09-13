"""ASTRA Core logging infrastructure."""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """Log levels for ASTRA logging."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class LogEntry:
    """A structured log entry."""

    level: LogLevel
    message: str
    component: str
    tick: int = -1
    context: Dict[str, Any] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}


class AstraLogger:
    """ASTRA's structured logger."""

    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self._logger = logging.getLogger(f"astra.{name}")
        self._logger.setLevel(level.value)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def debug(self, message: str, **context):
        self._logger.debug(message, extra=context)

    def info(self, message: str, **context):
        self._logger.info(message, extra=context)

    def warning(self, message: str, **context):
        self._logger.warning(message, extra=context)

    def error(self, message: str, **context):
        self._logger.error(message, extra=context)

    def critical(self, message: str, **context):
        self._logger.critical(message, extra=context)


# Global logger registry
_loggers: Dict[str, AstraLogger] = {}


def get_logger(name: str, level: LogLevel = LogLevel.INFO) -> AstraLogger:
    """Get or create a logger for the given component."""
    if name not in _loggers:
        _loggers[name] = AstraLogger(name, level)
    return _loggers[name]


def set_global_level(level: LogLevel):
    """Set the global logging level for all ASTRA loggers."""
    logging.getLogger("astra").setLevel(level.value)
