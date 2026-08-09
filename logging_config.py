"""
Central logging setup for MSFS Startup Manager.

In a --windowed PyInstaller build there is no console, so sys.stdout and
sys.stderr are None. Any bare print() call (and there were a lot of them)
can raise on some setups when writing to a None stream, which can silently
kill a background thread. This module:

  1. Redirects stdout/stderr to a rotating log file when they're None
     (i.e. running frozen + windowed), so nothing raises on write.
  2. Sets up a `logging` logger that every module can use instead of
     print(), which also gets picked up when running from a normal
     console during development.
  3. Installs a hook to log uncaught exceptions instead of losing them.

Usage, once near the top of main():

    from logging_config import setup_logging
    logger = setup_logging()
"""

import sys
import os
import logging
import logging.handlers

import settings  # for APP_DIR

LOG_DIR = os.path.join(settings.APP_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "msfs_startup_manager.log")


class _StreamToLogger:
    """File-like shim so print()/stray writes still go somewhere useful."""

    def __init__(self, logger, level):
        self._logger = logger
        self._level = level

    def write(self, message):
        message = message.strip()
        if message:
            self._logger.log(self._level, message)

    def flush(self):
        pass


def setup_logging(level=logging.INFO):
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("msfs_startup_manager")
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging() is ever called twice
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler: 1MB per file, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # If we have a real console (dev mode / --start-background from a
    # terminal), also log there. If stdout/stderr are None (frozen +
    # --windowed), redirect them to the logger so a stray print() can't
    # raise trying to write to a None stream.
    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    else:
        sys.stdout = _StreamToLogger(logger, logging.INFO)

    if sys.stderr is None:
        sys.stderr = _StreamToLogger(logger, logging.ERROR)

    # Catch anything that slips through as an uncaught exception
    def _log_uncaught(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _log_uncaught

    logger.info("Logging initialized. Log file: %s", LOG_FILE)
    return logger


def get_logger(name=None):
    """Get a child logger, e.g. get_logger(__name__), after setup_logging() has run."""
    base = logging.getLogger("msfs_startup_manager")
    if name:
        return base.getChild(name)
    return base
