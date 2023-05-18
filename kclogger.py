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

    def fill_color(self, c="[37m", msg=""):
        return f'\033{c}{msg}\033[0m'

    def filter(self, rec: logging.LogRecord) -> bool:
        # 颜色map
        FMTDICT = {
            'DEBUG':    ["[36m", "DBG"],
            'INFO':     ["[37m", "INF"],
            'WARN':     ["[33m", "WAR"],
            'WARNING':  ["[33m", "WAR"],
            'ERROR':    ["[31m", "ERR"],
            'CRITICAL': ["[35m", "CRT"],
        }
        c, n = FMTDICT.get(rec.levelname, ["[37m", "UN"])
        rec.msg = self.fill_color(c, rec.msg)
        rec.levelname = self.fill_color(c, n)
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

def close_logger():
    for h in reversed(logger.handlers[:]):
        try:
            try:
                h.acquire()
                h.flush()
                h.close()
            except (OSError, ValueError):
                pass
            finally:
                h.release()
        except:
            ...

