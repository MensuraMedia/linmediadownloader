# ui/window.py
"""The app window: the kit's dashboard shell (header + status chip + rail + pages)
with this app's four destinations: Download, Activity and Library are real pages;
Settings stays a placeholder until its phase. The window owns the status chip:
`window.chip.set_status(text, key)` takes the whole sentence and a kit status key
(the kit's own chip composes "device · word", which cannot say "Reading ·
the link"), so every chip text the app shows stays in one place: ui/messages.py.
"""

import os
import shutil

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from lintheme import status  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from lintheme.gtk4.shell import DashboardWindow  # noqa: E402
from ui import icons, messages, style  # noqa: E402
from ui.pages.activity import ActivityPage  # noqa: E402
from ui.pages.download import DownloadPage  # noqa: E402
from ui.pages.library import LibraryPage  # noqa: E402

# The app's own icons (rail, cards) must resolve however the window is created
# (entry point, tests, tools/shot_states.py); registering twice is harmless.
icons.register()


def tools_chip():
    """The start-up tools check: yt-dlp importable and ffmpeg on PATH"""
    try:
        __import__("yt_dlp")
    except ImportError:
        return messages.CHIP_TOOLS_NO_YTDLP, "attention"
    if shutil.which("ffmpeg") is None:
        return messages.CHIP_TOOLS_NO_FFMPEG, "attention"
    return messages.CHIP_TOOLS_OK, "ok"


class AppStatusChip(kit.StatusChip):
    """The kit's chip, with set_status(text, key) taking the full sentence.

    Reuses the kit's lt-chip styling, status icons and accessible-name bookkeeping;
    only the wording differs (word first, then the detail: "Downloading · 2 of 7").
    The pill shows the first word of the sentence only ("Ready", "Downloading"); the full
    sentence stays as the tooltip and the accessible name.
    """

    def __init__(self, *args, **kwargs):
        self._full_text, self._key, self._compact = "", "none", False
        super().__init__(*args, **kwargs)  # calls set_status, which renders

    def set_status(self, text, key):  # noqa: F811 - the kit's signature is (device, key, detail)
        self._full_text, self._key = text, key
        self._render()

    def set_compact(self, compact):
        """Narrow window: the word only ("Ready"), so the chip stops squeezing to 'y…y'"""
        if compact != self._compact:
            self._compact = compact
            self._render()

    def _render(self):
        text, key = self._full_text, self._key
        for css_class in ("lt-ok", "lt-busy", "lt-attention", "lt-error"):
            kit.uncss(self, css_class)
        kit.css(self, status.status(key).css)
        child = self._box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._box.remove(child)
            child = nxt
        self._box.append(kit.status_icon(key, 18))
        # The pill shows only the word that starts each sentence ("Ready", "Downloading");
        # the whole sentence stays as tooltip and accessible name.
        shown = text.split(" · ", 1)[0] or status.status(key).word
        words = Gtk.Label(label=shown)
        words.set_ellipsize(2)  # middle: keeps the status word and the start of the detail
        words.set_max_width_chars(40)
        self._box.append(words)
        kit.name(self, f"Status: {text}")
        self.set_tooltip_text(text)


class MainWindow(DashboardWindow):
    def __init__(self, application):
        super().__init__(application, messages.APP_NAME, "download-simple")
        style.install()  # after the shell: the display is open, the window class exists
        self.set_default_size(1200, 800)
        self._tools = tools_chip()

        self.download_page = DownloadPage(self)
        # Escape cancels a running download only: while the app action is disabled the key
        # stays free for dialogs, popovers and the folder chooser.
        cancel = application.lookup_action("cancel") if application else None
        if cancel is not None:
            self.download_page.on_state(lambda state: cancel.set_enabled(state == "downloading"))
        self.add_page("download", messages.PAGE_DOWNLOAD, "download-simple", self.download_page)
        self.activity_page = ActivityPage(self)
        self.add_page("activity", messages.PAGE_ACTIVITY, "clock-counter-clockwise", self.activity_page)
        self.library_page = LibraryPage(self)
        self.add_page("library", messages.PAGE_LIBRARY, "music-notes", self.library_page)
        self.add_page(
            "settings",
            messages.PAGE_SETTINGS,
            "gear-six",
            self._placeholder(messages.PAGE_SETTINGS, "gear-six"),
            bottom=True,
        )
        self._swap_chip()
        self._rehome_rail_badges()
        # A narrow header squeezes the chip to ellipses; the word alone still says the state
        self.on_layout(lambda mode: self.chip.set_compact(mode == "compact"))
        self.show_page("download")

    def _rehome_rail_badges(self):
        """The kit draws the count badge inside the icon's own 24 px overlay, where
        it lands on the glyph; the mockups pin it to the top right of the whole
        item, so every badge moves to an overlay around the icon+label column."""
        for page_id, item in self.rail._items.items():
            badge = self.rail._badges.get(page_id)
            if badge is None or not isinstance(badge.get_parent(), Gtk.Overlay):
                continue
            icon_overlay = badge.get_parent()
            column = item.get_child()
            icon_overlay.remove_overlay(badge)
            wrap = Gtk.Overlay()
            item.set_child(wrap)
            wrap.set_child(column)
            badge.set_halign(Gtk.Align.END)
            badge.set_valign(Gtk.Align.START)
            badge.set_margin_top(2)
            badge.set_margin_end(2)
            wrap.add_overlay(badge)

    def open_in_library(self, files, folder):
        """'Play in Library' after a download: a playlist folder opens as that playlist;
        a single file in the download folder opens under All files and starts playing"""
        self.show_page("library")
        if len(files) == 1 and not os.path.dirname(files[0]).endswith("_playlist"):
            self.library_page.show_file(files[0])
        elif folder:
            self.library_page.select_by_path(folder)

    def show_page(self, page_id):
        super().show_page(page_id)
        if page_id == "library":
            # "Play in Library" lands on the folder of the last download
            self.library_page.select_by_path(getattr(self.download_page, "_done_folder", ""))

    @staticmethod
    def _placeholder(label, icon_name):
        page = kit.css(Gtk.Box(), "lt-page")
        page.set_vexpand(True)
        page.append(kit.EmptyState(icon_name, label, messages.COMING_LATER))
        return page

    def _swap_chip(self):
        """Replace the shell's chip with one that takes full sentences; it keeps its
        place at the right of the header and opens Settings when clicked."""
        header = self.get_titlebar()
        header.remove(self.chip)
        self.chip = AppStatusChip(on_click=lambda: self.show_page("settings"))
        header.pack_end(self.chip)
        self.reset_chip()

    def set_chip(self, text, key):
        """Show a status sentence with a kit status key (icon + word + detail)"""
        self.chip.set_status(text, key)

    def reset_chip(self):
        """Back to the start-up tools status"""
        self.set_chip(*self._tools)
