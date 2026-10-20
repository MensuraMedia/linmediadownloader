# ui/widgets/player_bar.py
"""The Library page's player bar (its one main action is the 48 px play-pause):
previous / play-pause / next, title and counts, a position scale with elapsed
and total time, volume, and the Auto-next switch. Position updates poll the
Player every 250 ms while it plays; everything else reacts to Player events.

Keyboard handling (Space, arrows, Delete) lives on the file table in
ui/pages/library.py; this bar only shows and controls.
"""

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from ui import messages  # noqa: E402

logger = logging.getLogger("lmd.ui.player_bar")

TICK_MS = 250


def clock_words(seconds):
    """1:12 for the bar's time labels (never negative, blank when unknown)"""
    seconds = max(0, int(seconds or 0))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class PlayerBar(Gtk.Box):
    def __init__(self, player, window):
        super().__init__()
        kit.css(self, "lt-actionbar")
        self.player = player
        self.window = window
        self._tick = None
        self._seeking = False
        self._build()
        player.on_event = self._on_event
        self._paint_state()

    # ================================================================ build
    def _build(self):
        self.prev_button = kit.icon_button("skip-back", messages.PLB_PREVIOUS, on_click=self._previous)
        # the one main action: a 48x48 primary square (lt-big would widen it to 160+)
        self.play_button = kit.button(messages.PLB_PLAY, kind="primary")
        self.play_button.set_size_request(48, 48)
        self.play_button.set_child(kit.icon("play", 22, tokens.COLOR["on_accent"]))
        self.play_button.connect("clicked", lambda *_a: self.player.toggle())
        self.next_button = kit.icon_button("skip-forward", messages.PLB_NEXT, on_click=self._next)
        for button in (self.prev_button, self.play_button, self.next_button):
            button.set_valign(Gtk.Align.CENTER)
            self.append(button)

        # track title + caption live in the bar, between the buttons and the scale
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        words.set_valign(Gtk.Align.CENTER)
        words.set_margin_start(4)
        words.set_size_request(140, -1)  # the title shortens; 140 px keeps the bar inside a narrow window
        self.title = kit.text(messages.PLB_NOWHERE, "lt-strong")
        self.title.set_ellipsize(3)
        self.counts = kit.text("", "lt-caption")
        self.counts.set_ellipsize(3)
        words.append(self.title)
        words.append(self.counts)
        self.append(words)

        self.elapsed = kit.text("0:00", "lt-muted")
        self.elapsed.set_width_chars(5)
        self.elapsed.set_valign(Gtk.Align.CENTER)
        self.append(self.elapsed)
        self.position = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.001)
        self.position.set_hexpand(True)
        self.position.set_valign(Gtk.Align.CENTER)
        self.position.set_draw_value(False)
        kit.name(self.position, messages.PLB_POSITION)
        self.position.connect("change-value", self._on_seek)
        self.append(self.position)
        self.total = kit.text("0:00", "lt-muted")
        self.total.set_width_chars(5)
        self.total.set_valign(Gtk.Align.CENTER)
        self.append(self.total)

        speaker = kit.icon("speaker-high", 18)
        speaker.set_valign(Gtk.Align.CENTER)
        self.append(speaker)
        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.01)
        self.volume.set_size_request(96, -1)
        self.volume.set_valign(Gtk.Align.CENTER)
        self.volume.set_value(self.player.volume)
        self.volume.set_draw_value(False)
        kit.name(self.volume, messages.PLB_VOLUME)
        self.volume.connect("value-changed", self._on_volume)
        self.append(self.volume)

        self.auto_next = kit.SwitchRow("", None, True)
        self.auto_next.switch.set_valign(Gtk.Align.CENTER)
        kit.name(self.auto_next.switch, messages.PLB_AUTO_NEXT)
        self.auto_next.switch.connect("notify::active", self._on_auto_next)
        label = kit.text(messages.PLB_AUTO_NEXT)
        label.set_valign(Gtk.Align.CENTER)
        self.append(kit.hbox(self.auto_next, label, spacing=8))

    # ================================================================ events
    def _on_event(self, name, **data):
        self._paint_state()
        if name in ("started", "playing"):
            self._ticks_start()
        if name in ("paused", "stopped", "error", "ended", "externally"):
            self._ticks_stop()
        if name == "error":
            self._show_error()
        if name == "externally":
            self.title.set_text(messages.PLB_VIDEO_EXTERNALLY)

    def _show_error(self):
        self.title.set_text(messages.PLB_ERROR_TITLE)
        self.counts.set_text(messages.PLB_ERROR_BODY)

    def _ticks_start(self):
        if self._tick is None:
            self._tick = GLib.timeout_add(TICK_MS, self._on_tick)

    def _ticks_stop(self):
        if self._tick is not None:
            GLib.source_remove(self._tick)
            self._tick = None

    def _on_tick(self):
        duration = self.player.duration()
        position = self.player.position()
        if duration > 0:
            self.position.set_range(0.0, duration)
            self._seeking = True
            self.position.set_value(position)
            self._seeking = False
        self.elapsed.set_text(clock_words(position))
        self.total.set_text(clock_words(duration))
        return self.player.playing

    def _on_seek(self, _scale, _kind, value):
        if getattr(self, "_seeking", False):
            return True
        self.player.seek_absolute(value)
        return True

    def _on_volume(self, scale):
        self.player.set_volume(scale.get_value())

    def _on_auto_next(self, switch, _param):
        self.player.auto_next = switch.get_active()

    def _previous(self):
        self.player.previous()
        self._paint_state()

    def _next(self):
        self.player.next()
        self._paint_state()

    # ================================================================ painting
    def _paint_state(self):
        entry = self.player.current()
        playing = self.player.playing
        icon_name = "pause" if playing else "play"
        self.play_button.set_child(kit.icon(icon_name, 22, tokens.COLOR["on_accent"]))
        spoken = messages.PLB_PAUSE if playing else messages.PLB_PLAY
        kit.name(self.play_button, spoken)
        self.play_button.set_tooltip_text(spoken)
        if entry is None:
            self.title.set_text(messages.PLB_NOWHERE)
            self.counts.set_text("")
            return
        _path, title, playlist_name = entry
        self.title.set_text(title or _path)
        self.counts.set_text(
            messages.PLB_OF.format(
                playlist=playlist_name or "",
                i=self.player.index + 1,
                n=len(self.player.files),
            )
        )
