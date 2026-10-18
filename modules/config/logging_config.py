#!/usr/bin/env python3
# modules/config/logging_config.py
# Centralised logging configuration for Linux Media Downloader.
#
# Logs go to BOTH the console and a rotating file at <data dir>/logs/app.log so a
# download's full lifecycle (request -> yt-dlp activity -> result/errors) is
# captured for review even after the window closes.

import os
import logging
from logging.handlers import RotatingFileHandler

from modules.config import paths

LOG_DIR = paths.LOG_DIR
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

_LOG_FORMAT = '%(asctime)s [%(levelname)-7s] %(name)s: %(message)s'
_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

_configured = False


def setup_logging(level=None):
    """Configure root logging once. Safe to call multiple times.

    Level can be overridden via the LMD_LOG_LEVEL environment variable
    (e.g. LMD_LOG_LEVEL=DEBUG) or the ``level`` argument.
    """
    global _configured
    if _configured:
        return logging.getLogger('lmd')

    if level is None:
        level_name = os.environ.get('LMD_LOG_LEVEL', 'INFO').upper()
        level = getattr(logging, level_name, logging.INFO)

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if some other code already configured the root.
    root.handlers = [console, file_handler]

    _configured = True
    logging.getLogger('lmd').info('Logging initialised (level=%s, file=%s)',
                                  logging.getLevelName(level), LOG_FILE)
    return logging.getLogger('lmd')


class YTDLPLogger:
    """Adapter that routes yt-dlp's internal messages into our logger."""

    def __init__(self, logger=None, on_error=None):
        self._log = logger or logging.getLogger('lmd.ytdlp')
        self._on_error = on_error  # called with each error line (the download records them)

    def debug(self, msg):
        # yt-dlp sends both debug and info lines to debug(); '[debug]'-prefixed
        # ones are genuinely debug-level.
        if msg.startswith('[debug] '):
            self._log.debug(msg)
        else:
            self._log.info(msg)

    def info(self, msg):
        self._log.info(msg)

    def warning(self, msg):
        self._log.warning(msg)

    def error(self, msg):
        self._log.error(msg)
        if self._on_error:
            self._on_error(msg)
