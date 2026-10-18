# ui/app.py
"""The Gtk.Application: one instance (a second launch presents the existing
window), the app actions and their accelerators.

Actions: app.download (Ctrl+Return), app.cancel (Escape, only while a download
runs), app.focus-link (Ctrl+L), app.quit (Ctrl+Q). Page switching stays with the
shell's Alt+1…Alt+4.
"""

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

from ui.window import MainWindow  # noqa: E402

APP_ID = "org.mensuramedia.LinMediaDownloader"
logger = logging.getLogger("lmd.ui.app")


class App(Gtk.Application):
    def __init__(self, application_id=APP_ID):
        # Default flags: a second launch of the same id activates the primary
        # instance instead (do_activate then presents the window that exists).
        super().__init__(application_id=application_id)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        for name, handler, accels in (
            ("download", self._download, ["<Primary>Return"]),
            ("cancel", self._cancel, ["Escape"]),
            ("focus-link", self._focus_link, ["<Primary>l"]),
            ("quit", lambda *_a: self.quit(), ["<Primary>q"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = MainWindow(self)
            logger.info("window opened")
        window.present()

    # -- action handlers
    def _download(self, *_a):
        self.props.active_window.download_page.start_download()

    def _cancel(self, *_a):
        # Escape does nothing unless a download is running (easy exit, harmless rest)
        self.props.active_window.download_page.cancel_running_download()

    def _focus_link(self, *_a):
        self.props.active_window.download_page.focus_link()
