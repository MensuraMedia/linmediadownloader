#!/usr/bin/env python3
# tests/test_ui_file_control.py
# The File Control page (renaming: tidy names, playlist names, word lists) with the
# playlist backends faked and a throwaway settings file. Skips without a display.

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
from modules.config import user_settings  # noqa: E402
from ui import messages  # noqa: E402
from ui.pages import file_control as fc_module  # noqa: E402
from ui.window import MainWindow  # noqa: E402

PLAYLISTS = [
    {"name": "AKIRA OST", "path": "/music/akira", "file_count": 10, "order": 14, "color": "#4c9dff"},
    {"name": "Neo-Tokyo Ambience", "path": "/music/neo", "file_count": 12, "order": 13, "color": "#5fd38d"},
]
FILES = [
    {"filename": "Kaneda's Theme.mp3", "size": 5_100_000, "duration": 222},
    {"filename": "Requiem.mp3", "size": 6_000_000, "duration": 262},
]


def walk(widget):
    yield widget
    child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


def label_texts(container):
    return [w.get_text() for w in walk(container) if isinstance(w, Gtk.Label)]


@pytest.fixture(scope="module")
def app():
    Gtk.init()
    from ui.app import App

    application = App(application_id="org.mensuramedia.LinMediaDownloaderTests.filecontrol")
    application.register(None)
    return application


@pytest.fixture(autouse=True)
def fake_library(monkeypatch):
    calls = {"stack": {"can_undo": False, "can_redo": False}}
    monkeypatch.setattr(library, "list_playlists", lambda: [dict(p) for p in PLAYLISTS])
    monkeypatch.setattr(library, "list_playlist_files", lambda path: [dict(f) for f in FILES])
    monkeypatch.setattr(
        library,
        "list_all_media",
        lambda: [{"name": f["filename"], "path": "/music/akira/" + f["filename"], "folder": "AKIRA OST",
                  "size": f["size"]} for f in FILES],
    )
    monkeypatch.setattr(library, "file_stats", lambda: {"total": 2, "duplicate_names": 0, "same_size": 0})
    monkeypatch.setattr(library, "trash_count", lambda path: 0)
    monkeypatch.setattr(library, "stack_state", lambda: dict(calls["stack"]))
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
        lambda path, op: calls.update(apply=(path, op)) or {"status": "success", "renamed": 2},
    )
    monkeypatch.setattr(
        library, "global_operation", lambda op: calls.update(global_op=op) or {"status": "success"}
    )
    monkeypatch.setattr(
        library,
        "rename_playlist",
        lambda path, name: calls.update(rename=(path, name))
        or {"status": "success", "path": f"/music/{name}", "name": name},
    )
    monkeypatch.setattr(library, "undo_last", lambda: calls.update(undo=True) or {})
    monkeypatch.setattr(library, "redo_last", lambda: calls.update(redo=True) or {})
    yield calls


@pytest.fixture()
def window(app):
    win = MainWindow(app)
    yield win
    win.library_page.player.stop()
    win.destroy()


@pytest.fixture()
def page(window):
    page = window.file_control_page
    page.refresh()
    return page


def test_page_sits_in_the_rail_before_settings(window):
    assert window.stack.get_child_by_name("file_control") is window.file_control_page
    assert window._order.index("file_control") == window._order.index("library") + 1


def test_nothing_renames_before_a_change_is_picked(page):
    assert page.target["path"] == "/music/akira"
    assert messages.FC_PICK_OPERATION in label_texts(page)
    assert not page.apply_button.get_sensitive()


def test_preview_lists_every_change_and_apply_runs_it(page, fake_library):
    page.select("remove_filler")
    texts = label_texts(page)
    assert messages.LIB_PREVIEW.format(k=2, n=10) in texts
    assert "Illusion (Music Video).mp3" in texts and "Illusion.mp3" in texts
    assert page.apply_button.get_label() == messages.LIB_RENAME_K.format(k=2)
    assert "apply" not in fake_library  # a preview never renames
    page.apply()
    assert fake_library["apply"] == ("/music/akira", "remove_filler")


def test_action_bar_says_what_apply_will_do(page):
    page.select("remove_filler")
    assert messages.LIB_OP_REMOVE_FILLER + " · AKIRA OST" in label_texts(page.actionbar)


def test_delete_long_previews_a_trash_move(page):
    page.select("delete_long")
    assert page.apply_button.get_label() == messages.LIB_MOVE_K.format(k=1)
    assert page.op_note.get_visible()
    assert messages.FC_TO_TRASH in label_texts(page.preview_rows)


def test_all_files_runs_the_global_operation(page, fake_library):
    page.scope_seg.set_value("all")
    assert not page.playlist_row.get_visible()
    page.select("upper_case")
    page.apply()
    assert fake_library["global_op"] == "upper_case"


def test_choosing_another_playlist_previews_it(page, fake_library, monkeypatch):
    seen = []
    monkeypatch.setattr(library, "preview_operation", lambda path, op: seen.append(path) or [])
    page.select("upper_case")
    page.playlist_choice.set_selected(1)
    assert page.target["path"] == "/music/neo"
    assert seen[-1] == "/music/neo"
    assert page.rename_entry.get_text() == "Neo-Tokyo Ambience"


def test_rename_playlist_and_the_library_follows(page, window, fake_library):
    window.library_page.select(PLAYLISTS[0])
    assert not page.rename_button.get_sensitive()  # the same name: nothing to do
    page.rename_entry.set_text("Renamed OST")
    assert page.rename_button.get_sensitive()
    page.apply_rename()
    assert fake_library["rename"] == ("/music/akira", "Renamed OST")
    assert page.rename_note.get_text() == messages.FC_RENAMED.format(name="Renamed OST")


def test_undo_and_redo_say_why_they_are_off_then_run(page, fake_library):
    assert not page.undo_button.get_sensitive()
    assert page.undo_button.get_tooltip_text() == messages.LIB_UNDO_NONE
    assert page.redo_button.get_tooltip_text() == messages.LIB_REDO_NONE
    fake_library["stack"] = {"can_undo": True, "can_redo": False}
    page.refresh()
    assert page.undo_button.get_sensitive()
    page._undo()
    assert fake_library["undo"] is True


def test_filler_word_add_and_remove(page):
    words = lambda: user_settings.get_settings()["filler_words"]  # noqa: E731
    page.word_entry.set_text("extraword")
    page._add_word()
    assert "extraword" in words()
    assert messages.SET_WORD_ADDED in label_texts(page)
    page._remove_word("extraword")
    assert "extraword" not in words()


def test_replacement_add_and_remove(page):
    rows = lambda: user_settings.get_settings()["char_replacements"]  # noqa: E731
    page.new_from.set_text("")
    page._add_replacement()
    assert page.replacement_note.get_text() == messages.SET_REPLACEMENT_NEEDS_FROM
    page.new_from.set_text("&")
    page.new_to.set_text("and")
    page._add_replacement()
    assert rows() == [{"from": "&", "to": "and"}]
    page._remove_replacement(0)
    assert rows() == []


def test_word_changes_refresh_a_preview_that_uses_them(page, monkeypatch):
    calls = []
    monkeypatch.setattr(library, "preview_operation", lambda path, op: calls.append(op) or [])
    page.select("remove_filler")
    page.word_entry.set_text("brandnewword")
    page._add_word()
    assert calls == ["remove_filler", "remove_filler"]
    page._remove_word("brandnewword")


def test_reset_asks_before_restoring_defaults(page, monkeypatch):
    user_settings.save_settings({"filler_words": ["a", "b"], "char_replacements": [{"from": "x", "to": "y"}]})
    asked = {}

    def fake_confirm(_parent, title, _body, _label, **kwargs):
        asked["title"] = title
        asked["yes"] = kwargs.get("on_answer")

    monkeypatch.setattr(fc_module.kit, "confirm", fake_confirm)
    page._confirm_reset()
    assert messages.SET_RESET_TITLE in asked["title"]
    asked["yes"](True)
    values = user_settings.get_settings()
    assert values["filler_words"] == sorted(user_settings.DEFAULT_FILLER_WORDS)
    assert values["char_replacements"] == []


def test_a_long_playlist_name_never_widens_the_page(page, monkeypatch):
    long_name = "A Very Long Playlist Name " * 8
    monkeypatch.setattr(
        library, "list_playlists", lambda: [dict(PLAYLISTS[0], name=long_name), dict(PLAYLISTS[1])]
    )
    page.refresh()
    minimum = page.playlist_choice.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
    assert minimum < 300, f"the playlist dropdown asks for {minimum} px"
