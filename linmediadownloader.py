#!/usr/bin/env python3
# linmediadownloader.py
"""LinMediaDownloader 2.0 entry point: logging, the app's icons, then the GTK 4
window. (Replaces 1.x's app.py / browser_app.py on this branch.)

    python3 linmediadownloader.py

Everything worth knowing when something goes wrong lands in one rotating log,
<data dir>/logs/app.log (~/.local/share/linmediadownloader/logs/app.log): the
environment at start-up, every download from start to the saved files, and any
exception, including those raised in worker threads or GTK callbacks.
"""

import logging
import platform
import shutil
import sys
import threading

from modules.config import paths
from modules.config.logging_config import LOG_FILE, setup_logging
from ui import icons
from ui.app import App

logger = logging.getLogger("lmd.app")


def log_environment():
    """One block at start-up: versions and paths a bug report needs"""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    try:
        import yt_dlp

        ytdlp = yt_dlp.version.__version__
    except Exception as e:  # the chip says so too; the log keeps the reason
        ytdlp = f"missing ({e})"
    from lintheme import __version__ as kit
    from modules.download import access

    found = access.current(refresh=True).describe()
    logger.info(
        "LinMediaDownloader start | Python %s | GTK %d.%d.%d | PyGObject %s | yt-dlp %s | kit %s | "
        "ffmpeg %s | YouTube sign-in: %s | JS runtime: %s | data %s | log %s",
        platform.python_version(),
        Gtk.get_major_version(),
        Gtk.get_minor_version(),
        Gtk.get_micro_version(),
        gi.__version__,
        ytdlp,
        kit,
        shutil.which("ffmpeg") or "missing",
        found["browser"] or "none",
        found["js_runtime"] or "none",
        paths.DATA_DIR,
        LOG_FILE,
    )


def log_uncaught_exceptions():
    """Exceptions nobody catches go to the log, not only to a terminal nobody sees"""

    def on_main(exc_type, exc, tb):
        logger.critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    def on_thread(args):
        logger.critical(
            "Uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = on_main  # PyGObject routes exceptions from GTK callbacks here too
    threading.excepthook = on_thread


def main(argv=None):
    from gi.repository import GLib

    from ui.app import APP_ID

    # The window class must be the app id, so the desktop matches windows to the menu
    # entry (StartupWMClass) and shows its icon in the panel and in Alt+Tab
    GLib.set_prgname(APP_ID)
    setup_logging()
    log_uncaught_exceptions()
    log_environment()
    icons.register()
    status = App().run(argv if argv is not None else sys.argv)
    logger.info("LinMediaDownloader exit (status %s)", status)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
