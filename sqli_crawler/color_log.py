import logging

from . import termcolor


class ColorHandler(logging.StreamHandler):
    _logging_colors = {
        "CRITICAL": termcolor.RED,
        "ERROR": termcolor.RED,
        "WARNING": termcolor.YELLOW,
        "INFO": termcolor.GREEN,
        "DEBUG": termcolor.BLUE,
    }

    @property
    def isatty(self) -> bool:
        return getattr(self.stream, "isatty", lambda: False)()

    _fmt = logging.Formatter("[%(levelname).1s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        message = self._fmt.format(record)
        if self.isatty and (
            color := self._logging_colors.get(record.levelname)
        ):
            return f"{color}{message}{termcolor.RESET}"
        return message
