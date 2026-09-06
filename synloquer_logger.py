"""
Synloquer 日志模块

提供分级日志（DEBUG/INFO/WARNING/ERROR），同时输出到控制台和文件。
控制台只显示 INFO 及以上，文件记录全部级别。
"""

import logging
import os
from datetime import datetime


_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, f"synloquer_{datetime.now().strftime('%Y%m%d')}.log")

_logger = logging.getLogger("synloquer")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False

if not _logger.handlers:
    _console = logging.StreamHandler()
    _console.setLevel(logging.INFO)
    _console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    _logger.addHandler(_console)

    _file = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _file.setLevel(logging.DEBUG)
    _file.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(_file)


def debug(msg: str):
    _logger.debug(msg)


def info(msg: str):
    _logger.info(msg)


def warning(msg: str):
    _logger.warning(msg)


def error(msg: str):
    _logger.error(msg)


def exception(msg: str):
    _logger.exception(msg)
