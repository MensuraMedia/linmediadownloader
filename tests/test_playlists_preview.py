#!/usr/bin/env python3
# tests/test_playlists_preview.py
# preview_operation (modules/playlists.py): it plans exactly what apply_operation
# then does, without touching a single file. GTK-free.

import pytest

from modules import playlists


@pytest.fixture()
def folder(tmp_path, monkeypatch):
    """A real playlist folder inside a safe download root (no ffprobe needed:
    durations are stubbed so delete_long is testable offline)"""
    root = tmp_path / "downloads"
    root.mkdir()
    monkeypatch.setattr(playlists, "_scan_dirs", lambda: {str(root)})
    playlist = root / "AKIRA OST_playlist"
    playlist.mkdir()
    names = [
        "Kaneda's Theme (Lyrics).mp3",
        "Battle Against Clown - AKIRA 1988.mp3",
        "Mutation.MP3",
        "Illusion (Music Video).mp3",
    ]
    for name in names:
        (playlist / name).write_bytes(b"x" * 128)
    monkeypatch.setattr(playlists, "_duration", lambda path: 100.0)
    return playlist


def touch_names(folder):
    return sorted(p.name for p in folder.iterdir() if p.is_file())


def test_preview_lists_renames_and_touches_nothing(folder):
    before = touch_names(folder)
    planned = playlists.preview_operation(str(folder), "remove_filler")
    assert ("Illusion (Music Video).mp3", "Illusion.mp3") in planned
    assert touch_names(folder) == before  # a preview never renames


def test_apply_matches_the_preview(folder):
    planned = playlists.preview_operation(str(folder), "remove_filler")
    result = playlists.apply_operation(str(folder), "remove_filler")
    assert result["status"] == "success" and result["renamed"] == len(planned)
    after = touch_names(folder)
    for _old, new in planned:
        assert new in after
    # running it again changes nothing, and the preview agrees
    assert playlists.preview_operation(str(folder), "remove_filler") == []


def test_case_and_prefix_previews(folder):
    import os

    planned = playlists.preview_operation(str(folder), "lower_case")
    # the base name is lowered; the extension keeps its case
    assert all(os.path.splitext(new)[0] == os.path.splitext(old)[0].lower() for old, new in planned)
    planned = playlists.preview_operation(str(folder), "number_prefix")
    assert [new for _old, new in planned] == [  # files are numbered in list order (A to Z)
        "01_Battle Against Clown - AKIRA 1988.mp3",
        "02_Illusion (Music Video).mp3",
        "03_Kaneda's Theme (Lyrics).mp3",
        "04_Mutation.MP3",
    ]


def test_delete_long_preview_points_at_the_trash(folder, monkeypatch):
    monkeypatch.setattr(playlists, "_duration", lambda path: 500.0)  # over 7 min
    planned = playlists.preview_operation(str(folder), "delete_long")
    assert len(planned) == len(touch_names(folder))
    assert all(new.startswith(".trash") for _old, new in planned)
    assert touch_names(folder) and playlists.trash_count(str(folder)) == 0


def test_unknown_operation_and_unsafe_path(folder, tmp_path):
    assert playlists.preview_operation(str(folder), "no_such_op") == []
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert playlists.preview_operation(str(outside), "clean") == []


def test_preview_global_spans_folders(folder, tmp_path, monkeypatch):
    other = tmp_path / "downloads" / "Second_playlist"
    other.mkdir()
    (other / "Tetsuo Demo (Official).mp3").write_bytes(b"y" * 64)
    monkeypatch.setattr(
        playlists,
        "list_playlists",
        lambda: [
            {"path": str(folder), "name": "one", "order": 1, "color": "#000000"},
            {"path": str(other), "name": "two", "order": 2, "color": "#000000"},
        ],
    )
    planned = playlists.preview_global("remove_filler")
    assert ("Tetsuo Demo (Official).mp3", "Tetsuo Demo.mp3") in planned
    assert any(old.startswith("Illusion") for old, _new in planned)
