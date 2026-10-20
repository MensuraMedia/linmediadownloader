# ui/app.py
"""The Gtk.Application: one instance (a second launch presents the existing
window), the app actions and their accelerators.

Actions: app.download (Ctrl+Return), app.cancel (Escape, only while a download
runs), app.focus-link (Ctrl+L), app.quit (Ctrl+Q). Page switching stays with the
shell's Alt+1…Alt+5. The panel icon (ui/tray.py) hides and shows the window; closing
the window while a download runs or waits hides it there instead of quitting.
"""

import logging
import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from modules.download import jobs  # noqa: E402
from ui import messages  # noqa: E402
from ui.tray import Tray  # noqa: E402
from ui.window import MainWindow  # noqa: E402

APP_ID = "org.mensuramedia.LinMediaDownloader"
# The app icon (resources/icons/hicolor/scalable/apps/<APP_ID>.svg). Installed copies live in
# ~/.local/share/icons (packaging/install-menu.sh); the repo's folder is searched too, so a
# window started straight from a checkout still shows it in the panel and Alt+Tab.
ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "icons")
logger = logging.getLogger("lmd.ui.app")


class App(Gtk.Application):
    def __init__(self, application_id=APP_ID):
        # Default flags: a second launch of the same id activates the primary
        # instance instead (do_activate then presents the window that exists).
        super().__init__(application_id=application_id)
        self.tray = None
        self._told_hidden = False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.IconTheme.get_for_display(display).add_search_path(ICON_DIR)
        Gtk.Window.set_default_icon_name(APP_ID)  # panel, Alt+Tab and the window's own icon
        for name, handler, accels in (
            ("download", self._download, ["<Primary>Return"]),
            ("cancel", self._cancel, ["Escape"]),
            ("focus-link", self._focus_link, ["<Primary>l"]),
            ("quit", lambda *_a: self.quit(), ["<Primary>q"]),  # quits even while hidden
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)

    def do_activate(self):
        window = self._window()
        if window is None:
            window = MainWindow(self)
            logger.info("window opened")
            # connected after the pages' own handlers; returning True keeps the window
            window.connect("close-request", self._on_close)
            self._start_tray(window)
        window.present()
        if self.tray is not None:
            self.tray.window_changed()

    def _window(self):
        """The main window, shown or hidden in the panel"""
        windows = [w for w in self.get_windows() if isinstance(w, MainWindow)]
        return windows[0] if windows else None

    # -- the panel icon
    def _start_tray(self, window):
        if os.environ.get("LMD_NO_TRAY"):
            return
        words = {
            "title": messages.APP_NAME,
            "show": messages.TRAY_SHOW,
            "hide": messages.TRAY_HIDE,
            "quit": messages.TRAY_QUIT,
            "idle": messages.TRAY_IDLE,
        }
        self.tray = Tray(
            APP_ID,
            ICON_DIR,
            words,
            on_toggle=self._toggle_window,
            on_quit=self.quit,
            is_shown=lambda: bool(self._window() and self._window().get_visible()),
        )
        window.tray = self.tray

    def _toggle_window(self):
        window = self._window()
        if window is None:
            return
        if window.get_visible() and window.is_active():
            window.set_visible(False)
        else:
            window.present()

    def _on_close(self, window):
        """Closing while a download runs or waits hides the window to the panel icon, so
        the download goes on; otherwise the app quits as before."""
        if self.tray is None or not self.tray.available or not self._busy(window):
            return False
        window.set_visible(False)
        self.tray.window_changed()
        if not self._told_hidden:
            self._told_hidden = True
            note = Gio.Notification.new(messages.TRAY_HIDDEN_TITLE)
            note.set_body(messages.TRAY_HIDDEN_BODY)
            self.send_notification("hidden-to-panel", note)
        logger.info("window hidden to the panel icon; the download goes on")
        return True

    @staticmethod
    def _busy(window):
        if window.download_page.state == "downloading":
            return True
        try:
            return any(job.get("status") in ("queued", "active") for job in jobs.queue_snapshot())
        except Exception:
            return False

    # -- action handlers
    def _download(self, *_a):
        self._window().download_page.start_download()

    def _cancel(self, *_a):
        # Escape does nothing unless a download is running (easy exit, harmless rest)
        self._window().download_page.cancel_running_download()

    def _focus_link(self, *_a):
        self._window().download_page.focus_link()

    def do_shutdown(self):
        if self.tray is not None:
            self.tray.stop()
        Gtk.Application.do_shutdown(self)
