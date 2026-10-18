# tests/test_ui_download.py
"""The Download page against monkeypatched backends: preview reads, the option
cards, submit/cancel/finish flows, the error view, the ring and the track list.
Needs a display (desktop session or xvfb-run -a) and never touches the network:
preview.preview_link, jobs.submit_download, jobs.cancel_active_download and
jobs.status_snapshot are all fakes."""

import sys
import time

import pytest
from conftest import requires_display

pytestmark = requires_display

gi = pytest.importorskip("gi")
if "gi.repository.Gtk" in sys.modules:  # another test module already picked a toolkit
    if sys.modules["gi.repository.Gtk"].get_major_version() != 4:
        pytest.skip("Gtk 3.0 already loaded in this process", allow_module_level=True)
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from lintheme.gtk4.components import accessible_name  # noqa: E402
from modules.download import dedupe, jobs, preview  # noqa: E402
from ui import messages  # noqa: E402
from ui.window import MainWindow  # noqa: E402
from ui.pages import download as download_module  # noqa: E402

URL = "https://www.youtube.com/playlist?list=PLtest1"


def fake_preview():
    """4 videos: 1 duplicate, 1 over 7 min, 2 to download"""
    return {
        "url": URL,
        "kind": "playlist",
        "title": "Test Playlist",
        "video_title": "",
        "entries": [
            {"index": 1, "id": "v1", "title": "One", "duration": 200, "url": f"{URL}&1", "skip": None},
            {"index": 2, "id": "v2", "title": "Two", "duration": 210, "url": f"{URL}&2", "skip": "duplicate"},
            {"index": 3, "id": "v3", "title": "Three", "duration": 500, "url": f"{URL}&3", "skip": "long"},
            {"index": 4, "id": "v4", "title": "Four", "duration": 220, "url": f"{URL}&4", "skip": None},
        ],
        "error": None,
    }


def active_snapshot(tracks=None):
    return {
        "status": "downloading",
        "job_id": 7,
        "playlist_title": "Test Playlist",
        "current_file": "Four.mp3",
        "message": "Downloading: Four.mp3",
        "progress": 50,
        "total_progress": 50,
        "completed_files": 1,
        "total_files": 2,
        "downloaded_bytes": 500_000,
        "total_bytes": 1_000_000,
        "speed": 500_000,
        "eta": 90,
        "is_playlist": True,
        "output_path": "/tmp",
        "tracks": (
            tracks
            if tracks is not None
            else {
                "v1": {"title": "One", "state": "done", "progress": 100},
                "v4": {"title": "Four", "state": "downloading", "progress": 50},
            }
        ),
        "queue_pending": 0,
    }


def done_snapshot():
    tracks = {
        "v1": {"title": "One", "state": "done", "progress": 100},
        "v2": {"title": "Two", "state": "skipped_duplicate"},
        "v3": {"title": "Three", "state": "skipped_long"},
        "v4": {"title": "Four", "state": "done", "progress": 100},
    }
    snap = active_snapshot(tracks)
    snap.update(
        status="completed",
        current_file="",
        message="Download completed",
        progress=100,
        total_progress=100,
        completed_files=2,
        queue_pending=0,
    )
    return snap


def wait_until(condition, timeout=5.0):
    """Drive the default main context until condition() holds (workers report via idle_add)"""
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition never became true"
        GLib.MainContext.default().iteration(False)
        time.sleep(0.005)


@pytest.fixture(scope="module")  # one registration on the session bus per module
def app():
    Gtk.init()  # PyGObject needs it before the first Gtk.Application
    from ui.app import App

    application = App(application_id="org.mensuramedia.LinMediaDownloaderTests." + __name__.rsplit(".", 1)[-1].replace("_", ""))
    application.register(None)  # runs do_startup: the real app actions and accelerators
    return application


@pytest.fixture()
def window(app, monkeypatch):
    # no download is running and none is queued while pages are built
    monkeypatch.setattr(jobs, "status_snapshot", lambda: {"status": None, "queue_pending": 0})
    win = MainWindow(app)
    yield win
    page = win.download_page
    if page._typing_timer is not None:  # a pending read must not fire into the next test
        GLib.source_remove(page._typing_timer)
        page._typing_timer = None
    page._read_generation += 1  # any worker still in flight is stale now
    page.poller.stop()
    win.destroy()


@pytest.fixture()
def page(window):
    return window.download_page


def read_link(page, monkeypatch, result=None, error=None):
    """Point preview.preview_link at a fake and read the URL like typing would"""
    calls = []
    monkeypatch.setattr(dedupe, "_manifest", [{"id": "v2", "title": "Two", "tokens": []}])

    def fake_preview_link(url, skip_long=False, ignore_dupes=False):
        calls.append(url)
        if error is not None:
            return {
                "url": url,
                "kind": "video",
                "title": "",
                "video_title": "",
                "entries": [],
                "error": error,
            }
        return result or fake_preview()

    monkeypatch.setattr(preview, "preview_link", fake_preview_link)
    page._setting_text = True
    page.link_entry.set_text(URL)
    page._setting_text = False
    page.start_read(URL)
    return calls


def test_first_launch_shows_an_empty_ready_page(page):
    assert page.state == "empty"
    assert page.primary_btn is not None and not page.primary_btn.get_sensitive()
    assert not page.get_controls.get_sensitive()
    assert page.right_stack.get_visible_child_name() == "empty"
    assert accessible_name(page.link_entry) == messages.LINK_NAME
    assert window_chip_text(page) == page.window._tools[0]


def window_chip_text(page):
    """The chip's full sentence (tooltip and accessible name)"""
    return page.window.chip.get_tooltip_text()


def window_chip_word(page):
    """What the pill shows: the status word only"""
    return page.window.chip.get_child().get_first_child().get_next_sibling().get_text()


def test_read_a_playlist_to_ready(page, monkeypatch):
    calls = read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    assert calls == [URL]
    assert page.get_controls.get_sensitive()
    assert page.right_stack.get_visible_child_name() == "list"
    assert "4 videos" in page.pane_counts.get_text() and "2 to download" in page.pane_counts.get_text()
    assert page.primary_btn.get_sensitive()
    assert "2 tracks" in actionbar_head(page)
    assert "Audio MP3" in actionbar_head(page)
    assert page.playlist_reason.get_visible() is False
    counts = page.track_list.counts()
    assert counts["skip"] == 2 and counts["pending"] == 2


def actionbar_head(page):
    return page.actionbar._head.get_text()


def test_stale_read_results_are_ignored(page, monkeypatch):
    calls = read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    page.start_read(URL)  # same link: no new read
    assert calls == [URL]
    page._setting_text = True
    page.link_entry.set_text("https://other.example/w")
    page._setting_text = False
    page._read_generation += 1  # what a newer read does to an older one
    page._read_finished(1, URL, fake_preview())  # the late answer for the old link
    assert page.state == "ready"
    assert page.preview["url"] == URL


def test_toggling_skip_long_remarks_the_preview(page, monkeypatch):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    page.dupes_row.switch.set_active(True)
    page.skip_long_row.switch.set_active(False)
    marks = [e["skip"] for e in page.preview["entries"]]
    assert marks == [None, "duplicate", None, None]
    assert page.track_list.counts()["skip"] == 1
    assert "1 you have" in actionbar_caption(page)


def actionbar_caption(page):
    return page.actionbar._detail.get_text()


def test_download_runs_and_finishes(page, monkeypatch, tmp_path):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    submitted = {}

    def fake_submit(url, options):
        submitted["url"], submitted["options"] = url, options
        return {"status": "started", "job_id": 7}

    snaps = {"current": active_snapshot()}
    monkeypatch.setattr(jobs, "submit_download", fake_submit)
    monkeypatch.setattr(jobs, "status_snapshot", lambda: snaps["current"])
    page.start_download()
    wait_until(lambda: page.state == "downloading")
    assert submitted["url"] == URL
    assert submitted["options"]["download_type"] == "audio"
    assert submitted["options"]["playlist_mode"] == "playlist"
    assert submitted["options"]["skip_long"] is False
    assert page.primary_btn.get_sensitive()
    assert messages.CANCEL in button_label(page.primary_btn)
    assert "Downloading 2 of 2" in page.actionbar._busy_words.get_text()
    assert "Downloading · 2 of 2" in window_chip_text(page)
    assert window_chip_word(page) == "Downloading"

    snaps["current"] = done_snapshot()
    wait_until(lambda: page.state == "done")
    assert "Downloaded 2 tracks" in page.actionbar._head.get_text()
    assert messages.OPEN_FOLDER in button_label(page.primary_btn)
    counts = page.track_list.counts()
    assert counts["done"] == 2 and counts["skip"] == 2

    opened = {}
    from modules.utils import file_utils

    monkeypatch.setattr(file_utils, "open_folder", lambda folder: opened.update(folder=folder) or {})
    page.open_done_folder()
    assert opened["folder"] == submitted["options"]["output_dir"]


def button_label(btn):
    label = btn.get_child()
    if isinstance(label, Gtk.Label):
        return label.get_text()
    text = ""
    child = label.get_first_child()
    while child:
        if isinstance(child, Gtk.Label):
            text += child.get_text()
        child = child.get_next_sibling()
    return text


def test_cancel_calls_the_backend_once(page, monkeypatch, app):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    monkeypatch.setattr(jobs, "submit_download", lambda url, options: {"status": "started", "job_id": 7})
    cancelled = []
    monkeypatch.setattr(jobs, "cancel_active_download", lambda: cancelled.append(True))
    monkeypatch.setattr(jobs, "status_snapshot", active_snapshot)
    page.start_download()
    wait_until(lambda: page.state == "downloading")
    cancel = app.lookup_action("cancel")
    assert cancel.get_enabled()  # Escape is live only while downloading
    cancel.activate(None)  # what Escape runs
    page.cancel_running_download()  # a second click while cancelling: no double cancel
    assert len(cancelled) == 1
    assert not page.primary_btn.get_sensitive()


def test_queued_download_keeps_the_page_ready(page, monkeypatch):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    monkeypatch.setattr(
        jobs,
        "submit_download",
        lambda url, options: {"status": "queued", "job_id": 8, "position": 2},
    )
    monkeypatch.setattr(jobs, "status_snapshot", lambda: {"status": None, "queue_pending": 1})
    page.start_download()
    wait_until(lambda: page.poller.running)
    assert page.state == "ready"
    assert (
        messages.QUEUED_AHEAD.format(position=2)
        in page.link_status.get_first_child().get_first_child().get_next_sibling().get_text()
    )


def test_read_error_shows_the_plain_words_and_disables_download(page, monkeypatch):
    read_link(
        page,
        monkeypatch,
        error={"kind": "bot_check", "detail": "ERROR: [youtube] x: Sign in to confirm"},
    )
    wait_until(lambda: page.state == "error")
    assert page.right_stack.get_visible_child_name() == "error"
    assert messages.ERRORS["bot_check"]["title"] == page._last_error_title
    assert actionbar_head(page) == messages.AB_ERROR_HEAD  # the bar names the next step,
    assert actionbar_caption(page) == messages.AB_ERROR_CAPTION  # not the error again
    assert not page.primary_btn.get_sensitive()
    assert not page.get_controls.get_sensitive()
    assert "Can't reach · YouTube" in window_chip_text(page)
    assert "Sign in to confirm" in page.detail_text.get_text()


def test_try_again_rereads_the_link(page, monkeypatch):
    calls = read_link(
        page,
        monkeypatch,
        error={"kind": "network", "detail": "unable to download webpage"},
    )
    wait_until(lambda: page.state == "error")
    # the next read succeeds
    monkeypatch.setattr(preview, "preview_link", lambda *a, **k: fake_preview())
    page._try_again()
    wait_until(lambda: page.state == "ready")
    assert len(calls) == 1  # first failed read; the retry went through the new fake


def test_format_and_playlist_choices_drive_the_options(page, monkeypatch):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    submitted = {}
    monkeypatch.setattr(
        jobs,
        "submit_download",
        lambda url, options: submitted.update(options=options) or {"status": "started", "job_id": 9},
    )
    monkeypatch.setattr(jobs, "status_snapshot", active_snapshot)
    page.format_seg.set_value("video")
    assert page.quality_row.get_visible()
    page.quality_seg.set_value("480")
    page.get_seg.set_value("first")
    page.stepper.set_value(3, notify=True)
    page.start_download()
    assert submitted["options"]["video_quality"] == "480"
    assert submitted["options"]["limit"] == 3
    assert submitted["options"]["playlist_mode"] == "playlist"
    assert page.state == "downloading"


def test_more_options_reveal_stays_open(page, monkeypatch):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    assert not page.split_row.get_visible()
    page._toggle_more()
    assert page.split_row.get_visible()
    page.skip_long_row.switch.set_active(True)
    assert page.split_row.get_visible()  # still open after the refresh


def test_ring_words_and_fraction(page):
    page.ring.set_progress(0.5, 2, 4)
    assert accessible_name(page.ring) == "Overall progress 50 percent, 2 of 4 files"
    page.done_ring.set_complete(4)
    assert accessible_name(page.done_ring) == "All 4 files downloaded"


def test_track_list_holds_long_playlists(page):
    entries = [
        {"index": i, "id": f"t{i}", "title": f"Track {i}", "duration": 100 + i, "url": f"u{i}", "skip": None}
        for i in range(1, 501)
    ]
    started = time.monotonic()
    page.track_list.set_entries(entries)
    assert page.track_list.store.get_n_items() == 500
    states = {f"t{i}": {"title": f"Track {i}", "state": "done", "progress": 100} for i in range(1, 501)}
    page.track_list.apply_states(states)
    assert page.track_list.counts()["done"] == 500
    assert time.monotonic() - started < 5.0  # half a thousand rows, still quick


def test_narrow_layout_folds_the_preview_into_the_strip(window, page, monkeypatch):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    window.set_default_size(720, 800)  # unmapped: default-width decides, like the shell test
    assert window._mode == "compact"
    assert page.strip.get_visible()
    assert not page.right.get_visible()
    page._toggle_strip()
    assert page.right.get_visible()
    assert page.strip_button.get_child().get_text() == messages.HIDE_LIST


def test_chip_shows_the_word_and_keeps_the_sentence(window, page, monkeypatch):
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    full = window_chip_text(page)
    assert window_chip_word(page) == "Ready"  # wide or narrow: the status word alone
    window.set_default_size(720, 800)
    assert window._mode == "compact"
    assert window_chip_word(page) == "Ready"
    chip = page.window.chip
    assert chip.get_tooltip_text() == full
    assert accessible_name(chip) == f"Status: {full}"


def test_counts_agree_when_the_download_finds_more_duplicates(page, monkeypatch):
    """One source of truth: an entry is skipped if the preview marked it OR the
    download reported it skipped; every number on screen comes from that merge."""
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    monkeypatch.setattr(jobs, "submit_download", lambda url, options: {"status": "started", "job_id": 7})
    tracks = {
        "v1": {"title": "One", "state": "done", "progress": 100},
        "v2": {"title": "Two", "state": "skipped_duplicate"},  # the preview knew
        "v3": {"title": "Three", "state": "skipped_long"},  # the preview knew
        "v4": {"title": "Four", "state": "skipped_duplicate"},  # the download re-checked
    }
    snap = active_snapshot(tracks)
    snap["status"] = "downloading"
    monkeypatch.setattr(jobs, "status_snapshot", lambda: snap)
    page.start_download()
    wait_until(lambda: page.state == "downloading")
    assert "Downloading · 1 of 1" in window_chip_text(page)
    assert "1 of 1 files" in accessible_name(page.ring)
    assert "Downloading 1 of 1" in page.actionbar._busy_words.get_text()
    assert page.this_skip_label.get_text() == "2 you have · 1 over 7 min"
    assert page.track_list.counts()["skip"] == 3

    snap.update(status="completed", current_file="", message="Download completed")
    wait_until(lambda: page.state == "done")
    assert "Downloaded 1 track" in page.actionbar._head.get_text()
    assert "did not finish" not in page.actionbar._detail.get_text()
    assert "Skipped 2 you already have and 1 over 7 min" in page.actionbar._detail.get_text()
    assert page.done_ring._complete is True  # the end moment: full ring with the check
    assert accessible_name(page.done_ring) == "All 1 files downloaded"


def test_nothing_downloaded_is_not_shown_as_success(page, monkeypatch):
    """Every track failed (YouTube's bot check): attention ring with a dash, the reason, Try again"""
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    snaps = {"current": active_snapshot()}
    submits = []
    monkeypatch.setattr(
        jobs,
        "submit_download",
        lambda url, options: submits.append(url) or {"status": "started", "job_id": 9},
    )
    monkeypatch.setattr(jobs, "status_snapshot", lambda: snaps["current"])
    page.start_download()
    wait_until(lambda: page.state == "downloading")
    failed = active_snapshot({})
    failed.update(
        status="completed_with_errors",
        completed_files=0,
        current_file="",
        errors=["ERROR: [youtube] x: Sign in to confirm you\u2019re not a bot."],
    )
    snaps["current"] = failed
    wait_until(lambda: page.state == "done")
    assert page.done_ring._nothing and not page.done_ring._complete
    assert page.done_headline.get_text() == messages.DONE_NOTHING
    assert page.done_stats.get_text() == messages.ERRORS["bot_check"]["title"]
    assert not page.done_play.get_visible()
    assert page.actionbar.state() == "idle"  # no success tick in the bar
    assert page.actionbar._head.get_text().startswith(messages.DONE_NOTHING)
    assert messages.RETRY_DOWNLOAD in button_label(page.primary_btn)
    assert "Can't reach" in window_chip_text(page)
    snaps["current"] = active_snapshot()
    page.primary_btn.emit("clicked")  # Try again runs the same download
    wait_until(lambda: page.state == "downloading")
    assert len(submits) == 2


def test_paste_buttons_keep_their_width(page):
    assert page.link_entry.get_hexpand()
    for entry in (page.link_entry, page.queue_entry, page.another_entry):
        paste = entry.get_next_sibling()
        assert not paste.get_hexpand() and not paste.compute_expand(0)


def test_done_card_names_the_saved_file_and_shows_it(page, monkeypatch, tmp_path):
    """The file on disk can be renamed from the title: the card says where it went"""
    read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    snaps = {"current": active_snapshot()}
    monkeypatch.setattr(jobs, "submit_download", lambda url, options: {"status": "started", "job_id": 11})
    monkeypatch.setattr(jobs, "status_snapshot", lambda: snaps["current"])
    page.start_download()
    wait_until(lambda: page.state == "downloading")
    saved = tmp_path / "Beethoven_7th_Symphony_Complete.mp3"
    finished = done_snapshot()
    finished["tracks"]["v1"]["path"] = str(saved)
    snaps["current"] = finished
    wait_until(lambda: page.state == "done")
    shown = []
    monkeypatch.setattr(download_module.file_utils, "show_file", shown.append)
    assert page.done_saved.get_text().startswith("Saved") and page.done_show.get_visible()
    page.done_show.emit("clicked")
    assert shown and shown[0] in page._done_files


def test_heading_shows_the_plain_name():
    assert download_module.display_name("Beethoven - 7th Symphony (Complete) ✔") == "Beethoven - 7th Symphony"
    assert download_module.display_name("Song [HD] (Official Video)") == "Song"
    assert download_module.display_name("(Live)") == "(Live)"  # never empty


def test_a_video_with_parts_offers_split_and_lists_them(page, monkeypatch):
    result = {
        "url": URL, "kind": "video", "title": "Symphony (Complete) ✔", "video_title": "", "error": None,
        "entries": [{"index": 1, "id": "b7", "title": "Symphony", "duration": 2507, "url": URL, "skip": None}],
        "chapters": [
            {"index": i, "id": f"part-{i}", "title": "", "start": s, "end": e, "duration": e - s}
            for i, (s, e) in enumerate([(0, 882), (882, 1421), (1421, 1976), (1976, 2507)], 1)
        ],
    }
    read_link(page, monkeypatch, result=result)
    wait_until(lambda: page.state == "ready")
    assert page.split_row.get_visible() and page.split_row.get_sensitive()  # opened and offered
    assert page.track_list.store.get_n_items() == 1  # off: one video
    page.split_row.switch.set_active(True)
    assert page.split_chapters is True
    names = [page.track_list.store.get_item(i).title for i in range(page.track_list.store.get_n_items())]
    assert names == ["Part 1 of 4", "Part 2 of 4", "Part 3 of 4", "Part 4 of 4"]
    submitted = {}
    monkeypatch.setattr(jobs, "submit_download", lambda url, options: submitted.update(options) or {"status": "queued", "job_id": 3, "position": 1})
    page.start_download()
    assert submitted["split_chapters"] is True


def _finish_one_download(page, monkeypatch):
    snaps = {"current": active_snapshot()}
    monkeypatch.setattr(jobs, "submit_download", lambda url, options: {"status": "started", "job_id": 21})
    monkeypatch.setattr(jobs, "status_snapshot", lambda: snaps["current"])
    page.start_download()
    wait_until(lambda: page.state == "downloading")
    snaps["current"] = done_snapshot()
    wait_until(lambda: page.state == "done")


def test_a_link_pasted_after_a_download_brings_back_download(page, monkeypatch):
    """The user's report: after a finished download, a new link showed no Download button"""
    calls = read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    _finish_one_download(page, monkeypatch)
    other = URL + "&next"
    page.get_display().get_clipboard().set(other)
    page.another_paste_button.emit("clicked")  # the Paste button in "Download another"
    wait_until(lambda: page.state == "ready")
    assert calls[-1] == other  # the new link was read (the fake preview answers with its own URL)
    assert messages.DOWNLOAD in button_label(page.primary_btn) and page.primary_btn.get_sensitive()


def test_typing_in_download_another_reads_it_too(page, monkeypatch):
    calls = read_link(page, monkeypatch)
    wait_until(lambda: page.state == "ready")
    _finish_one_download(page, monkeypatch)
    page.another_entry.set_text(URL)  # the same link again, typed or Ctrl+V
    wait_until(lambda: page.state == "ready", timeout=5)
    assert calls.count(URL) == 2 and messages.DOWNLOAD in button_label(page.primary_btn)
