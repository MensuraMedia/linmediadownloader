# ui/player.py
"""Audio playback on GStreamer playbin (the app's own sound; Gtk.MediaFile is not
used because its GStreamer GTK-backend package is not installed).

The Player is a small state machine around an engine; the engine is the only
part that touches GStreamer, so tests can drive the Player with a fake. Video
files have no GTK 4 sink here, so they are handed to the system player
(Gio.AppInfo.launch_default_for_uri) and the bar says so in words.

Bus messages (end-of-stream, errors) and position ticks arrive on the main loop.
"""

import logging
import os

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, Gst  # noqa: E402

logger = logging.getLogger("lmd.ui.player")

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
TICK_MS = 250

_gst_ready = False


def _ensure_gst():
    global _gst_ready
    if not _gst_ready:
        Gst.init(None)
        _gst_ready = True


class PlaybinEngine:
    """The GStreamer part: one playbin, a bus watch, position/duration queries."""

    def __init__(self, on_message):
        _ensure_gst()
        self.playbin = Gst.ElementFactory.make("playbin", "lmd-player")
        self.playbin.set_property("video-sink", None)  # audio bar: never open a window
        bus = self.playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message", lambda _bus, message: on_message(message))

    def set_uri(self, uri):
        self.playbin.set_property("uri", uri)

    def set_volume(self, volume):  # 0.0 .. 1.0
        self.playbin.set_property("volume", max(0.0, min(1.0, volume)))

    def get_volume(self):
        return self.playbin.get_property("volume")

    def play(self):
        return self.playbin.set_state(Gst.State.PLAYING)

    def pause(self):
        return self.playbin.set_state(Gst.State.PAUSED)

    def stop(self):
        return self.playbin.set_state(Gst.State.NULL)

    def seek(self, seconds):
        self.playbin.seek(
            Gst.Format.TIME,
            1.0,  # rate
            Gst.SeekFlags.FLUSH,
            Gst.SeekType.SET,
            int(max(0.0, seconds) * Gst.SECOND),
            Gst.SeekType.NONE,
            0,
        )

    def position(self):
        ok, value = self.playbin.query_position(Gst.Format.TIME)
        return value / Gst.SECOND if ok else 0.0

    def duration(self):
        ok, value = self.playbin.query_duration(Gst.Format.TIME)
        return value / Gst.SECOND if ok else 0.0

    @property
    def state(self):
        _, current, _pending = self.playbin.get_state(0)
        return current


class Player:
    """Plays a list of files in order (auto-next), reporting through callbacks.

    on_event(name, **data) gets 'started', 'stopped', 'playing', 'paused',
    'ended' (the list ran out), 'externally' (a video opened elsewhere) and
    'error' (data: text). Position updates are polled by the bar with
    GLib.timeout_add while self.playing is True."""

    def __init__(self, engine_factory=PlaybinEngine, launch=None):
        self._launch = launch  # injected in tests; None uses Gio
        self.on_event = lambda *a, **k: None
        self.files = []  # [(path, title, playlist_name)]
        self.index = -1
        self.auto_next = True
        self.volume = 0.7
        self._engine = None  # created lazily: Gst.init on first play only
        self._engine_factory = engine_factory
        self._playing = False

    # -- state
    @property
    def playing(self):
        return self._playing

    def current(self):
        if 0 <= self.index < len(self.files):
            return self.files[self.index]
        return None

    def _engine_or_none(self):
        return self._engine

    # -- engine
    def _engine_get(self):
        if self._engine is None:
            self._engine = self._engine_factory(self._on_bus_message)
            self._engine.set_volume(self.volume)
        return self._engine

    def _on_bus_message(self, message):
        if message.type == Gst.MessageType.EOS:
            self._advance()
        elif message.type == Gst.MessageType.ERROR:
            _, error = message.parse_error()
            logger.warning("playback error: %s", error.message)
            self.stop()
            self.on_event("error", text=error.message)

    # -- playing
    def play_list(self, files, index=0):
        """files: [(path, title, playlist_name)]"""
        self.files = list(files)
        self.index = max(0, min(index, len(files) - 1)) if files else -1
        if not files:
            self.stop()
            return
        self._start_current()

    def _start_current(self):
        entry = self.current()
        if entry is None:
            self.stop()
            self.on_event("ended")
            return
        path = entry[0]
        if os.path.splitext(path)[1].lower() in VIDEO_EXTS:
            # No video sink in this app: the system player shows it.
            self._launch_video(path)
            return
        engine = self._engine_get()
        engine.set_uri(GLib.filename_to_uri(os.path.abspath(path)))
        engine.set_volume(self.volume)
        engine.play()
        self._playing = True
        self.on_event("started")

    def _launch_video(self, path):
        logger.info("handing %s to the system player", path)
        if self._launch is not None:
            self._launch(GLib.filename_to_uri(os.path.abspath(path)))
        else:
            from gi.repository import Gio

            Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(os.path.abspath(path)), None)
        self.on_event("externally")

    def toggle(self):
        if self.index < 0:
            return
        if self._playing:
            self.pause()
        else:
            engine = self._engine_get()
            engine.play()
            self._playing = True
            self.on_event("playing")

    def pause(self):
        if self._engine is not None:
            self._engine.pause()
        self._playing = False
        self.on_event("paused")

    def stop(self):
        if self._engine is not None:
            self._engine.stop()
        self._playing = False
        self.on_event("stopped")

    def next(self):
        if self.index + 1 < len(self.files):
            self.index += 1
            self._start_current()
        else:
            self.stop()
            self.on_event("ended")

    def previous(self):
        if self.index > 0:
            self.index -= 1
            self._start_current()

    def _advance(self):
        """End of one file: next when auto-next is on, otherwise stop here"""
        if self.auto_next:
            self.next()
        else:
            self.stop()

    # -- position and volume
    def position(self):
        return self._engine.position() if self._engine is not None else 0.0

    def duration(self):
        return self._engine.duration() if self._engine is not None else 0.0

    def seek_relative(self, seconds):
        if self._engine is not None:
            self._engine.seek(self.position() + seconds)

    def seek_absolute(self, seconds):
        if self._engine is not None:
            self._engine.seek(seconds)

    def set_volume(self, volume):  # 0.0 .. 1.0
        self.volume = max(0.0, min(1.0, volume))
        if self._engine is not None:
            self._engine.set_volume(self.volume)
