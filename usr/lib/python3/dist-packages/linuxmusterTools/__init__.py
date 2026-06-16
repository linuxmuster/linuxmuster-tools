import sys
import logging
from pathlib import Path


class LMNToolsLoggingFormatter(logging.Formatter):
    grey = '\x1b[38;5;245m'
    green = '\x1b[38;5;82m'
    orange = '\x1b[38;5;214m'
    red = '\x1b[38;5;196m'
    bold_red = '\x1b[31;1m'
    violet = '\x1b[38;5;129m'
    reset = '\x1b[0m'

    def __init__(self):
        super().__init__()
        self.fmtprefix = "%(asctime)s %(name)60s" + self.violet + " %(filename)20s:%(lineno)d " + self.reset
        self.fmt = f"%(levelname)8s - %(message)s"
        self.FORMATS = {
            logging.DEBUG: self.fmtprefix + self.grey + self.fmt + self.reset,
            logging.INFO: self.fmtprefix + self.green + self.fmt + self.reset,
            logging.WARNING: self.fmtprefix + self.orange + self.fmt + self.reset,
            logging.ERROR: self.fmtprefix + self.red + self.fmt + self.reset,
            logging.CRITICAL: self.fmtprefix + self.bold_red + self.fmt + self.reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class LMNFileHandler(logging.Handler):
    """
    Routes log records to per-submodule files under /var/log/linuxmuster/lmntools/.
    """

    LOG_DIR = Path('/var/log/linuxmuster/lmntools')
    file_formatter = logging.Formatter(
        '%(asctime)s %(levelname)8s %(name)s %(filename)s:%(lineno)d - %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )

    def __init__(self):
        super().__init__()
        self._handlers = {}
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _get_handler(self, submodule):
        if submodule not in self._handlers:
            fh = logging.FileHandler(self.LOG_DIR / f'{submodule}.log')
            fh.setFormatter(self.file_formatter)
            self._handlers[submodule] = fh
        return self._handlers[submodule]

    def emit(self, record):
        parts = record.name.split('.')
        submodule = parts[1] if len(parts) > 1 else 'lmntools'
        self._get_handler(submodule).emit(record)


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.propagate = False


def setup_logging(mode='file'):
    """
    Configure logging for linuxmusterTools.

    mode='file'    : log to /var/log/linuxmuster/lmntools/<submodule>.log
    mode='console' : log to stderr with colored output
    """


    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    if mode == 'console':
        handler = logging.StreamHandler()
        handler.setFormatter(LMNToolsLoggingFormatter())
    else:
        handler = LMNFileHandler()

    logger.addHandler(handler)


if hasattr(sys, 'ps1') or sys.flags.interactive:
    setup_logging(mode='console')
