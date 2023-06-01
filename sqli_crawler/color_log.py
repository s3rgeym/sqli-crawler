import logging
from typing import Any

from . import termcolor


class AnsiColorHandler(logging.StreamHandler):
    _color_map = {
        "CRITICAL": termcolor.RED,
        "ERROR": termcolor.RED,
        "WARNING": termcolor.YELLOW,
        "INFO": termcolor.GREEN,
        "DEBUG": termcolor.BLUE,
    }

    _fmt = logging.Formatter("[%(levelname).1s] %(message)s")

    def format(self, rec: logging.LogRecord) -> str:
        mess = self._fmt.format(rec)
        isatty = getattr(self.stream, "isatty", None)
        if isatty and isatty() and (col := self._color_map.get(rec.levelname)):
            return f"{col}{mess}{termcolor.RESET}"
        return mess
