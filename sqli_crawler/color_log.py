import logging

from . import termcolor


class ColorHandler(logging.StreamHandler):
    _logging_colors = {
        "CRITICAL": termcolor.RED,
        "ERROR": termcolor.RED,
        "WARNING": termcolor.RED,
        "INFO": termcolor.GREEN,
        "DEBUG": termcolor.BLUE,
    }

    _fmt = logging.Formatter("[%(levelname).1s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        message = self._fmt.format(record)
        if getattr(self.stream, "isatty", lambda: False)() and (
            color := self._logging_colors.get(record.levelname)
        ):
            return f"{color}{message}{termcolor.RESET}"
        return message
