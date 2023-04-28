import logging
from logging import handlers
from pathlib import Path
DEBUG = True
LOGFILE = Path(__file__).parent / "log.log"
# NAME = __package__
NAME = "SDN"


class Filter(logging.Filter):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def filter(self, record: logging.LogRecord) -> bool:
        # 颜色map
        FMTDCIT = {
            'DEBUG': "\033[36mDBG\033[0m",
            'INFO': "\033[37mINF\033[0m",
            'WARN': "\033[33mWAR\033[0m",
            'WARNING': "\033[33mWAR\033[0m",
            'ERROR': "\033[31mERR\033[0m",
            'CRITICAL': "\033[35mCRT\033[0m",
        }
        record.levelname = FMTDCIT.get(record.levelname)
        return True


def getLogger(name="CLOG", level=logging.INFO, fmt='[%(name)s-%(levelname)s]: %(message)s', fmt_date="%H:%M:%S") -> logging.Logger:
    fmter = logging.Formatter('[%(levelname)s]:%(filename)s>%(lineno)s: %(message)s')
    # 按 D/H/M 天时分 保存日志, backupcount 为保留数量
    dfh = handlers.TimedRotatingFileHandler(filename=LOGFILE, when='D', backupCount=2)
    dfh.setLevel(logging.DEBUG)
    dfh.setFormatter(fmter)
    # 命令行打印
    filter = Filter()
    fmter = logging.Formatter(fmt, fmt_date)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmter)
    ch.addFilter(filter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    # 防止卸载模块后重新加载导致 重复打印
    if not logger.hasHandlers():
        # 注意添加顺序, ch有filter, 如果fh后添加 则会默认带上ch的filter
        # logger.addHandler(fh)
        logger.addHandler(dfh)
        logger.addHandler(ch)
    return logger


level = logging.WARNING
if DEBUG:
    level = logging.DEBUG

logger = getLogger(NAME, level)
# logger.debug("DEBUG")
# logger.info("INFO")
# logger.warn("WARN")
# logger.error("ERROR")
# logger.critical("CRITICAL")
