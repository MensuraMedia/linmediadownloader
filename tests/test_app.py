#!/usr/bin/env python3
# tests/test_app.py
# Offline unit + route tests for Linux Media Downloader.
# These require no network and must never trigger a real download.

import os

import pytest
import yt_dlp

import modules.config.settings as settings
from modules.utils.file_utils import sanitize_filename
from modules.download.media import DownloadProgress
from modules import playlists as pl
from modules.download import chapters as ch
from modules.download import dedupe as dd
import browser_app  # provides a Flask app with both blueprints registered


def _make_playlist(tmp_path, folder, names):
    """Create a folder with media files; return its path."""
    d = tmp_path / folder
    d.mkdir()
    for n in names:
        (d / n).write_bytes(b"x")
    return str(d)


# ── filename sanitization ────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("My Video.mp3", "My_Video.mp3"),
    ("a  b---c.mp4", "a_b_c.mp4"),
    ("  spaced  .m4a", "spaced.m4a"),
    ("weird:*?name<>.webm", "weirdname.webm"),
    ("__leading_trailing__.mp3", "leading_trailing.mp3"),
])
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_preserves_extension():
    assert sanitize_filename("song.final.mp3").endswith(".mp3")


# ── cancellation wiring (the cross-module bug that was fixed) ─────────────────

def test_cancel_flag_single_source_of_truth():
    settings.reset_cancel()
    assert settings.is_cancel_requested() is False
    settings.request_cancel()
    # media.py imported the accessor, so it must observe the same state
    from modules.download import media
    assert media.is_cancel_requested() is True
    settings.reset_cancel()


def test_progress_hook_raises_when_cancelled():
    settings.reset_cancel()
    dp = DownloadProgress(total_files=1)
    settings.request_cancel()
    with pytest.raises(yt_dlp.utils.DownloadCancelled):
        dp.progress_hook({
            "status": "downloading",
            "filename": "file.part",
            "downloaded_bytes": 1,
            "total_bytes": 2,
        })
    settings.reset_cancel()


def test_progress_hook_finished_marks_completed():
    settings.reset_cancel()
    dp = DownloadProgress(total_files=1)
    dp.progress_hook({"status": "finished", "filename": "/tmp/song.webm"})
    assert settings.current_download["status"] == "processing"  # converting: not complete yet
    dp.postprocessor_hook({"status": "finished", "postprocessor": "MoveFiles", "info_dict": {}})
    assert settings.current_download["status"] == "completed"
    assert settings.current_download["total_progress"] == 100
    assert dp.done is True


def test_progress_hook_defers_completion_when_splitting():
    """With a split pending, the last file must NOT flip status to 'completed'."""
    settings.reset_cancel()
    dp = DownloadProgress(total_files=1, split_pending=True)
    dp.progress_hook({"status": "finished", "filename": "/tmp/song.webm"})
    dp.postprocessor_hook({"status": "finished", "postprocessor": "MoveFiles", "info_dict": {}})
    assert dp.done is True                                  # download really finished
    assert settings.current_download["status"] == "processing"   # but not 'completed' yet
    settings.current_download["status"] = None


def test_split_file_reports_progress(tmp_path):
    import subprocess
    src = tmp_path / "full.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "6", "-q:a", "9", str(src)], capture_output=True)
    if not src.exists():
        pytest.skip("ffmpeg not available")
    calls = []
    segs = [{"start": 0, "end": 3, "title": "A"}, {"start": 3, "end": 6, "title": "B"}]
    ch.split_file(str(src), segs, str(tmp_path / "o"), "V",
                  on_progress=lambda i, c, t: calls.append((i, c, t)))
    assert [c[0] for c in calls] == [0, 1]      # called before each segment
    assert calls[0][1] == 2                       # count


# ── secret key hygiene ───────────────────────────────────────────────────────

def test_secret_key_not_hardcoded_default():
    assert settings.SECRET_KEY != "ytmediabackup"
    assert len(settings.SECRET_KEY) >= 24


# ── API routes (Flask test client, offline) ──────────────────────────────────

@pytest.fixture
def client():
    browser_app.app.config["TESTING"] = True
    return browser_app.app.test_client()


def test_get_default_path(client):
    r = client.get("/api/get-default-path")
    assert r.status_code == 200
    assert "path" in r.get_json()


def test_check_url_requires_url(client):
    assert client.post("/api/check-url", json={}).get_json().get("error")


def test_download_requires_url(client):
    assert client.post("/api/download", json={}).get_json().get("error")


def test_download_queued_when_already_active(client):
    """A second download is queued (not rejected) while one is running."""
    settings.current_download["status"] = "downloading"
    settings.download_queue.clear()
    try:
        r = client.post("/api/download", json={"url": "https://example.com/x"})
        data = r.get_json()
        assert data.get("status") == "queued"          # queued, not started/rejected
        assert data.get("position") == 1
        assert settings.download_queue[-1]["status"] == "queued"  # no thread spawned
    finally:
        settings.current_download["status"] = None
        settings.download_queue.clear()


def test_queue_api_lists_jobs(client):
    settings.current_download["status"] = "downloading"
    settings.download_queue.clear()
    try:
        client.post("/api/download", json={"url": "https://example.com/a"})
        client.post("/api/download", json={"url": "https://example.com/b"})
        q = client.get("/api/queue").get_json()
        assert [j["url"] for j in q] == ["https://example.com/a", "https://example.com/b"]
        assert client.get("/api/download-status").get_json()["queue_pending"] == 2
    finally:
        settings.current_download["status"] = None
        settings.download_queue.clear()


def test_pending_page_renders(client):
    r = client.get("/pending")
    assert r.status_code == 200
    assert b"Pending" in r.data


def test_download_status_ok(client):
    assert client.get("/api/download-status").status_code == 200


def test_cancel_download_sets_flag_through_http(tmp_path, monkeypatch, client):
    """End-to-end proof of the fix: an HTTP cancel must be visible in settings."""
    # Redirect history writes to a temp file so the test never touches repo data.
    monkeypatch.setattr(settings, "HISTORY_FILE", str(tmp_path / "history.json"))
    settings.reset_cancel()
    r = client.post("/api/cancel-download", json={})
    assert r.get_json()["status"] == "cancelled"
    assert settings.is_cancel_requested() is True
    settings.reset_cancel()


# ── progress fallback ────────────────────────────────────────────────────────

def test_progress_hook_fragment_fallback():
    """When byte totals are absent, progress falls back to fragment counts."""
    settings.reset_cancel()
    dp = DownloadProgress(total_files=1)
    dp.progress_hook({
        "status": "downloading",
        "filename": "x.m4a",
        "downloaded_bytes": 0,
        "fragment_index": 3,
        "fragment_count": 12,
    })
    assert round(settings.current_download["progress"]) == 25
    settings.reset_cancel()


# ── links history ────────────────────────────────────────────────────────────

def test_add_and_update_link_history(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LINKS_HISTORY_FILE", str(tmp_path / "links.json"))
    settings.links_history.clear()
    entry = settings.add_link_history("https://youtu.be/abc", "audio", "single")
    assert entry["url"] == "https://youtu.be/abc"
    assert entry["status"] == "started"
    settings.update_last_link_history(title="My Song", status="completed")
    assert settings.links_history[-1]["title"] == "My Song"
    assert settings.links_history[-1]["status"] == "completed"
    settings.links_history.clear()


def test_links_history_api_newest_first(tmp_path, monkeypatch, client):
    monkeypatch.setattr(settings, "LINKS_HISTORY_FILE", str(tmp_path / "links.json"))
    settings.links_history.clear()
    settings.add_link_history("https://youtu.be/one", "audio", "single")
    settings.add_link_history("https://youtu.be/two", "video", "playlist")
    data = client.get("/api/links-history").get_json()
    assert [d["url"] for d in data] == ["https://youtu.be/two", "https://youtu.be/one"]
    assert client.post("/api/clear-links-history").get_json()["status"] == "cleared"
    assert client.get("/api/links-history").get_json() == []


def test_links_page_renders(client):
    r = client.get("/links")
    assert r.status_code == 200
    assert b"Links History" in r.data


# ── playlists manager ────────────────────────────────────────────────────────

@pytest.fixture
def pl_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "default_download_path", str(tmp_path))
    monkeypatch.setattr(settings, "download_history", [])
    # Isolate the per-playlist metadata stores so tests never touch repo data.
    monkeypatch.setattr(pl, "COLORS_FILE", str(tmp_path / "colors.json"))
    monkeypatch.setattr(pl, "SEQ_FILE", str(tmp_path / "seq.json"))
    pl._undo_stack.clear()
    pl._redo_stack.clear()
    return tmp_path


def test_list_playlists_only_multi_file(pl_root):
    _make_playlist(pl_root, "My Mix_playlist", ["a.mp3", "b.mp3"])
    _make_playlist(pl_root, "solo", ["only.mp3"])  # single file -> not a playlist
    names = [p["name"] for p in pl.list_playlists()]
    assert "My Mix_playlist" in names
    assert "solo" not in names


def test_rename_playlist(pl_root):
    p = _make_playlist(pl_root, "Old Name", ["a.mp3", "b.mp3"])
    res = pl.rename_playlist(p, "New Name")
    assert res["status"] == "success"
    assert os.path.isdir(str(pl_root / "New Name"))


def test_rename_rejects_outside_path(pl_root):
    # Path traversal guard: a path outside the download roots must be refused.
    assert pl.rename_playlist("/etc", "hacked")["status"] == "error"


def test_operation_replace_spaces(pl_root):
    p = _make_playlist(pl_root, "mix_playlist", ["a b c.mp3", "d e.mp3"])
    res = pl.apply_operation(p, "replace_spaces")
    assert res["status"] == "success" and res["renamed"] == 2
    assert sorted(os.listdir(p)) == ["a_b_c.mp3", "d_e.mp3"]


def test_operation_remove_special(pl_root):
    p = _make_playlist(pl_root, "mix_playlist", ["a*b?.mp3", "c!.mp3"])
    assert pl.apply_operation(p, "remove_special")["status"] == "success"
    assert sorted(os.listdir(p)) == ["ab.mp3", "c.mp3"]


def test_operation_number_prefix(pl_root):
    p = _make_playlist(pl_root, "mix_playlist", ["alpha.mp3", "beta.mp3"])
    assert pl.apply_operation(p, "number_prefix")["status"] == "success"
    assert sorted(os.listdir(p)) == ["01_alpha.mp3", "02_beta.mp3"]


def test_operation_truncate(pl_root):
    long_name = "This Is A Really Long Track Title That Exceeds The Limit.mp3"
    p = _make_playlist(pl_root, "mix_playlist", [long_name, "short.mp3"])
    assert pl.apply_operation(p, "truncate")["status"] == "success"
    for f in os.listdir(p):
        assert len(os.path.splitext(f)[0]) <= 35


def test_operation_remove_filler(pl_root):
    p = _make_playlist(pl_root, "mix_playlist",
                       ["Artist - Song (Official Music Video) [4K HD].mp3", "keep.mp3"])
    pl.apply_operation(p, "remove_filler")
    assert "Artist Song.mp3" in os.listdir(p)


def test_rename_collision_gets_salt(pl_root):
    # Two names that truncate to the same value must both survive (one salted).
    p = _make_playlist(pl_root, "mix_playlist", ["A" * 40 + "1.mp3", "A" * 40 + "2.mp3"])
    assert pl.apply_operation(p, "truncate")["status"] == "success"
    assert len(os.listdir(p)) == 2


def test_operation_standard_font(pl_root):
    p = _make_playlist(pl_root, "mix_playlist", ["Café Münster.mp3", "b.mp3"])
    pl.apply_operation(p, "standard_font")
    assert "Cafe Munster.mp3" in os.listdir(p)


def test_operation_camel_case(pl_root):
    p = _make_playlist(pl_root, "mix_playlist", ["hello world.mp3", "keep me.mp3"])
    pl.apply_operation(p, "camel_case")
    assert "HelloWorld.mp3" in os.listdir(p)


def test_operation_title_case_all_words(pl_root):
    p = _make_playlist(pl_root, "mix_playlist",
                       ["brad_fiedel_the terminator.mp3", "keep.mp3"])
    pl.apply_operation(p, "title_case")
    # Every word capitalized, across underscores and spaces
    assert "Brad_Fiedel_The Terminator.mp3" in os.listdir(p)


def test_remove_filler_animated(pl_root):
    p = _make_playlist(pl_root, "mix_playlist",
                       ["Cool_Animated_Short.mp3", "keep.mp3"])
    pl.apply_operation(p, "remove_filler")
    assert "Cool Short.mp3" in os.listdir(p)


def test_operation_delete_long(pl_root, monkeypatch):
    p = _make_playlist(pl_root, "mix_playlist", ["short.mp3", "long.mp3"])
    monkeypatch.setattr(pl, "_duration", lambda path: 500 if os.path.basename(path) == "long.mp3" else 100)
    res = pl.apply_operation(p, "delete_long")
    assert res["status"] == "success" and res["deleted"] == 1
    remaining = [f for f in os.listdir(p) if f != ".trash"]
    assert remaining == ["short.mp3"]
    # Undo restores the "deleted" file
    assert pl.undo_last()["status"] == "success"
    assert "long.mp3" in os.listdir(p)


def test_empty_trash(pl_root, monkeypatch):
    p = _make_playlist(pl_root, "mix_playlist", ["short.mp3", "long.mp3"])
    monkeypatch.setattr(pl, "_duration", lambda path: 500 if os.path.basename(path) == "long.mp3" else 100)
    pl.apply_operation(p, "delete_long")
    assert pl.trash_count(p) == 1
    res = pl.empty_trash(p)
    assert res["status"] == "success" and res["purged"] == 1
    assert pl.trash_count(p) == 0
    assert not os.path.isdir(os.path.join(p, ".trash"))


def test_remove_filler_camelcase(pl_root):
    p = _make_playlist(pl_root, "mix_playlist",
                       ["SongTitleOfficialVideo.mp3", "keep.mp3"])
    pl.apply_operation(p, "remove_filler")
    assert "SongTitle.mp3" in os.listdir(p)


def test_remove_filler_media_terms(pl_root):
    p = _make_playlist(pl_root, "mix_playlist",
                       ["MyShow_OST_Track01.mp3", "AnimeAMVScoreBattle.mp3"])
    pl.apply_operation(p, "remove_filler")
    got = os.listdir(p)
    assert "MyShow Track01.mp3" in got   # OST removed, unique part kept
    assert "Battle.mp3" in got           # Anime + AMV + Score removed from camelCase


def test_undo_redo_rename(pl_root):
    p = _make_playlist(pl_root, "mix_playlist", ["a b.mp3", "c d.mp3"])
    pl.apply_operation(p, "replace_spaces")
    assert sorted(f for f in os.listdir(p) if f.endswith(".mp3")) == ["a_b.mp3", "c_d.mp3"]
    assert pl.undo_last()["status"] == "success"
    assert sorted(f for f in os.listdir(p) if f.endswith(".mp3")) == ["a b.mp3", "c d.mp3"]
    assert pl.redo_last()["status"] == "success"
    assert sorted(f for f in os.listdir(p) if f.endswith(".mp3")) == ["a_b.mp3", "c_d.mp3"]


def test_playlists_api(pl_root, client):
    _make_playlist(pl_root, "api_mix_playlist", ["a.mp3", "b.mp3"])
    data = client.get("/api/playlists").get_json()
    assert any(p["name"] == "api_mix_playlist" for p in data)


def test_playlists_page_renders(client):
    r = client.get("/playlists")
    assert r.status_code == 200
    assert b"Playlists" in r.data


# ── player / media curation ──────────────────────────────────────────────────

def test_list_all_media(pl_root):
    _make_playlist(pl_root, "a_playlist", ["x.mp3", "y.mp3"])
    (pl_root / "single.mp3").write_bytes(b"z")
    names = [m["name"] for m in pl.list_all_media()]
    assert "x.mp3" in names and "single.mp3" in names


def test_delete_media_file(pl_root):
    p = _make_playlist(pl_root, "a_playlist", ["x.mp3", "y.mp3"])
    f = os.path.join(p, "x.mp3")
    assert pl.delete_media_file(f)["status"] == "success"
    assert not os.path.exists(f)
    assert os.path.isfile(os.path.join(p, ".trash", "x.mp3"))


def test_delete_media_rejects_outside(pl_root):
    assert pl.delete_media_file("/etc/hosts")["status"] == "error"


def test_add_to_folder_copies(pl_root):
    p = _make_playlist(pl_root, "a_playlist", ["x.mp3", "y.mp3"])
    f = os.path.join(p, "x.mp3")
    res = pl.add_to_folder(f, "My Curated")
    assert res["status"] == "success"
    assert os.path.isfile(os.path.join(str(pl_root), "My Curated", "x.mp3"))
    assert os.path.isfile(f)  # original kept (it's a copy)


def test_player_page_renders(client):
    r = client.get("/player")
    assert r.status_code == 200
    assert b"Player" in r.data


def test_serve_media_rejects_outside(client):
    assert client.get("/api/media?path=/etc/hosts").status_code == 404


# ── file manager ─────────────────────────────────────────────────────────────

def test_list_app_media_scopes_to_playlist_folders(pl_root):
    _make_playlist(pl_root, "a_playlist", ["x.mp3", "y.mp3"])
    (pl_root / "loose_single.mp3").write_bytes(b"z")  # loose root file, not a playlist
    names = [m["name"] for m in pl.list_app_media()]
    assert "x.mp3" in names
    assert "loose_single.mp3" not in names  # not inside a playlist folder


def test_file_stats(pl_root):
    _make_playlist(pl_root, "a_playlist", ["dup.mp3", "unique.mp3"])
    _make_playlist(pl_root, "b_playlist", ["dup.mp3", "other.mp3"])  # dup.mp3 name collision
    s = pl.file_stats()
    assert s["total"] == 4
    assert s["duplicate_names"] == 2   # the two dup.mp3


def test_global_operation_across_folders(pl_root):
    _make_playlist(pl_root, "a_playlist", ["a b.mp3"])
    _make_playlist(pl_root, "b_playlist", ["c d.mp3"])
    # single-file folders aren't "playlists" (>1), so give each 2 files
    (pl_root / "a_playlist" / "e f.mp3").write_bytes(b"x")
    (pl_root / "b_playlist" / "g h.mp3").write_bytes(b"x")
    res = pl.global_operation("replace_spaces")
    assert res["status"] == "success"
    assert "a_b.mp3" in os.listdir(str(pl_root / "a_playlist"))
    assert "g_h.mp3" in os.listdir(str(pl_root / "b_playlist"))
    # one combined undo restores everything
    pl.undo_last()
    assert "a b.mp3" in os.listdir(str(pl_root / "a_playlist"))
    assert "g h.mp3" in os.listdir(str(pl_root / "b_playlist"))


def test_file_manager_page_renders(client):
    r = client.get("/file-manager")
    assert r.status_code == 200
    assert b"File Manager" in r.data


# ── chapter / tracklist split ────────────────────────────────────────────────

def test_parse_description_segments():
    segs = ch.parse_description("0:00 Intro\n1:30 - Second Track\n3:00 Third", duration=240)
    assert [s["start"] for s in segs] == [0, 90, 180]
    assert [s["end"] for s in segs] == [90, 180, 240]
    assert segs[1]["title"] == "Second Track"


def test_parse_description_needs_two_and_monotonic():
    assert ch.parse_description("0:00 only one", 100) == []
    # non-increasing timestamps are dropped
    assert len(ch.parse_description("0:00 A\n0:00 B\n2:00 C", 200)) == 2


def test_parse_timestamp_hms():
    assert ch.parse_timestamp("1:02:03") == 3723
    assert ch.parse_timestamp("2:05") == 125


def test_chapter_segments_prefers_embedded():
    info = {"chapters": [{"start_time": 0, "end_time": 10, "title": "One"},
                         {"start_time": 10, "end_time": 20, "title": "Two"}],
            "description": "0:00 X\n0:05 Y"}
    assert [s["title"] for s in ch.chapter_segments(info, 20)] == ["One", "Two"]


def test_segment_filename_labeled_and_unlabeled():
    assert ch.segment_filename({"title": "Cool Song"}, 0, 3, "Vid") == "Cool_Song"
    # unlabeled -> NN_<video-title-summary>
    assert ch.segment_filename({"title": ""}, 2, 12, "My Big Compilation") == "03_My_Big_Compilation"


def test_split_file_integration(tmp_path):
    import subprocess
    src = tmp_path / "full.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "6", "-q:a", "9", str(src)], capture_output=True)
    if not src.exists():
        pytest.skip("ffmpeg not available")
    segs = [{"start": 0, "end": 3, "title": "One"}, {"start": 3, "end": 6, "title": ""}]
    res = ch.split_file(str(src), segs, str(tmp_path / "out"), "MyVideo")
    assert res["tracks"] == 2
    out = sorted(os.listdir(str(tmp_path / "out")))
    assert "One.mp3" in out
    assert "02_MyVideo.mp3" in out


def test_abbreviate_duplicates(pl_root):
    p = _make_playlist(pl_root, "mix_playlist",
                       ["Predator_Soundtrack_Track01.mp3",
                        "Predator_Soundtrack_Track02.mp3"])
    pl.apply_operation(p, "abbreviate_dupes")
    assert sorted(os.listdir(p)) == ["Pred_Soun_Track01.mp3", "Pred_Soun_Track02.mp3"]


def test_playlist_color_set_and_listed(pl_root, monkeypatch):
    monkeypatch.setattr(pl, "COLORS_FILE", str(pl_root / "colors.json"))
    p = _make_playlist(pl_root, "mix_playlist", ["a.mp3", "b.mp3"])
    assert pl.set_playlist_color(p, "#ff0000")["status"] == "success"
    entry = next(x for x in pl.list_playlists() if x["name"] == "mix_playlist")
    assert entry["color"] == "#ff0000"


def test_playlist_color_invalid_defaults(pl_root, monkeypatch):
    monkeypatch.setattr(pl, "COLORS_FILE", str(pl_root / "colors.json"))
    p = _make_playlist(pl_root, "mix_playlist", ["a.mp3", "b.mp3"])
    assert pl.set_playlist_color(p, "not-a-color")["color"] == "#0d6efd"


def test_list_playlists_sorted_newest_first(pl_root):
    import time
    old = _make_playlist(pl_root, "old_playlist", ["a.mp3", "b.mp3"])
    _make_playlist(pl_root, "new_playlist", ["a.mp3", "b.mp3"])
    os.utime(old, (time.time() - 10000, time.time() - 10000))
    names = [x["name"] for x in pl.list_playlists()]
    assert names.index("new_playlist") < names.index("old_playlist")


def test_sequence_fixed_and_descending(pl_root):
    import time
    a = _make_playlist(pl_root, "a_playlist", ["x.mp3", "y.mp3"])
    _make_playlist(pl_root, "b_playlist", ["x.mp3", "y.mp3"])
    os.utime(a, (time.time() - 100, time.time() - 100))  # a older, b newer
    lst = pl.list_playlists()
    seq = {p["name"]: p["seq"] for p in lst}
    assert lst[0]["name"] == "b_playlist"          # newest on top
    assert seq["b_playlist"] > seq["a_playlist"]   # newest has the higher number

    # Adding another playlist must NOT change existing (fixed) numbers.
    _make_playlist(pl_root, "c_playlist", ["x.mp3", "y.mp3"])
    lst2 = pl.list_playlists()
    seq2 = {p["name"]: p["seq"] for p in lst2}
    assert seq2["a_playlist"] == seq["a_playlist"]
    assert seq2["b_playlist"] == seq["b_playlist"]
    assert lst2[0]["name"] == "c_playlist"


def test_sequence_counts_to_99999_then_wraps(pl_root):
    """The number counts up to 99999, then wraps (user, 2026-10-19; 1.x wrapped at 1000)"""
    import time
    (pl_root / "seq.json").write_text('{"next": 99999, "orders": {}}')
    a = _make_playlist(pl_root, "a_playlist", ["x.mp3", "y.mp3"])
    _make_playlist(pl_root, "b_playlist", ["x.mp3", "y.mp3"])
    os.utime(a, (time.time() - 100, time.time() - 100))  # a -> 99999, b -> 100000
    seq = {p["name"]: p["seq"] for p in pl.list_playlists()}
    assert seq["a_playlist"] == 99999
    assert seq["b_playlist"] == 0  # 100000 % 100000 wraps to 0


def test_scan_does_not_walk_into_parent(tmp_path, monkeypatch):
    # A single (non-playlist) history entry must NOT cause the parent dir to be
    # scanned, or the download root itself / sibling folders leak in as playlists.
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(settings, "default_download_path", str(root))
    # A playlist URL grabbed in single mode: is_playlist True, but output_dir is
    # the plain download root (not a *_playlist folder). Must not scan the parent.
    monkeypatch.setattr(settings, "download_history",
                        [{"output_dir": str(root), "is_playlist": True}])
    _make_playlist(root, "mix_playlist", ["a.mp3", "b.mp3"])
    _make_playlist(tmp_path, "other", ["c.mp3", "d.mp3"])  # sibling of root -> ignored
    names = [p["name"] for p in pl.list_playlists()]
    assert "mix_playlist" in names
    assert "other" not in names


# ── ignore duplicates ─────────────────────────────────────────────────────────

@pytest.fixture
def dd_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(dd, "MANIFEST_FILE", str(tmp_path / "manifest.json"))
    dd._manifest.clear()
    return dd


def test_dedupe_concept_examples(dd_isolated):
    # "Beach_Original_music" == "Original Beach Music" (original = filler)
    assert dd.similarity("Beach_Original_music",
                         sorted(dd._tokens("Original Beach Music")),
                         dd._norm_str("Original Beach Music")) == 1.0
    # "My_Cool_video" == "This Cool Video" (my/this stop, video filler)
    assert dd.similarity("My_Cool_video",
                         sorted(dd._tokens("This Cool Video")),
                         dd._norm_str("This Cool Video")) == 1.0


def test_dedupe_distinct_titles_not_matched(dd_isolated):
    # "Predator Theme" vs "Predator Suite" -> {predator} vs {predator,suite} = 0.67 < 0.8
    s = dd.similarity("Predator Theme",
                      sorted(dd._tokens("Predator Suite")),
                      dd._norm_str("Predator Suite"))
    assert s < 0.80


def test_dedupe_by_video_id(dd_isolated):
    dd.record_download({"id": "abc123", "title": "Some Song"})
    assert dd.is_duplicate({"id": "abc123", "title": "Totally Different Name"}) is True
    assert dd.is_duplicate({"id": "zzz999", "title": "Brand New Unique Track Here"}) is False


def test_dedupe_by_fuzzy_name(dd_isolated):
    dd.record_download({"id": "id1", "title": "Original Beach Music"})
    assert dd.is_duplicate({"id": "id2", "title": "Beach_Original_music"}) is True


def test_record_download_persists_and_dedupes(dd_isolated):
    dd.record_download({"id": "v1", "title": "Song One"})
    dd.record_download({"id": "v1", "title": "Song One"})   # same id -> not duplicated
    assert len(dd._manifest) == 1
    dd.load_manifest()                                       # reloads from disk
    assert dd._manifest[0]["id"] == "v1"


def test_download_accepts_ignore_dupes_param(client):
    # Smoke: the API accepts the flag without error (no active download).
    settings.current_download["status"] = None
    settings.reset_cancel()
    r = client.post("/api/download", json={"url": "", "ignore_dupes": True})
    assert r.get_json().get("error")  # empty url still rejected -> param parsed fine


def test_faq_page_renders(client):
    r = client.get("/faq")
    assert r.status_code == 200
    assert b"FAQ" in r.data


# ── settings (user-editable text controls) ────────────────────────────────────

@pytest.fixture
def settings_isolated(tmp_path, monkeypatch):
    from modules.config import user_settings as us
    monkeypatch.setattr(us, "SETTINGS_FILE", str(tmp_path / "app_settings.json"))
    us._settings = None
    us.load_settings()
    return us


def test_settings_defaults_and_save(settings_isolated):
    us = settings_isolated
    assert "official" in us.get_filler_words()
    us.save_settings({"filler_words": ["foo", "bar"], "char_replacements": [{"from": "&", "to": "and"}]})
    assert us.get_filler_words() == {"foo", "bar"}
    assert us.get_char_replacements() == [("&", "and")]


def test_custom_filler_word_affects_remove_filler(pl_root, monkeypatch, tmp_path):
    from modules.config import user_settings as us
    monkeypatch.setattr(us, "SETTINGS_FILE", str(tmp_path / "s.json"))
    us._settings = None
    us.save_settings({"filler_words": ["banana"], "char_replacements": []})
    p = _make_playlist(pl_root, "mix_playlist", ["Cool_Banana_Song.mp3", "keep.mp3"])
    pl.apply_operation(p, "remove_filler")
    assert "Cool Song.mp3" in os.listdir(p)   # 'banana' removed per custom setting
    us._settings = None                        # reset cache for other tests


def test_apply_replacements_operation(pl_root, monkeypatch, tmp_path):
    from modules.config import user_settings as us
    monkeypatch.setattr(us, "SETTINGS_FILE", str(tmp_path / "s.json"))
    us._settings = None
    us.save_settings({"filler_words": sorted(us.DEFAULT_FILLER_WORDS),
                      "char_replacements": [{"from": "&", "to": "and"}]})
    p = _make_playlist(pl_root, "mix_playlist", ["Rock & Roll.mp3", "keep.mp3"])
    pl.apply_operation(p, "apply_replacements")
    assert "Rock and Roll.mp3" in os.listdir(p)
    us._settings = None


def test_settings_api_roundtrip(client, tmp_path, monkeypatch):
    from modules.config import user_settings as us
    monkeypatch.setattr(us, "SETTINGS_FILE", str(tmp_path / "s.json"))
    us._settings = None
    r = client.post("/api/settings", json={"filler_words": ["xyz"], "char_replacements": []})
    assert r.get_json()["filler_words"] == ["xyz"]
    assert client.get("/api/settings").get_json()["filler_words"] == ["xyz"]
    us._settings = None


def test_settings_page_renders(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert b"Settings" in r.data
