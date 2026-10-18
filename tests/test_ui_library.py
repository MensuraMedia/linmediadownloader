#!/usr/bin/env python3
# tests/test_ui_library.py
# The Library page with faked playlist backends (tmp folders for anything the
# page reads off disk, monkeypatched modules.playlists functions for the rest),
# plus the GStreamer-free Player state machine. Skips without a display.

import sys

import pytest
from conftest import requires_display

pytestmark = requires_display

gi = pytest.importorskip("gi")
if "gi.repository.Gtk" in sys.modules:
    if sys.modules["gi.repository.Gtk"].get_major_version() != 4:
        pytest.skip("Gtk 3.0 already loaded in this process", allow_module_level=True)
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from modules import playlists as library  # noqa: E402
from ui import messages  # noqa: E402
from ui.pages.library import badge_class  # noqa: E402
from ui.player import Player  # noqa: E402
from ui.window import MainWindow  # noqa: E402


def walk(widget):
    yield widget
    if hasattr(widget, "get_first_child"):
        child = widget.get_first_child()
        while child:
            yield from walk(child)
            child = child.get_next_sibling()


def label_texts(container):
    return [w.get_text() for w in walk(container) if isinstance(w, Gtk.Label)]


def pill_texts(container):
    out = []
    for widget in walk(container):
        if hasattr(widget, "has_css_class") and widget.has_css_class("lt-pill"):
            out.extend(label_texts(widget))
    return out


FAKE_PLAYLISTS = [
    {
        "name": "AKIRA OST",
        "path": "/music/akira",
        "file_count": 10,
        "total_size": 41_000_000,
        "order": 14,
        "color": "#4c9dff",
        "mtime": 1,
    },
    {
        "name": "Neo-Tokyo Ambience",
        "path": "/music/neo",
        "file_count": 12,
        "total_size": 58_000_000,
        "order": 13,
        "color": "#5fd38d",
        "mtime": 2,
    },
    {
        "name": "Road Trip",
        "path": "/music/road",
        "file_count": 38,
        "total_size": 160_000_000,
        "order": 10,
        "color": "#0d6efd",
        "mtime": 3,
    },  # not a token colour: accent
]
FAKE_FILES = [
    {"filename": "Kaneda's Theme.mp3", "size": 5_100_000, "duration": 222},
    {"filename": "Battle Against Clown.mp3", "size": 5_100_000, "duration": 221},
    {"filename": "Requiem.mp3", "size": 6_000_000, "duration": 262},
]


@pytest.fixture(scope="module")
def app():
    Gtk.init()
    from ui.app import App

    application = App(
        application_id="org.mensuramedia.LinMediaDownloaderTests."
        + __name__.rsplit(".", 1)[-1].replace("_", "")
    )
    application.register(None)
    return application


@pytest.fixture(autouse=True)
def fake_library(monkeypatch):
    calls = {}
    monkeypatch.setattr(library, "list_playlists", lambda: [dict(p) for p in FAKE_PLAYLISTS])
    monkeypatch.setattr(
        library,
        "list_playlist_files",
        lambda path: [dict(f) for f in FAKE_FILES] if path == "/music/akira" else [],
    )
    monkeypatch.setattr(
        library,
        "list_all_media",
        lambda: [
            {
                "name": f["filename"],
                "path": f"/music/akira/{f['filename']}",
                "folder": "AKIRA OST",
                "size": f["size"],
            }
            for f in FAKE_FILES
        ],
    )
    monkeypatch.setattr(library, "file_stats", lambda: {"total": 3, "duplicate_names": 0, "same_size": 2})
    monkeypatch.setattr(library, "trash_count", lambda path: 3 if path == "/music/akira" else 0)
    monkeypatch.setattr(library, "stack_state", lambda: {"can_undo": False, "can_redo": False})
    monkeypatch.setattr(
        library,
        "preview_operation",
        lambda path, op: (
            [("Illusion (Music Video).mp3", "Illusion.mp3"), ("Kaneda's Theme.mp3", "Kaneda's Theme.mp3")]
            if op == "remove_filler"
            else [("Requiem.mp3", "REQUIEM.mp3")]
        ),
    )
    monkeypatch.setattr(library, "preview_global", lambda op: [("Requiem.mp3", "REQUIEM.mp3")])
    monkeypatch.setattr(
        library,
        "apply_operation",
        lambda path, op: calls.update(apply=(path, op))
        or {"status": "success", "renamed": 1, "moves": [], "can_undo": True, "can_redo": False},
    )
    monkeypatch.setattr(
        library,
        "global_operation",
        lambda op: calls.update(global_op=op)
        or {"status": "success", "renamed": 1, "folders": 1, "can_undo": True, "can_redo": False},
    )
    monkeypatch.setattr(
        library,
        "rename_playlist",
        lambda path, name: calls.update(rename=(path, name))
        or {"status": "success", "path": f"/music/{name}", "name": name},
    )
    monkeypatch.setattr(
        library,
        "set_playlist_color",
        lambda path, colour: calls.update(colour=(path, colour)) or {"status": "success"},
    )
    monkeypatch.setattr(
        library,
        "delete_media_file",
        lambda path: calls.update(trashed=path) or {"status": "success"},
    )
    monkeypatch.setattr(
        library,
        "empty_trash",
        lambda path: calls.update(emptied=path) or {"status": "success", "purged": 3},
    )
    yield calls


@pytest.fixture()
def window(app):
    win = MainWindow(app)
    yield win
    win.library_page.player.stop()
    win.destroy()


@pytest.fixture()
def page(window):
    return window.library_page


def test_sidebar_lists_playlists_with_badges_and_selects(page):
    words = label_texts(page.sidebar_rows)
    assert "AKIRA OST" in words and "Neo-Tokyo Ambience" in words
    assert any("10" in text and "41 MB" in text for text in words)
    assert page.selected["path"] == "/music/akira"  # newest order first
    assert "AKIRA OST" in label_texts(page.title_label)


def test_unknown_badge_colours_fall_back_to_accent():
    assert badge_class("#0d6efd") == "accent"
    assert badge_class("#5fd38d") == "ok"
    assert badge_class(None) == "accent"


def test_playlist_pane_pills_and_file_table(page):
    page.select(FAKE_PLAYLISTS[0])
    pills = pill_texts(page.pills)
    assert any("look alike" in text for text in pills)  # two files share a size
    assert messages.LIB_TRASH.format(n=3) in pills
    assert page.playlist_store.get_n_items() == 3
    names = [page.playlist_store.get_item(i).name for i in range(3)]
    assert names == sorted(f["filename"] for f in FAKE_FILES)


def test_all_files_view_shows_stats_and_folders(page):
    page._on_view_changed("all")
    assert page.right_stack.get_visible_child_name() == "all"
    pills = pill_texts(page.stats_pills)
    assert messages.LIB_STATS_TOTAL.format(n=3) in pills
    assert messages.LIB_STATS_SIZES.format(n=2) in pills
    assert page.all_store.get_n_items() == 3


def test_search_narrows_the_sidebar(page):
    page.search.set_text("neo")
    words = label_texts(page.sidebar_rows)
    assert "Neo-Tokyo Ambience" in words and "AKIRA OST" not in words


def test_rename_edits_inline_and_reports_errors(page, fake_library):
    page.select(FAKE_PLAYLISTS[0])
    page._start_rename()
    assert page.rename_entry.get_visible() is True
    page.rename_entry.set_text("Renamed OST")
    page._apply_rename()
    assert fake_library["rename"] == ("/music/akira", "Renamed OST")
    assert page.title_label.get_text() == "Renamed OST"


def test_tidy_preview_and_apply(page, fake_library):
    page.select(FAKE_PLAYLISTS[0])
    tidy = page.tidy_button.get_popover().get_child()
    tidy.select("remove_filler")
    assert messages.LIB_PREVIEW.format(k=2, n=10) in label_texts(tidy)
    assert "Illusion (Music Video).mp3" in label_texts(tidy)
    assert "becomes" in label_texts(tidy)
    assert tidy.apply_button.get_label() == messages.LIB_RENAME_K.format(k=2)
    tidy.apply()
    assert fake_library["apply"] == ("/music/akira", "remove_filler")


def test_tidy_delete_long_previews_a_trash_move(page, fake_library):
    page.select(FAKE_PLAYLISTS[0])
    tidy = page.tidy_button.get_popover().get_child()
    tidy.select("delete_long")
    assert tidy.apply_button.get_label() == messages.LIB_MOVE_K.format(k=1)
    assert messages.LIB_OP_DELETE_LONG_NOTE in label_texts(tidy)


def test_tidy_all_files_runs_the_global_operation(page, fake_library):
    page._on_view_changed("all")
    tidy = page.all_tidy_button.get_popover().get_child()
    tidy.select("upper_case")
    assert tidy.apply_button.get_label() == messages.LIB_RENAME_K.format(k=1)
    tidy.apply()
    assert fake_library["global_op"] == "upper_case"


def test_undo_and_redo_say_why_they_are_off(page):
    assert not page.undo_button.get_sensitive()
    assert page.undo_button.get_tooltip_text() == messages.LIB_UNDO_NONE
    assert not page.redo_button.get_sensitive()
    assert page.redo_button.get_tooltip_text() == messages.LIB_REDO_NONE


def test_trash_confirm_lists_the_files_before_deleting(page, fake_library, monkeypatch, tmp_path):
    trash = tmp_path / ".trash"
    trash.mkdir()
    for name in ("one.mp3", "two.mp3", "three.mp3"):
        (trash / name).write_bytes(b"x")
    page.select(dict(FAKE_PLAYLISTS[0], path=str(tmp_path)))
    asked = {}

    def fake_confirm(_parent, title, body, confirm_label, **kwargs):
        asked.update(title=title, body=body, detail=kwargs.get("detail_mono"), yes=kwargs.get("on_answer"))

    import ui.pages.library as library_page_module

    monkeypatch.setattr(library_page_module.kit, "confirm", fake_confirm)
    page._confirm_empty_trash()
    assert asked["title"] == messages.LIB_EMPTY_TRASH_TITLE.format(name="AKIRA OST")
    assert "one.mp3" in asked["detail"] and "three.mp3" in asked["detail"]
    asked["yes"](True)
    assert fake_library["emptied"] == str(tmp_path)


def test_move_to_trash_stops_playback_and_refreshes(page, fake_library):
    page.select(FAKE_PLAYLISTS[0])
    page._trash_file("/music/akira/Requiem.mp3")
    assert fake_library["trashed"] == "/music/akira/Requiem.mp3"
    assert page.playlist_store.get_n_items() == 3  # list_playlist_files is still the fake


def test_select_by_path_picks_the_right_playlist(page):
    page.select_by_path("/music/neo")
    assert page.selected["name"] == "Neo-Tokyo Ambience"
    page.select_by_path("")  # nothing: keep the selection
    assert page.selected["name"] == "Neo-Tokyo Ambience"


# -- the Player state machine, engine faked (no GStreamer needed)
class FakeEngine:
    def __init__(self, on_message):
        self.uri = None
        self.volume = None
        self.state_changes = []
        self.on_message = on_message

    def set_uri(self, uri):
        self.uri = uri

    def set_volume(self, volume):
        self.volume = volume

    def play(self):
        self.state_changes.append("play")

    def pause(self):
        self.state_changes.append("pause")

    def stop(self):
        self.state_changes.append("stop")

    def seek(self, seconds):
        self.state_changes.append(("seek", seconds))

    def position(self):
        return 72.0

    def duration(self):
        return 221.0


def make_player():
    events = []
    player = Player(engine_factory=FakeEngine)
    player.on_event = lambda name, **data: events.append(name)
    return player, events


def test_player_plays_auto_nexts_and_stops():
    player, events = make_player()
    files = [("/a/one.mp3", "One", "P"), ("/a/two.mp3", "Two", "P")]
    player.play_list(files)
    assert events == ["started"] and player.playing is True
    player._engine.on_message(_fake_eos())
    assert player.current()[0] == "/a/two.mp3"
    player._engine.on_message(_fake_eos())  # end of the list: stopped
    assert player.playing is False and events[-2:] == ["stopped", "ended"]  # the list ran out


def _fake_eos():
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst

    class M:
        type = Gst.MessageType.EOS

        def parse_error(self):  # pragma: no cover - not called for EOS
            raise AssertionError("EOS messages have no error")

    return M()


def test_player_auto_next_off_stops_at_eos():
    player, _events = make_player()
    player.auto_next = False
    player.play_list([("/a/one.mp3", "One", "P")])
    player._engine.on_message(_fake_eos())
    assert player.playing is False


def test_player_video_files_go_to_the_system_player():
    launched = []
    player, events = make_player()
    player._launch = launched.append
    player.play_list([("/v/clip.mp4", "Clip", "P")])
    assert launched and launched[0].endswith("clip.mp4")
    assert "externally" in events and player.playing is False


def test_player_seek_volume_and_toggle():
    player, _events = make_player()
    player.play_list([("/a/one.mp3", "One", "P")])
    player.seek_relative(5)
    assert player._engine.state_changes[-1] == ("seek", 77.0)
    player.set_volume(1.5)  # clamped
    assert player.volume == 1.0
    player.pause()
    player.toggle()
    assert player.playing is True


def test_player_error_stops_and_reports():
    player, events = make_player()
    player.play_list([("/a/one.mp3", "One", "P")])
    player._engine.on_message(_fake_error("cannot decode"))
    assert player.playing is False and "error" in events


def _fake_error(text):
    from gi.repository import Gst

    class Message:
        type = Gst.MessageType.ERROR

        def parse_error(self):
            return None, type("Error", (), {"message": text})()

    return Message()


def test_tables_scroll_so_the_window_stays_800(page, window):
    """Both file tables live in ScrolledWindows: a 10-file playlist and the whole
    library keep the window's natural height within 800 px."""
    assert isinstance(page.playlist_view.get_first_child(), Gtk.ScrolledWindow)
    page._on_view_changed("all")
    assert isinstance(page.all_view.get_first_child(), Gtk.ScrolledWindow)
    minimum, natural = window.measure(Gtk.Orientation.VERTICAL, -1)[:2]
    assert natural <= 800, f"window wants {natural} px tall"


def test_play_button_is_a_48_px_square(page):
    request = page.bar.play_button.get_size_request()
    assert request[1] == 48
    minimum, natural = page.bar.play_button.measure(Gtk.Orientation.HORIZONTAL, -1)[:2]
    assert natural <= 56, f"play button wants {natural} px wide"
