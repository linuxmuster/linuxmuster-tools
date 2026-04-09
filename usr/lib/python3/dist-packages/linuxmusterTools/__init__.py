import logging

logger = logging.getLogger(__name__)
logger_handler = logging.StreamHandler()
logger.addHandler(logger_handler)
logger.setLevel(logging.INFO)

class LMNToolsFormatter(logging.Formatter):
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

logger_handler.setFormatter(LMNToolsFormatter())
