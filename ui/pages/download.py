# ui/pages/download.py
"""The Download page: the one job of the app. Two panes (options left, preview or
progress right) at 960 px and above; one scrolling column with the preview folded
into a strip below that. States: empty, reading, ready, downloading, done, plus
the shared "can't reach" view for a failed read or download.

Threads: link reads run preview.preview_link in a worker thread and come back
with GLib.idle_add; downloads run in the jobs module's own threads and are only
observed here, on the main loop, through the snapshot poller.
"""

import logging
import os
import re
import threading
import time
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from modules.config import settings  # noqa: E402
from modules.download import access, jobs, preview  # noqa: E402
from modules.utils import file_utils  # noqa: E402
from ui import messages  # noqa: E402
from ui.poller import ACTIVE_STATUSES, SnapshotPoller, snapshot_copy  # noqa: E402
from ui.widgets.ring import ProgressRing  # noqa: E402
from ui.widgets.track_list import TrackList  # noqa: E402

logger = logging.getLogger("lmd.ui.download")

C = tokens.COLOR
TYPE_DELAY_MS = 600  # reading starts this long after typing stops
OPTIONS_WIDE_W = tokens.LAYOUT["options_min"]  # the options column never gets narrower
AUDIO_BYTES_PER_SECOND = 24_000  # 192 kbps CBR audio, for "about N MB" estimates


# ---------------------------------------------------------------- formatting
def fmt_size(n):
    """1.4 MB · 31 MB · 1.2 GB; '' when unknown"""
    if not n or n <= 0:
        return ""
    mb = n / 1_000_000
    if mb >= 1000:
        return f"{mb / 1000:.1f} GB"
    if mb >= 10:
        return f"{round(mb)} MB"
    return f"{mb:.1f} MB"


def fmt_speed(n):
    return f"{fmt_size(n)}/s" if n else ""


def fmt_eta_left(sec):
    """'1 s' · '3 min' · '1 h 4 min'; '' when unknown"""
    sec = int(sec or 0)
    if sec <= 0:
        return ""
    hours, rest = divmod(sec, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min"
    return f"{seconds} s"


def fmt_elapsed(sec):
    """'12 s' · '3 min 41 s' · '1 h 2 min'"""
    sec = int(sec or 0)
    hours, rest = divmod(sec, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {seconds} s"
    return f"{seconds} s"


def minutes_words(sec):
    """'45 min' · '1 h 12 min', for a playlist's total length"""
    if not sec:
        return ""
    total = round(sec / 60)
    if total < 60:
        return f"{total} min"
    return f"{total // 60} h {total % 60} min"


def tilde(path):
    """Show the home folder as ~"""
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path and home and path.startswith(home + os.sep):
        return "~" + path[len(home) :]
    return path or ""


def site_name(url):
    """The site a link points at, for the chip: 'YouTube', or the host, or 'the site'"""
    host = (urlparse(url or "").netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    if host.endswith("youtube.com") or host == "youtu.be":
        return "YouTube"
    return host or messages.SITE_FALLBACK


def display_name(title):
    """The plain name for the heading above the ring: no symbols (✔, emoji) and no trailing
    bracketed tags like "(Complete)" or "[HD]", which read like a status there"""
    import unicodedata

    name = "".join(ch for ch in title or "" if not unicodedata.category(ch).startswith(("So", "Sk", "Cs")))
    previous = None
    while previous != name:  # "Title (Complete) [HD]" -> "Title"
        previous = name
        name = re.sub(r"\s*[\(\[\{][^\)\]\}]*[\)\]\}]\s*$", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip(" -–—|·")
    return name or (title or "").strip()


def audio_estimate_mb(entries):
    seconds = sum(e.get("duration") or 0 for e in entries or [])
    return seconds * AUDIO_BYTES_PER_SECOND / 1_000_000


# ---------------------------------------------------------------- widgets
class IconSegmented(Gtk.Box):
    """A kit Segmented whose buttons carry a Phosphor icon beside the label
    (lintheme's Segmented takes plain labels; the mockups show icons). Same
    lt-seg classes and radio semantics."""

    def __init__(self, options, active=None, on_change=None, accessible_name=""):
        super().__init__(spacing=kit.SEG_GAP)
        kit.css(self, "lt-seg")
        self._buttons = {}
        group = None
        for value, label, icon_name in options:
            btn = Gtk.ToggleButton(group=group)
            group = group or btn
            btn.set_child(kit.hbox(kit.icon(icon_name, 18), Gtk.Label(label=label), spacing=8))
            self._buttons[value] = btn
            self.append(btn)
        self.set_value(active if active is not None else options[0][0])
        for value, btn in self._buttons.items():
            btn.connect(
                "toggled",
                lambda toggled, v=value: toggled.get_active() and on_change and on_change(v),
            )
        if accessible_name:
            kit.name(self, accessible_name)

    def get_value(self):
        return next((v for v, b in self._buttons.items() if b.get_active()), None)

    def set_value(self, value):
        if value in self._buttons:
            self._buttons[value].set_active(True)


def button_with_icon_hint(label, icon_name, hint, kind=None, big=False, on_click=None):
    """A kit button with an icon and a shortcut hint inside it (with_shortcut
    drops an icon button's child, so the pieces are composed here in order)."""
    btn = kit.button(label, on_click=on_click, kind=kind, big=big)
    if hint:
        kit.with_shortcut(btn, hint)
        box = btn.get_child()
        box.prepend(kit.icon(icon_name, 20, C["on_accent"] if kind == "primary" else None))
    else:
        btn.set_child(
            kit.hbox(
                kit.icon(icon_name, 18, C["on_accent"] if kind == "primary" else None),
                Gtk.Label(label=label),
                spacing=8,
            )
        )
    return btn


def clear_children(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def caption_label(row):
    """A kit SwitchRow's description label (the second label inside it)"""
    words = row.get_first_child()
    title = words.get_first_child() if words else None
    return title.get_next_sibling() if title is not None else None


# ---------------------------------------------------------------- the page
class DownloadPage(Gtk.Box):
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        changed = getattr(self, "_state", None) != value
        self._state = value
        if changed:
            for listener in self._state_listeners:
                listener(value)

    def on_state(self, listener):
        """listener(state) now and on every change (the app enables Escape only while downloading)"""
        self._state_listeners.append(listener)
        listener(self._state)

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window

        # view state
        self._state_listeners = []
        self._done_files, self._done_folder = [], ""
        self.state = "empty"  # empty | reading | ready | error | downloading | done
        self.preview = None
        self.preview_error = None
        self._last_error_title = ""
        self._read_generation = 0
        self._typing_timer = None
        self._setting_text = False
        self._mode = "wide"
        self._strip_open = False
        self._more_open = False
        self._rows_job = None
        self._done_folder = ""

        # options (the page's choices; jobs.normalize_options validates on submit)
        self.download_type = "audio"
        self.quality = jobs.DEFAULT_VIDEO_QUALITY
        self.playlist_choice = "all"  # single | all | first
        self.limit_value = 0
        self.skip_long = False
        self.ignore_dupes = False
        self.split_chapters = False
        self.folder = settings.default_download_path

        # download tracking
        self._submitted = {}  # job_id -> meta captured at submit
        self._active = None
        self._cancel_requested = False
        self.poller = SnapshotPoller(self.apply_snapshot)

        self._build()
        window.on_layout(self._on_layout)
        self._apply_state()
        # a download that was already running before the window opened
        try:
            snap = snapshot_copy()
            if snap.get("status") in ACTIVE_STATUSES or snap.get("queue_pending"):
                self.poller.start()
        except Exception:
            logger.exception("could not read the initial download state")

    # ================================================================ build
    def _build(self):
        content = Gtk.Box()
        content.set_homogeneous(True)  # options and tracks share the width equally (user, 2026-10-18)
        content.set_hexpand(True)
        content.set_vexpand(True)
        self.left_scroll = kit.scrolled(self._build_left_column())
        self.left_scroll.set_hexpand(True)
        self.left_scroll.set_size_request(OPTIONS_WIDE_W, -1)
        content.append(self.left_scroll)
        content.append(self._build_right_pane())
        self.append(content)
        self.actionbar = kit.ActionBar()
        self.append(self.actionbar)
        self.primary_btn = None

    def _build_left_column(self):
        self._col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        kit.css(self._col, "lt-pane")
        self.left_stack = Gtk.Stack()
        self.left_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.left_stack.set_transition_duration(tokens.MOTION["state_ms"])
        self.left_stack.add_named(self._build_options_stack(), "options")
        self.left_stack.add_named(self._build_progress_stack(), "progress")
        self.left_stack.add_named(self._build_result_stack(), "result")
        self._col.append(self.left_stack)
        return self._col

    # -- options column
    def _build_options_stack(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self.link_card = kit.Card(messages.CARD_LINK, action=(messages.CLEAR, self._clear_link))
        self.link_entry = kit.entry(
            placeholder=messages.LINK_PLACEHOLDER,
            accessible_name=messages.LINK_NAME,
            width_chars=24,
        )
        self.link_entry.set_hexpand(True)
        self.link_entry.connect("changed", self._on_link_changed)
        self.link_entry.connect("activate", lambda *_a: self._read_now())
        paste = kit.button(messages.PASTE, on_click=self._paste_link, icon_name="clipboard-text")
        self.link_card.add_row(kit.hbox(self.link_entry, paste))
        self.link_status = Gtk.Box(spacing=8)
        self.link_card.add_row(self.link_status)
        self.access_note = kit.text("", "lt-caption", wrap=True)  # whose YouTube sign-in is used
        self.access_note.set_visible(False)
        self.link_card.add_row(self.access_note)
        box.append(self.link_card)
        # The narrow-mode strip sits right under the Link card, visible without scrolling
        box.append(self._build_strip_card())

        self.format_card = kit.Card(messages.CARD_FORMAT)
        self.format_seg = IconSegmented(
            [
                ("audio", messages.FORMAT_AUDIO, "music-note"),
                ("video", messages.FORMAT_VIDEO, "film-strip"),
            ],
            "audio",
            self._on_format_changed,
            messages.FORMAT_NAME,
        )
        self.rate_caption = kit.text(messages.AUDIO_RATE, "lt-caption")
        self.rate_caption.set_valign(Gtk.Align.CENTER)
        self.format_card.add_row(kit.hbox(self.format_seg, self.rate_caption, expand_last=True))
        self.quality_seg = kit.Segmented(
            [
                ("1080", messages.QUALITY_1080),
                ("720", messages.QUALITY_720),
                ("480", messages.QUALITY_480),
            ],
            self.quality,
            self._on_quality_changed,
            messages.QUALITY_NAME,
        )
        self.quality_row = kit.field_row(messages.FIELD_QUALITY, self.quality_seg)
        self.quality_row.set_visible(False)
        self.format_card.add_row(self.quality_row)
        box.append(self.format_card)

        self.playlist_card = kit.Card(messages.CARD_PLAYLIST)
        self.get_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.skip_long_row = kit.SwitchRow(messages.SKIP_LONG, " ", False, self._on_skip_long_toggled)
        self.dupes_row = kit.SwitchRow(messages.IGNORE_DUPES, " ", False, self._on_dupes_toggled)
        self.playlist_card.add_row(self.get_controls)
        self.playlist_reason = kit.text("", "lt-caption")
        self.playlist_reason.set_visible(False)
        self.playlist_card.add_row(self.playlist_reason)
        self._rebuild_get_row(n=None)
        box.append(self.playlist_card)

        self.save_card = kit.Card(messages.CARD_SAVE)
        self.folder_label = kit.text(tilde(self.folder))
        folder_box = kit.css(
            kit.hbox(kit.icon("folder-simple", 18, C["text_muted"]), self.folder_label, spacing=8),
            "lt-entry",
        )
        folder_box.set_hexpand(True)
        kit.name(folder_box, messages.FOLDER_NAME)
        change = kit.button(messages.CHANGE, on_click=self._change_folder)
        # folder field takes the width the button leaves; the button stays natural-sized
        self.save_card.add_row(kit.hbox(folder_box, change))
        self.folder_note = kit.text(messages.PLAYLIST_FOLDER_NOTE, "lt-caption")
        self.folder_note.set_visible(False)
        self.save_card.add_row(self.folder_note)
        box.append(self.save_card)

        self.more_link = kit.button(messages.MORE_OPTIONS, on_click=self._toggle_more, kind="link")
        self.more_link.set_halign(Gtk.Align.START)
        box.append(self.more_link)
        self.split_row = kit.SwitchRow(
            messages.SPLIT_CHAPTERS, messages.SPLIT_CAPTION, False, on_toggle=self._on_split
        )
        self.split_row.set_visible(False)
        box.append(self.split_row)
        return box

    def _rebuild_get_row(self, n):
        """The 'Get' choices name the playlist's size, so the row is rebuilt per preview"""
        clear_children(self.get_controls)
        if n:
            options = [
                ("single", messages.GET_THIS_VIDEO),
                ("all", messages.GET_ALL.format(N=n)),
                ("first", messages.GET_FIRST),
            ]
            self.get_seg = kit.Segmented(
                options, self.playlist_choice, self._on_choice_changed, messages.GET_NAME
            )
            self.stepper = kit.Stepper(min(10, n), 1, n, self._on_limit_changed, messages.STEPPER_NAME)
            self.limit_value = self.stepper.get_value()
            self.stepper_holder = Gtk.Box()
            self.stepper_holder.append(self.stepper)
            self.stepper_holder.set_visible(self.playlist_choice == "first")
        else:
            options = [
                ("single", messages.GET_THIS_VIDEO),
                ("all", messages.GET_ALL_PLAIN),
                ("first", messages.GET_FIRST),
            ]
            self.get_seg = kit.Segmented(options, "all", None, messages.GET_NAME)
            self.stepper_holder = Gtk.Box()
            self.stepper = None
            self.limit_value = 0
        self.get_controls.append(kit.field_row(messages.FIELD_GET, self.get_seg))
        self.get_controls.append(self.stepper_holder)
        self.get_controls.append(self.skip_long_row)
        self.get_controls.append(self.dupes_row)

    # -- downloading column
    def _build_progress_stack(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self.ring_card = kit.Card()
        self.ring_card.set_valign(Gtk.Align.START)
        self.dl_title = kit.text("", "lt-heading")
        self.dl_title.set_halign(Gtk.Align.CENTER)
        self.ring = ProgressRing()
        self.ring.set_halign(Gtk.Align.CENTER)
        self.file_name = kit.text("", "lt-strong")
        self.file_pct = kit.text("", "lt-muted")
        self.file_bar = Gtk.ProgressBar()
        self.file_bar.set_hexpand(True)
        kit.name(self.file_bar, messages.CURRENT_FILE_NAME)
        self.file_caption = kit.text("", "lt-caption")
        self.ring_card.add_row(self.dl_title)
        self.ring_card.add_row(self.ring)
        file_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        file_block.append(kit.hbox(self.file_name, self.file_pct, expand_last=True))
        file_block.append(self.file_bar)
        file_block.append(self.file_caption)
        self.ring_card.add_row(file_block)
        box.append(self.ring_card)

        self.queue_card = kit.Card(messages.QUEUE_TITLE)
        self.queue_card.add_row(kit.text(messages.QUEUE_NOTE, "lt-caption"))
        self.queue_entry = kit.entry(
            placeholder=messages.LINK_PLACEHOLDER,
            accessible_name=messages.QUEUE_ENTRY_NAME,
            width_chars=24,
        )
        self.queue_entry.set_hexpand(True)
        queue_paste = kit.button(messages.PASTE, on_click=self._paste_queue, icon_name="clipboard-text")
        self.queue_card.add_row(kit.hbox(self.queue_entry, queue_paste))
        self.queue_message = kit.text("", "lt-caption")
        self.queue_card.add_row(self.queue_message)
        self.queue_card.add_row(kit.button(messages.ADD_TO_QUEUE, on_click=self._add_to_queue))
        box.append(self.queue_card)

        self.this_card = kit.Card(messages.THIS_DOWNLOAD)
        self.this_values = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.this_card.add_row(self.this_values)
        box.append(self.this_card)
        return box

    # -- done column
    def _build_result_stack(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self.done_card = kit.Card()
        self.done_card.set_valign(Gtk.Align.START)
        self.done_title = kit.text("", "lt-heading")
        self.done_title.set_halign(Gtk.Align.CENTER)
        self.done_ring = ProgressRing()
        self.done_ring.set_halign(Gtk.Align.CENTER)
        self.done_headline = kit.text("", "lt-title")
        self.done_headline.set_halign(Gtk.Align.CENTER)
        self.done_stats = kit.text("", "lt-muted")
        self.done_stats.set_halign(Gtk.Align.CENTER)
        self.link_entry.set_hexpand(True)  # Paste buttons keep their natural width
        self.done_saved = kit.text("", "lt-caption", wrap=True)  # the real file name(s) on disk
        self.done_saved.set_halign(Gtk.Align.CENTER)
        self.done_saved.set_selectable(True)
        play = self.done_play = kit.button(
            messages.PLAY_IN_LIBRARY,
            on_click=lambda: self.window.open_in_library(self._done_files, self._done_folder),
            icon_name="play",
        )
        self.done_show = kit.button(
            messages.SHOW_FILE, on_click=self._show_done_file, icon_name="folder-open"
        )
        activity = kit.button(
            messages.SEE_IN_ACTIVITY,
            on_click=lambda: self.window.show_page("activity"),
            icon_name="clock-counter-clockwise",
        )
        for widget in (
            self.done_title,
            self.done_ring,
            self.done_headline,
            self.done_stats,
            self.done_saved,
            kit.hbox(play, self.done_show, activity, spacing=8),
        ):
            self.done_card.add_row(widget)
        box.append(self.done_card)

        self.another_card = kit.Card(messages.ANOTHER_TITLE)
        self.another_entry = kit.entry(
            placeholder=messages.LINK_PLACEHOLDER,
            accessible_name=messages.LINK_NAME,
            width_chars=24,
        )
        self.another_entry.set_hexpand(True)
        self.another_entry.connect("activate", lambda *_a: self._use_another_link())
        # typing or Ctrl+V reads the link after a pause, exactly like the Link card's entry
        self.another_entry.connect("changed", self._on_another_changed)
        another_paste = self.another_paste_button = kit.button(
            messages.PASTE,
            on_click=lambda: self._paste_into(self.another_entry, then=self._use_another_link),
            icon_name="clipboard-text",
        )
        self.another_card.add_row(kit.hbox(self.another_entry, another_paste))
        self.another_note = kit.text("", "lt-caption")
        self.another_card.add_row(self.another_note)
        box.append(self.another_card)
        return box

    # -- right pane: preview, tracks or the problem
    def _build_right_pane(self):
        self.right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        kit.css(self.right, "lt-pane", "lt-pane-divider")
        self.right.set_hexpand(True)
        self.pane_title = kit.text(messages.PREVIEW, "lt-heading")
        self.pane_counts = kit.text("", "lt-muted")
        self.right.append(kit.hbox(self.pane_title, self.pane_counts, expand_last=True))

        self.right_stack = Gtk.Stack()
        self.right_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.right_stack.set_transition_duration(tokens.MOTION["state_ms"])
        self.right_stack.add_named(
            kit.EmptyState("link", messages.EMPTY_PREVIEW_TITLE, messages.EMPTY_PREVIEW_BODY),
            "empty",
        )
        self.track_list = TrackList()
        self.right_stack.add_named(self.track_list, "list")
        self.right_stack.add_named(self._build_error_pane(), "error")
        self.right_stack.set_visible_child_name("empty")
        self.right.append(self.right_stack)
        return self.right

    def _build_error_pane(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.error_banner_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(self.error_banner_holder)
        self.details = Gtk.Expander(label=messages.DETAILS)
        self.detail_text = kit.text("", "lt-mono", wrap=True, selectable=True)
        self.details.set_child(self.detail_text)
        box.append(self.details)
        return kit.scrolled(box)

    # -- narrow strip
    def _build_strip_card(self):
        self.strip = kit.css(Gtk.Box(spacing=12), "lt-card")
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        words.set_hexpand(True)
        self.strip_title = kit.text(messages.PREVIEW, "lt-heading")
        self.strip_counts = kit.text("", "lt-muted")
        words.append(self.strip_title)
        words.append(self.strip_counts)
        self.strip_button = kit.button(messages.SHOW_LIST, on_click=self._toggle_strip)
        self.strip.append(words)
        self.strip.append(self.strip_button)
        self.strip.set_visible(False)
        return self.strip

    # ================================================================ link reading
    def _on_link_changed(self, *_a):
        if self._setting_text:
            return
        if self._typing_timer is not None:
            GLib.source_remove(self._typing_timer)
        self._typing_timer = GLib.timeout_add(TYPE_DELAY_MS, self._typing_read)

    def _typing_read(self):
        self._typing_timer = None
        self._read_now()
        return False

    def _read_now(self):
        if self._typing_timer is not None:
            GLib.source_remove(self._typing_timer)
            self._typing_timer = None
        self.start_read(self.link_entry.get_text().strip())

    def start_read(self, url):
        """Read the link in a worker thread (Enter, Paste, or after typing stops)"""
        if self._typing_timer is not None:
            GLib.source_remove(self._typing_timer)
            self._typing_timer = None
        if not url:
            self._set_empty()
            return
        if (
            self.state in ("ready", "reading")
            and self.preview
            and self.preview.get("url") == url
            and not self.preview.get("error")
        ):
            return  # this link is already shown as a preview
        generation = self._read_generation = self._read_generation + 1
        self.state = "reading"
        self._apply_state()
        self.window.set_chip(messages.CHIP_READING, "busy")

        def worker():
            try:
                result = preview.preview_link(url, self.skip_long, self.ignore_dupes)
            except Exception as exc:  # a worker crash must not hang the page
                logger.exception("preview worker failed")
                result = {
                    "url": url,
                    "kind": "video",
                    "title": "",
                    "video_title": "",
                    "entries": [],
                    "error": {"kind": "unknown", "detail": str(exc)},
                }
            GLib.idle_add(self._read_finished, generation, url, result)

        threading.Thread(target=worker, daemon=True, name="lmd-preview").start()

    def _read_finished(self, generation, url, result):
        if generation != self._read_generation or self.link_entry.get_text().strip() != url:
            return False  # a stale answer for a link no longer in the entry
        if result.get("error"):
            self._enter_read_error(result)
        else:
            self.load_preview(result)
        return False

    def load_preview(self, result):
        """Show a successful read (also the entry point for fake data in tools and tests)."""
        self.preview, self.preview_error = result, None
        self._setting_text = True
        self.link_entry.set_text(result.get("url") or "")
        self._setting_text = False
        self._rebuild_get_row(
            n=len(result.get("entries") or []) if result.get("kind") == "playlist" else None
        )
        self.state = "ready"
        self._offer_split()
        self._apply_state()
        self.window.reset_chip()

    def _enter_read_error(self, result):
        self.preview, self.preview_error = None, result
        self.state = "error"
        self._apply_state()
        error = result.get("error") or {}
        self.window.set_chip(messages.CHIP_CANT_REACH.format(site=site_name(result.get("url"))), "error")
        self._show_error_pane(error.get("kind") or "unknown", error.get("detail") or "")

    def _set_empty(self):
        self.preview, self.preview_error = None, None
        self.state = "empty"
        self._apply_state()

    def _clear_link(self):
        self._setting_text = True
        self.link_entry.set_text("")
        self._setting_text = False
        self._read_generation += 1  # anything still in flight is stale now
        self._set_empty()

    # -- clipboard
    def use_link(self, url):
        """Another page hands the Download page a link (Try again / Use this link)"""
        if url:
            self._setting_text = True
            self.link_entry.set_text(url)
            self._setting_text = False
            self.start_read(url)

    def _paste_link(self):
        self._paste_into(self.link_entry, then=self._read_now)

    def _paste_queue(self):
        self._paste_into(self.queue_entry)

    def _paste_into(self, entry, then=None):
        def chosen(source, result):
            try:
                text = source.read_text_finish(result)
            except GLib.Error:
                logger.info("the clipboard could not be read as text")
                return
            if text:
                self._setting_text = True
                entry.set_text(text.strip())
                self._setting_text = False
                if then is not None:
                    then()

        self.get_display().get_clipboard().read_text_async(None, chosen)

    # ================================================================ options
    def _on_format_changed(self, value):
        self.download_type = value
        self.rate_caption.set_visible(value == "audio")
        self.quality_row.set_visible(value == "video")
        self._refresh_ready()

    def _on_quality_changed(self, value):
        self.quality = value

    def _on_choice_changed(self, value):
        self.playlist_choice = value
        self.stepper_holder.set_visible(value == "first")
        self._refresh_ready()

    def _on_limit_changed(self, value):
        self.limit_value = value
        self._refresh_ready()

    def _on_skip_long_toggled(self, active):
        self.skip_long = active
        self._remark_preview()

    def _on_dupes_toggled(self, active):
        self.ignore_dupes = active
        self._remark_preview()

    def _remark_preview(self):
        if not self.preview or self.state != "ready":
            return
        preview.apply_options(self.preview, self.skip_long, self.ignore_dupes)
        self._refresh_ready()

    def _on_split(self, active):
        self.split_chapters = bool(active)
        if self.state == "ready":
            self._refresh_ready()
            self.track_list.set_entries(self._scope_entries())

    def _chapters(self):
        """The parts of a single video (embedded chapters or a description tracklist)"""
        if not self.preview or self.preview.get("kind") == "playlist":
            return []
        return self.preview.get("chapters") or []

    def _offer_split(self):
        """After a read: a video with parts opens More options and says so; one without
        parts keeps the switch off and says why"""
        parts = self._chapters()
        words = self.split_row.get_first_child().get_last_child()  # the caption under the title
        if parts:
            self._more_open = True
            self.split_row.set_visible(True)
            self.split_row.set_sensitive(True)
            if isinstance(words, Gtk.Label):
                words.set_text(messages.SPLIT_FOUND.format(n=len(parts)))
        else:
            self.split_row.switch.set_active(False)
            self.split_row.set_sensitive(False)
            if isinstance(words, Gtk.Label):
                words.set_text(messages.SPLIT_NONE)

    def _toggle_more(self):
        self._more_open = not self._more_open
        self.split_row.set_visible(self._more_open)  # stays open until it is closed again

    def _toggle_strip(self):
        self._strip_open = not self._strip_open
        self._apply_strip()

    def _change_folder(self, *_a):
        dialog = Gtk.FileDialog()
        try:
            dialog.set_initial_folder(Gio.File.new_for_path(self.folder))
        except Exception:
            logger.debug("could not set the folder picker's start folder")
        dialog.select_folder(self.window, None, self._folder_chosen)

    def _folder_chosen(self, dialog, result):
        try:
            chosen = dialog.select_folder_finish(result)
        except GLib.Error as exc:
            logger.info("the folder picker was dismissed: %s", exc.message)
            return
        path = chosen.get_path() if chosen else None
        if path:
            self.folder = path
            self.refresh_save_card()
            if self.state == "ready":
                self.refresh_summaries()

    def refresh_save_card(self):
        self.folder_label.set_text(tilde(self.folder))
        is_playlist = bool(self.preview and self.preview.get("kind") == "playlist")
        self.folder_note.set_visible(is_playlist)

    # ================================================================ expected set
    def _scope_entries(self):
        """The entries the current choices look at (before skip filtering)"""
        if not self.preview:
            return []
        entries = self.preview.get("entries") or []
        parts = self._chapters()
        if parts and self.split_chapters:  # one video saved as its parts: the parts are the rows
            n = len(parts)
            return [
                {
                    "index": part["index"],
                    "id": part["id"],
                    "title": part.get("title") or messages.PART_NAME.format(i=part["index"], n=n),
                    "duration": part.get("duration"),
                    "skip": None,
                }
                for part in parts
            ]
        if self.preview.get("kind") != "playlist" or self.playlist_choice == "single":
            return entries[:1]
        if self.playlist_choice == "first" and self.limit_value:
            return entries[: self.limit_value]
        return entries

    def _expected_entries(self):
        return [e for e in self._scope_entries() if not e.get("skip")]

    @staticmethod
    def _entry_key(entry):
        return entry.get("id") or entry.get("title") or ""

    def _skip_counts(self):
        d = sum(1 for e in self._scope_entries() if e.get("skip") == "duplicate")
        l = sum(1 for e in self._scope_entries() if e.get("skip") == "long")
        return d, l

    def _potential_counts(self):
        """How many entries each switch could skip, for the captions beside them"""
        scratch = {"entries": [dict(e) for e in (self.preview or {}).get("entries") or []]}
        preview.apply_options(scratch, True, True)
        k_dupes = sum(1 for e in scratch["entries"] if e.get("skip") == "duplicate")
        k_long = sum(1 for e in scratch["entries"] if e.get("skip") == "long")
        return k_dupes, k_long

    # -- one source of truth while a download runs
    def _merged_track_view(self, tracks):
        """key -> {'state', 'progress'} for every row of the active download, merging the
        preview's marks with what the download itself reported: it re-checks duplicates,
        so it can find more than the preview did. Every count the page shows — ring,
        chip, action bar, "This download · Skipping", the done summary, "did not
        finish" — is computed from this one view, so they cannot disagree.

        An entry counts as skipped when the preview marked it OR the download reported
        skipped_long/skipped_duplicate for it; the expected files are the rest."""
        view = {}
        tracks = tracks or {}
        scope = (self._active or {}).get("scope")
        if scope is None:  # a link that was never previewed here: the tracks are the truth
            for key, track in tracks.items():
                state = track.get("state")
                if state not in ("done", "downloading", "processing", "skipped_long", "skipped_duplicate"):
                    state = "waiting"
                view[key] = {
                    "state": state,
                    "progress": track.get("progress") or 0 if state in ("downloading", "processing") else -1,
                    "size": track.get("size"),
                    "path": track.get("path"),
                }
            return view
        for entry in scope:
            key = self._entry_key(entry)
            track = tracks.get(key) or {}
            state = track.get("state")
            if state not in ("done", "downloading", "processing", "skipped_long", "skipped_duplicate"):
                if entry.get("skip") == "long":
                    state = "skipped_long"
                elif entry.get("skip") == "duplicate":
                    state = "skipped_duplicate"
                else:
                    state = "waiting"
            view[key] = {
                "state": state,
                "progress": track.get("progress") or 0 if state in ("downloading", "processing") else -1,
                "size": track.get("size"),
                "path": track.get("path"),
            }
        return view

    @staticmethod
    def _counts_from_view(view):
        """expected = entries − entries skipped, plus how many finished so far"""
        counts = {"total": 0, "done": 0, "downloading": 0, "waiting": 0, "dupes": 0, "long": 0, "skip": 0}
        for item in (view or {}).values():
            state = item["state"]
            if state == "done":
                counts["done"] += 1
                counts["total"] += 1
            elif state in ("downloading", "processing"):  # converting still counts as under way
                counts["downloading"] += 1
                counts["total"] += 1
            elif state == "skipped_duplicate":
                counts["dupes"] += 1
                counts["skip"] += 1
            elif state == "skipped_long":
                counts["long"] += 1
                counts["skip"] += 1
            else:
                counts["waiting"] += 1
                counts["total"] += 1
        return counts

    def _refresh_ready(self):
        """Repaint the whole ready view after anything that changes its numbers"""
        self.refresh_summaries()
        self.refresh_action_bar()

    # ================================================================ submitting
    def _options_for(self, url):
        is_playlist = bool(
            self.preview and self.preview.get("url") == url and self.preview.get("kind") == "playlist"
        )
        mode = "playlist" if is_playlist and self.playlist_choice in ("all", "first") else "single"
        limit = self.limit_value if is_playlist and self.playlist_choice == "first" else 0
        return {
            "output_dir": self.folder,
            "download_type": self.download_type,
            "playlist_mode": mode,
            "limit": limit,
            "skip_long": self.skip_long,
            "ignore_dupes": self.ignore_dupes,
            "split_chapters": self.split_chapters,
            "video_quality": self.quality,
        }

    def can_download(self):
        return self.state == "ready" and bool(self.preview)

    def start_download(self):
        """The one main action (the primary button, or Ctrl+Enter)"""
        if not self.can_download():
            return
        url = self.preview.get("url")
        options = self._options_for(url)
        try:
            result = jobs.submit_download(url, options)
        except Exception:
            logger.exception("submitting the download failed")
            return
        scope = self._scope_entries()  # every row to show (skips included), frozen at submit
        meta = {
            "job_id": result.get("job_id"),
            "url": url,
            "options": options,
            "title": self.preview.get("title") or "",
            "scope": scope,
            "started": None,
        }
        if meta["job_id"] is not None:
            self._submitted[meta["job_id"]] = meta
        if result.get("status") == "started":
            self._bind_active(meta, snapshot_copy())
            self.poller.start()
        else:
            self.poller.start()
            self._set_link_status(
                kit.status_line("busy", messages.QUEUED_AHEAD.format(position=result.get("position")))
            )
        logger.info("submitted %s (job %s, %s)", url, meta["job_id"], result.get("status"))

    def _add_to_queue(self):
        url = self.queue_entry.get_text().strip()
        if not url:
            kit.set_invalid(self.queue_entry, True, self.queue_message, messages.QUEUE_EMPTY)
            return
        kit.set_invalid(self.queue_entry, False, self.queue_message, "")
        options = self._options_for(url)
        try:
            result = jobs.submit_download(url, options)
        except Exception:
            logger.exception("queueing a second link failed")
            return
        meta = {
            "job_id": result.get("job_id"),
            "url": url,
            "options": options,
            "title": "",
            "started": None,
        }
        if meta["job_id"] is not None:
            self._submitted[meta["job_id"]] = meta
        self._setting_text = True
        self.queue_entry.set_text("")
        self._setting_text = False
        self.queue_message.set_text(messages.QUEUE_WAITING.format(n=max(result.get("position") or 1, 1)))
        self.poller.start()
        logger.info("queued %s (job %s)", url, result.get("job_id"))

    def _on_another_changed(self, *_a):
        if self._setting_text:
            return
        if self._typing_timer is not None:
            GLib.source_remove(self._typing_timer)
        self._typing_timer = GLib.timeout_add(TYPE_DELAY_MS, self._another_typed)

    def _another_typed(self):
        self._typing_timer = None
        self._use_another_link()
        return False

    def _use_another_link(self):
        """A link in "Download another": it becomes the Link card's link and is read, so the
        options and the Download button come back for it"""
        url = self.another_entry.get_text().strip()
        if not url:
            return
        self._setting_text = True
        self.link_entry.set_text(url)
        self.another_entry.set_text("")
        self._setting_text = False
        self.start_read(url)

    # ================================================================ snapshots
    def apply_snapshot(self, snap):
        """One poller snapshot, on the main loop (also the tools' and tests' entry point)."""
        self._update_badge(snap)
        status = snap.get("status")
        job_id = snap.get("job_id")
        if status in ACTIVE_STATUSES:
            bound = self._active or {}
            if self.state != "downloading" or bound.get("job_id") != job_id:
                meta = self._submitted.get(job_id) or self._fresh_meta(snap, job_id)
                self._bind_active(meta, snap)
            self._update_downloading(snap)
        elif status in ("completed", "completed_with_errors"):
            if self.state == "downloading":
                self._enter_done(snap)
        elif status == "error":
            if self.state == "downloading":
                url = (self._active or {}).get("url") or ""
                self._enter_download_error(
                    preview.classify_error(snap.get("message") or ""), snap.get("message") or "", url
                )
        elif status == "cancelled":
            if self.state == "downloading":
                self._return_to_ready()

    def _fresh_meta(self, snap, job_id):
        """A download this window never submitted (started before launch, or queued
        from the queue card): whatever is known comes from the snapshot."""
        return {
            "job_id": job_id,
            "url": "",
            "options": {"output_dir": snap.get("output_path") or "", "download_type": "audio"},
            "title": snap.get("playlist_title") or snap.get("current_file") or "",
            "started": time.monotonic(),
        }

    def _bind_active(self, meta, snap):
        self._active = meta
        self._cancel_requested = False
        if meta.get("started") is None:
            meta["started"] = time.monotonic()
        self.state = "downloading"
        self._apply_state()
        self._fill_this_download(meta)
        if self._rows_job != meta.get("job_id"):
            if meta.get("scope") is not None:
                self.track_list.set_entries(meta.get("scope") or [])
            else:  # a link that was never previewed here: rows come from the tracks
                self.track_list.set_raw(list((snap or {}).get("tracks", {}).items()))
            self._rows_job = meta.get("job_id")
        self._update_downloading(snap or {})

    def _fill_this_download(self, meta):
        options = meta.get("options") or {}
        if options.get("download_type") == "video":
            fmt_value = messages.FORMAT_VALUE_VIDEO.format(
                q=options.get("video_quality") or jobs.DEFAULT_VIDEO_QUALITY
            )
        elif options.get("download_type") == "audio":
            fmt_value = messages.FORMAT_VALUE_AUDIO
        else:
            fmt_value = ""
        saves = tilde(options.get("output_dir") or "")
        clear_children(self.this_values)
        self.this_skip_label = None
        grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        rows = [
            pair for pair in ((messages.KEY_FORMAT, fmt_value), (messages.KEY_SAVES_TO, saves)) if pair[1]
        ]
        for row, (key_text, value) in enumerate(rows):
            grid.attach(kit.text(key_text, "lt-muted", wrap=True), 0, row, 1, 1)
            value_label = kit.text(value, wrap=True)
            value_label.set_hexpand(True)
            value_label.set_xalign(1)
            value_label.set_justify(Gtk.Justification.RIGHT)
            grid.attach(value_label, 1, row, 1, 1)
        skip_row = len(rows)
        grid.attach(kit.text(messages.KEY_SKIPPING, "lt-muted", wrap=True), 0, skip_row, 1, 1)
        self.this_skip_label = kit.text(messages.SKIPPING_NONE, wrap=True)
        self.this_skip_label.set_hexpand(True)
        self.this_skip_label.set_xalign(1)
        self.this_skip_label.set_justify(Gtk.Justification.RIGHT)
        grid.attach(self.this_skip_label, 1, skip_row, 1, 1)
        self.this_values.append(grid)

    def _set_this_skipping(self, dupes, long):
        """The Skipping row follows the merged view: the download re-checks duplicates"""
        if getattr(self, "this_skip_label", None) is None:
            return
        if dupes and long:
            words = messages.SKIPPING_BOTH.format(d=dupes, l=long)
        elif dupes:
            words = messages.SKIPPING_DUPES.format(d=dupes)
        elif long:
            words = messages.SKIPPING_LONG.format(l=long)
        else:
            words = messages.SKIPPING_NONE
        self.this_skip_label.set_text(words)

    def _update_downloading(self, snap):
        tracks = snap.get("tracks") or {}
        view = self._merged_track_view(tracks)
        self.track_list.apply_states(view)
        counts = self._counts_from_view(view)
        total, done = counts["total"], counts["done"]
        audio = ((self._active or {}).get("options") or {}).get("download_type") == "audio"

        def share(item):
            """How far one track is: for MP3 the download is the first half, the conversion
            (often the longer part for long recordings) the second, so the ring keeps moving"""
            p = max(0.0, min(1.0, (item["progress"] or 0) / 100))
            if item["state"] == "downloading":
                return p * 0.5 if audio else p
            return 0.5 + p * 0.5 if audio else 1.0  # processing

        in_progress = max(
            (share(item) for item in view.values() if item["state"] in ("downloading", "processing")),
            default=0.0,
        )
        fraction = (done + in_progress) / total if total else 0.0
        if ((self._active or {}).get("options") or {}).get("split_chapters"):
            # The rows are the parts, made only after the whole video is downloaded and
            # converted: that first, longer stage is the first half of the ring.
            source = [t for key, t in tracks.items() if key not in view]
            if source:
                item = source[0]
                state = item.get("state")
                first = 1.0 if state == "done" else share({"state": state, "progress": item.get("progress")})
                fraction = 0.5 * first + 0.5 * (done / total if total else 0.0)
        index = min(done + 1, total) if total else 1
        self.ring.set_progress(fraction, done, total or index)
        self._set_this_skipping(counts["dupes"], counts["long"])

        title = snap.get("playlist_title") or (self._active or {}).get("title") or ""
        self.dl_title.set_text(display_name(title))
        converting = snap.get("phase") == "converting"
        name = snap.get("current_file") or title
        self.file_name.set_text(messages.CONVERTING_FILE.format(name=name) if converting else name)
        pct = snap.get("progress") or 0
        self.file_pct.set_text(f"{int(pct)}%" if snap.get("status") == "downloading" or converting else "")
        self.file_bar.set_fraction(max(0.0, min(1.0, pct / 100)))
        if converting:
            self.file_caption.set_text(messages.CONVERTING_CAPTION)
        elif snap.get("status") == "downloading":
            done_b = fmt_size(snap.get("downloaded_bytes"))
            total_b = fmt_size(snap.get("total_bytes"))
            speed = fmt_speed(snap.get("speed"))
            eta = fmt_eta_left(snap.get("eta"))
            if done_b and total_b and speed and eta:
                self.file_caption.set_text(
                    messages.FILE_CAPTION.format(done=done_b, total=total_b, speed=speed, eta=eta)
                )
            else:  # fragments only: never a dangling separator when one part is unknown
                parts = []
                if done_b and total_b:
                    parts.append(f"{done_b} of {total_b}")
                if speed:
                    parts.append(speed)
                if eta:
                    parts.append(messages.ETA_LEFT.format(eta=eta))
                self.file_caption.set_text(" · ".join(parts))
        else:
            self.file_caption.set_text(snap.get("message") or "")

        self._set_pane_counts(
            messages.TRACKS_COUNTS_ACTIVE.format(
                done=counts["done"],
                dl=counts["downloading"],
                wait=counts["waiting"],
                skip=counts["skip"],
            )
        )
        waiting = snap.get("queue_pending") or 0
        self.queue_message.set_text(messages.QUEUE_WAITING.format(n=waiting) if waiting else "")
        eta = fmt_eta_left(snap.get("eta"))
        words = (
            messages.AB_BUSY.format(i=index, M=total or index, eta=eta)
            if eta
            else messages.AB_BUSY_NO_ETA.format(i=index, M=total or index)
        )
        self.actionbar.busy(words, fraction)
        self.window.set_chip(messages.CHIP_DOWNLOADING.format(i=index, M=total or index), "busy")

    def _enter_done(self, snap):
        meta = self._active or {}
        view = self._merged_track_view(snap.get("tracks") or {})
        self.track_list.apply_states(view, final=True)
        counts = self._counts_from_view(view)
        total, done = counts["total"], counts["done"]
        missing = max(total - done, 0)
        started = meta.get("started")
        elapsed = fmt_elapsed(time.monotonic() - started) if started else ""
        options = meta.get("options") or {}
        if options.get("download_type") == "audio":
            done_keys = {key for key, item in view.items() if item["state"] == "done"}
            done_entries = [e for e in (meta.get("scope") or []) if self._entry_key(e) in done_keys]
            mb = audio_estimate_mb(done_entries)
            size = f"{round(mb)} MB" if mb >= 1 else fmt_size(mb * 1_000_000)
        else:
            size = ""
        word = messages.WORD_TRACK if done == 1 else messages.WORD_TRACKS
        self._set_this_skipping(counts["dupes"], counts["long"])  # the final view, not the last poll
        self.done_title.set_text(display_name(snap.get("playlist_title") or meta.get("title") or ""))
        self._nothing_saved = done == 0
        reason = self._failure_reason(snap) if self._nothing_saved else None
        if self._nothing_saved:  # never dress a failure up as a success
            self.done_ring.set_nothing()
            self.done_headline.set_text(messages.DONE_NOTHING)
        else:
            self.done_ring.set_complete(done)  # the end moment: full ring and check
            self.done_headline.set_text(messages.DONE_TRACKS.format(n=done, word=word))
        self.done_play.set_visible(not self._nothing_saved)
        if reason:
            self.done_stats.set_text(reason["title"])
        elif size and elapsed:
            self.done_stats.set_text(messages.DONE_STATS.format(size=size, time=elapsed))
        elif elapsed:
            self.done_stats.set_text(messages.DONE_STATS_TIME.format(time=elapsed))
        else:
            self.done_stats.set_text("")
        summary = (
            messages.FORMAT_SUMMARY_VIDEO
            if options.get("download_type") == "video"
            else messages.FORMAT_SUMMARY_AUDIO
        )
        extra = []
        if options.get("skip_long"):
            extra.append(messages.CHOICE_SKIP_LONG)
        if options.get("ignore_dupes"):
            extra.append(messages.CHOICE_IGNORE_DUPES)
        self.another_note.set_text(messages.ANOTHER_NOTE.format(choices=" · ".join([summary] + extra)))
        self._set_pane_counts(self._final_counts_words(counts, missing))

        self.state = "done"
        self._apply_state()
        folder = options.get("output_dir") or snap.get("output_path") or ""
        self._done_folder = folder
        self._done_files = [
            item["path"] for item in view.values() if item["state"] == "done" and item.get("path")
        ]
        if len(self._done_files) == 1:
            self.done_saved.set_text(messages.SAVED_AS.format(name=os.path.basename(self._done_files[0])))
        elif self._done_files:
            where = os.path.dirname(self._done_files[0])
            self.done_saved.set_text(
                messages.SAVED_FILES.format(n=len(self._done_files), folder=tilde(where))
            )
        else:
            self.done_saved.set_text("")
        self.done_saved.set_visible(bool(self._done_files))
        self.done_show.set_visible(bool(self._done_files))
        logger.info("download result: %d saved: %s", len(self._done_files), self._done_files)
        if self._nothing_saved:
            head = messages.AB_NOTHING.format(time=elapsed) if elapsed else messages.AB_NOTHING_NO_TIME
            caption = reason["body"] if reason else self._done_caption(counts, missing)
            if reason and reason["kind"] in ("bot_check", "rate_limited", "network"):
                site = site_name(meta.get("url"))
                self.window.set_chip(messages.CHIP_CANT_REACH.format(site=site), "error")
            else:
                self.window.reset_chip()
        else:
            head = (
                messages.AB_DONE.format(n=done, word=word, folder=tilde(folder), time=elapsed)
                if elapsed
                else messages.AB_DONE_NO_TIME.format(n=done, word=word, folder=tilde(folder))
            )
            caption = self._done_caption(counts, missing)
            self.window.reset_chip()
        # the plain two-line layout: the ring above already shows the result
        self.actionbar.idle(head, caption)
        self._update_badge(snap)
        if self.get_mapped():
            self.another_entry.grab_focus()
        logger.info("download finished: %d done, %d missing", done, missing)

    @staticmethod
    def _failure_reason(snap):
        """The plain-words reason for the newest yt-dlp error of this download, or None"""
        errors = snap.get("errors") or []
        if not errors:
            return None
        kind = preview.classify_error(errors[-1])
        copy = messages.ERRORS.get(kind) or messages.ERRORS["unknown"]
        return {"kind": kind, "title": copy["title"], "body": copy["body"]}

    def _show_access_note(self):
        """Say whose sign-in reached YouTube (cached by access.current(); no new browser scan)"""
        browser = access.current().describe()["browser"]
        self.access_note.set_text(
            messages.ACCESS_SIGNED_IN.format(browser=browser) if browser else messages.ACCESS_NONE
        )
        self.access_note.set_visible(True)

    def _show_done_file(self):
        """Open the folder with the saved file selected (the first, for a playlist)"""
        if self._done_files:
            file_utils.show_file(self._done_files[0])
        elif self._done_folder:
            file_utils.open_folder(self._done_folder)

    def _retry_download(self):
        """Run the same download again (after switching VPN server, for example)"""
        self._return_to_ready()
        self.start_download()

    @staticmethod
    def _done_caption(counts, missing):
        d, l = counts["dupes"], counts["long"]
        if d and l:
            words = messages.AB_DONE_CAPTION.format(d=d, l=l)
        elif d:
            words = messages.AB_DONE_CAPTION_DUPES.format(d=d)
        elif l:
            words = messages.AB_DONE_CAPTION_LONG.format(l=l)
        else:
            words = ""
        if missing:
            missed = messages.AB_DONE_CAPTION_MISSING.format(k=missing)
            words = f"{words}. {missed}" if words else missed
        return words

    @staticmethod
    def _final_counts_words(counts, missing):
        if missing:
            return messages.TRACKS_COUNTS_FINAL_MISSING.format(
                done=counts["done"], skip=counts["skip"], missing=missing
            )
        return messages.TRACKS_COUNTS_FINAL.format(done=counts["done"], skip=counts["skip"])

    def _return_to_ready(self):
        self._cancel_requested = False
        if self.preview:
            self.state = "ready"
            self._apply_state()
        else:
            self._set_empty()
        self.window.reset_chip()

    def cancel_running_download(self):
        """Cancel at once, without a confirm: nothing is destroyed, partial files stay"""
        if self.state != "downloading" or self._cancel_requested:
            return
        self._cancel_requested = True
        try:
            jobs.cancel_active_download()
        except Exception:
            logger.exception("cancelling failed")
            self._cancel_requested = False
            return
        if self.primary_btn is not None:
            self.primary_btn.set_sensitive(False)
        logger.info("cancel requested")

    def focus_link(self):
        entry = self.another_entry if self.state == "done" else self.link_entry
        entry.grab_focus()

    def _update_badge(self, snap):
        waiting = snap.get("queue_pending") or 0
        self.window.rail.set_badge(
            "activity", waiting or None, spoken=messages.BADGE_WAITING.format(n=waiting)
        )

    # ================================================================ error view
    def _enter_download_error(self, kind, detail, url):
        self.state = "error"
        self._apply_state()
        self.window.set_chip(messages.CHIP_CANT_REACH.format(site=site_name(url)), "error")
        self._show_error_pane(kind, detail)

    def _show_error_pane(self, kind, detail):
        copy = messages.ERRORS.get(kind) or messages.ERRORS["unknown"]
        self._last_error_title = copy["title"]
        clear_children(self.error_banner_holder)
        banner = kit.Banner(
            "error",
            "<b>{}</b>\n{}".format(
                GLib.markup_escape_text(copy["title"]), GLib.markup_escape_text(copy["body"])
            ),
            [(messages.TRY_AGAIN, self._try_again, None)],
        )
        self.error_banner_holder.append(banner)
        self.detail_text.set_text(detail or "")
        self.refresh_action_bar()

    def _try_again(self):
        url = self.link_entry.get_text().strip() or (self._active or {}).get("url") or ""
        if url:
            self.start_read(url)

    # ================================================================ state painting
    def _apply_state(self):
        """Lay out every part for the current state (called on each transition)"""
        self.refresh_link_status()
        self.refresh_playlist_card()
        self.refresh_save_card()
        self.refresh_summaries()
        self.refresh_action_bar()
        self._apply_left_stack()
        self._apply_right_stack()
        self._apply_strip()

    def _apply_left_stack(self):
        if self.state == "downloading":
            self.left_stack.set_visible_child_name("progress")
        elif self.state == "done":
            self.left_stack.set_visible_child_name("result")
        else:
            self.left_stack.set_visible_child_name("options")

    def _apply_right_stack(self):
        if self.state == "error":
            self.right_stack.set_visible_child_name("error")
        elif self.state in ("ready", "reading", "downloading", "done"):
            self.right_stack.set_visible_child_name("list")
        else:
            self.right_stack.set_visible_child_name("empty")

    def refresh_link_status(self):
        if self.state == "reading":
            spinner = Gtk.Spinner()
            spinner.start()
            self._set_link_status(kit.hbox(spinner, kit.text(messages.READING, "lt-muted"), spacing=8))
        elif self.state == "ready" and self.preview:
            counts = preview.summarize(self.preview)
            if self.preview.get("kind") == "playlist":
                detail = messages.FOUND_PLAYLIST_DETAIL.format(
                    title=self.preview.get("title") or "",
                    count=counts["count"],
                    duration=minutes_words(counts["seconds"]),
                )
                words = messages.PLAYLIST_FOUND
            else:
                entry = (self.preview.get("entries") or [{}])[0]
                detail = messages.FOUND_VIDEO_DETAIL.format(
                    title=self.preview.get("title") or "",
                    duration=minutes_words(entry.get("duration")),
                )
                if self._chapters():
                    detail += messages.FOUND_PARTS.format(n=len(self._chapters()))
                words = messages.VIDEO_FOUND
            self._set_link_status(
                kit.hbox(
                    kit.status_icon("ok", 16),
                    kit.text(words, "lt-ok-text"),
                    kit.text(detail, "lt-muted"),
                    spacing=6,
                )
            )
            self._show_access_note()
        elif self.state == "error":
            self._set_link_status(
                kit.hbox(
                    kit.status_icon("error", 16),
                    kit.text(messages.READ_FAILED, "lt-error-text"),
                    kit.text(messages.READ_FAILED_WHERE, "lt-muted"),
                    spacing=6,
                )
            )
        else:
            self._set_link_status(None)

    def _set_link_status(self, widget):
        clear_children(self.link_status)
        if widget is not None:
            self.link_status.append(widget)

    def refresh_playlist_card(self):
        is_playlist = bool(self.preview and self.preview.get("kind") == "playlist" and self.state == "ready")
        self.get_controls.set_sensitive(is_playlist)
        if is_playlist:
            self.playlist_reason.set_visible(False)
            k_dupes, k_long = self._potential_counts()
            self.skip_long_row.switch.set_active(self.skip_long)
            self.dupes_row.switch.set_active(self.ignore_dupes)
            self._set_caption(self.skip_long_row, messages.SKIP_LONG_CAPTION.format(k=k_long))
            self._set_caption(self.dupes_row, messages.IGNORE_DUPES_CAPTION.format(k=k_dupes))
            self.stepper_holder.set_visible(self.playlist_choice == "first")
        else:
            if self.state == "ready" and self.preview:
                reason = messages.PLAYLIST_REASON_SINGLE
            else:
                reason = messages.PLAYLIST_REASON_UNREAD
            self.playlist_reason.set_text(reason)
            self.playlist_reason.set_visible(True)

    @staticmethod
    def _set_caption(row, caption):
        label = caption_label(row)
        if label is not None:
            label.set_text(caption)

    def refresh_summaries(self):
        """Everything that depends on the chosen options and the preview's marks"""
        self.track_list.set_audio_estimates(self.download_type == "audio")
        if self.state not in ("ready", "reading"):
            self._set_pane_counts("")
            return
        if not self.preview:
            self._set_pane_counts("")
            return
        entries = self.preview.get("entries") or []
        expected = self._expected_entries()
        d, _l = self._skip_counts()
        skipped = d + _l
        n, m = len(entries), len(expected)
        if n == 1:
            counts_words = messages.PREVIEW_COUNTS_ONE
        elif skipped:
            counts_words = messages.PREVIEW_COUNTS.format(N=n, M=m, S=skipped)
        else:
            counts_words = messages.PREVIEW_COUNTS_NO_SKIP.format(N=n, M=m)
        self._set_pane_counts(counts_words)
        self.track_list.set_entries(self._scope_entries())

    def _set_pane_counts(self, words):
        self.pane_counts.set_text(words)
        self.strip_counts.set_text(words)
        tracks_view = self.state in ("downloading", "done")
        self.pane_title.set_text("" if tracks_view else messages.PREVIEW)
        self.pane_title.set_visible(not tracks_view)  # the track list explains itself
        self.strip_title.set_text(messages.PREVIEW)

    # -- the action bar
    def refresh_action_bar(self):
        self.actionbar.clear_actions()
        self.primary_btn = None
        if self.state == "ready":
            expected = self._expected_entries()
            m = len(expected)
            word = messages.WORD_TRACK if m == 1 else messages.WORD_TRACKS
            fmt = (
                messages.FORMAT_SUMMARY_VIDEO
                if self.download_type == "video"
                else messages.FORMAT_SUMMARY_AUDIO
            )
            if self.download_type == "audio" and expected:
                mb = audio_estimate_mb(expected)
                size = f"{round(mb)} MB" if mb >= 1 else fmt_size(mb * 1_000_000)
                head = messages.AB_READY_SIZE.format(M=m, word=word, format=fmt, size=size)
            else:
                head = messages.AB_READY.format(M=m, word=word, format=fmt)
            d, l = self._skip_counts()
            if d and l:
                caption = messages.AB_READY_CAPTION_BOTH.format(folder=tilde(self.folder), d=d, l=l)
            elif d:
                caption = messages.AB_READY_CAPTION_DUPES.format(folder=tilde(self.folder), d=d)
            elif l:
                caption = messages.AB_READY_CAPTION_LONG.format(folder=tilde(self.folder), l=l)
            else:
                caption = messages.AB_READY_CAPTION.format(folder=tilde(self.folder))
            self.actionbar.idle(head, caption)
            self.primary_btn = button_with_icon_hint(
                messages.DOWNLOAD,
                "download-simple",
                messages.DOWNLOAD_HINT,
                kind="primary",
                big=True,
                on_click=self.start_download,
            )
        elif self.state == "downloading":
            self.primary_btn = button_with_icon_hint(
                messages.CANCEL,
                "x",
                messages.CANCEL_HINT,
                big=True,
                on_click=self.cancel_running_download,
            )
        elif self.state == "done" and getattr(self, "_nothing_saved", False):
            self.primary_btn = button_with_icon_hint(
                messages.RETRY_DOWNLOAD,
                "arrow-clockwise",
                None,
                kind="primary",
                big=True,
                on_click=self._retry_download,
            )
        elif self.state == "done":
            self.primary_btn = button_with_icon_hint(
                messages.OPEN_FOLDER,
                "folder-open",
                None,
                kind="primary",
                big=True,
                on_click=self.open_done_folder,
            )
        else:
            if self.state == "error":
                # the banner on the right says what went wrong; the bar says the next step
                head, reason = messages.AB_ERROR_HEAD, messages.AB_ERROR_CAPTION
            else:
                head, reason = "", {
                    "empty": messages.AB_NO_LINK,
                    "reading": messages.READING,
                }.get(self.state, messages.READING)
            self.actionbar.idle(head, reason)
            self.primary_btn = kit.button(messages.DOWNLOAD, kind="primary", big=True)
            self.primary_btn.set_sensitive(False)
            self.primary_btn.set_tooltip_text(reason)
        if self.primary_btn is not None:
            self.actionbar.add_action(self.primary_btn)

    def open_done_folder(self):
        folder = self._done_folder or self.folder
        try:
            result = file_utils.open_folder(folder)
        except Exception:
            logger.exception("opening the folder failed")
            return
        if isinstance(result, dict) and result.get("status") == "error":
            logger.warning("open folder: %s", result.get("message"))

    # -- narrow layout
    def _on_layout(self, mode):
        self._mode = mode
        content = self.left_scroll.get_parent()
        if mode == "wide":
            self.left_scroll.set_size_request(OPTIONS_WIDE_W, -1)
            if self.right.get_parent() is self._col:
                self._col.remove(self.right)
            if self.right.get_parent() is not content:
                content.append(self.right)
            self.track_list.set_compact(False)
        else:
            self.left_scroll.set_size_request(-1, -1)
            if self.right.get_parent() is content:
                content.remove(self.right)
            if self.right.get_parent() is not self._col:
                self._col.append(self.right)
            self.track_list.set_compact(True)
        self._apply_strip()

    def _apply_strip(self):
        use_strip = self._mode == "compact" and self.state in ("reading", "ready")
        self.strip.set_visible(use_strip)
        if self._mode == "compact":
            self.right.set_visible(not use_strip or self._strip_open)
        else:
            self.right.set_visible(True)
        if use_strip:
            self.strip_button.set_label(messages.HIDE_LIST if self._strip_open else messages.SHOW_LIST)
