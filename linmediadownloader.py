#!/usr/bin/env python3
# linmediadownloader.py
"""LinMediaDownloader 2.0 entry point: logging, the app's icons, then the GTK 4
window. (Replaces 1.x's app.py / browser_app.py on this branch.)

    python3 linmediadownloader.py
"""

import sys

from modules.config.logging_config import setup_logging
from ui import icons
from ui.app import App


def main(argv=None):
    setup_logging()
    icons.register()
    return App().run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
