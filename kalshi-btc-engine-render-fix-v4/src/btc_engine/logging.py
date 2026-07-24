from __future__ import annotations

import json
import logging
import sys
from typing import Any


class EventLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _message(self, event: str, fields: dict[str, Any]) -> str:
        if not fields:
            return event
        return f"{event} {json.dumps(fields, default=str, separators=(',', ':'))}"

    def debug(self, event: str, **fields: Any) -> None:
        self._logger.debug(self._message(event, fields))

    def info(self, event: str, **fields: Any) -> None:
        self._logger.info(self._message(event, fields))

    def warning(self, event: str, **fields: Any) -> None:
        self._logger.warning(self._message(event, fields))

    def error(self, event: str, **fields: Any) -> None:
        self._logger.error(self._message(event, fields))

    def exception(self, event: str, **fields: Any) -> None:
        self._logger.exception(self._message(event, fields))


def get_logger(name: str) -> EventLogger:
    return EventLogger(name)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(asctime)sZ %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        level=level.upper(),
        force=True,
    )
