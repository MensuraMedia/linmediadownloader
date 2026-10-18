#!/usr/bin/env python3
# tests/test_ui_activity.py
# The Activity page with faked backends. Skips without a display; never the
# network, never a real download: history lives in throwaway lists, the queue
# and the snapshots come from monkeypatched jobs functions.

import sys
from datetime import datetime, timedelta

import pytest
from conftest import requires_display

pytestmark = requires_display

gi = pytest.importorskip("gi")
if "gi.repository.Gtk" in sys.modules:
    if sys.modules["gi.repository.Gtk"].get_major_version() != 4:
        pytest.skip("Gtk 3.0 already loaded in this process", allow_module_level=True)
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from lintheme.gtk4.components import accessible_name  # noqa: E402
from modules import history  # noqa: E402
from modules.config import settings  # noqa: E402
from modules.download import jobs  # noqa: E402
from modules.utils import file_utils  # noqa: E402
from ui import messages  # noqa: E402
from ui.pages import activity as activity_module  # noqa: E402
from ui.window import MainWindow  # noqa: E402

URL = "https://www.youtube.com/playlist?list=PLact1"


# -- walkers: find widgets by type/text anywhere under a container
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


def button_with_label(container, text):
    for widget in walk(container):
        if isinstance(widget, Gtk.Button) and text in label_texts(widget):
            return widget
    return None


def stamp(hours, days=0):
    day = datetime.now() - timedelta(days=days)
    when = day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=hours)
    return when.isoformat(timespec="seconds")  # history stores ISO strings


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
def quiet_backends(monkeypatch):
    monkeypatch.setattr(jobs, "status_snapshot", lambda: {"status": None, "queue_pending": 0})
    monkeypatch.setattr(jobs, "queue_snapshot", lambda: [])
    settings.download_history[:] = []
    settings.links_history[:] = []
    yield
    settings.download_history[:] = []
    settings.links_history[:] = []


@pytest.fixture()
def window(app):
    win = MainWindow(app)
    yield win
    win.activity_page.poller.stop()
    win.destroy()


@pytest.fixture()
def page(window):
    return window.activity_page


def filled_history():
    settings.download_history[:] = [
        {
            "url": f"{URL}&1",
            "title": "Neo-Tokyo Ambience",
            "status": "completed",
            "download_type": "audio",
            "is_playlist": True,
            "output_dir": "/music/neo",
            "timestamp": stamp(9),
        },
        {
            "url": f"{URL}&2",
            "title": "Bot check link",
            "status": "error",
            "download_type": "video",
            "is_playlist": False,
            "timestamp": stamp(8),
        },
        {
            "url": f"{URL}&3",
            "title": "Synth Repair Basics",
            "status": "completed",
            "download_type": "video",
            "is_playlist": False,
            "output_dir": "/videos",
            "timestamp": stamp(21, days=1),
        },
    ]
    settings.links_history[:] = [
        {
            "url": f"{URL}&4",
            "title": "Never downloaded mix",
            "status": "started",
            "download_type": "audio",
            "playlist_mode": "playlist",
            "timestamp": stamp(18),
        },
    ]


def active_snapshot():
    return {
        "status": "downloading",
        "job_id": 7,
        "playlist_title": "AKIRA OST",
        "current_file": "Kaneda.mp3",
        "message": "Downloading: Kaneda.mp3",
        "progress": 40,
        "total_progress": 37,
        "completed_files": 2,
        "total_files": 7,
        "downloaded_bytes": 1,
        "total_bytes": 2,
        "speed": 1,
        "eta": 60,
        "is_playlist": True,
        "output_path": "/music/akira",
        "tracks": {},
        "queue_pending": 1,
    }


def test_now_card_is_quiet_when_nothing_runs(page):
    assert label_texts(page.now_row) == [messages.ACT_NOW_EMPTY]


def test_now_card_shows_the_running_download(page, monkeypatch):
    monkeypatch.setattr(jobs, "status_snapshot", active_snapshot)
    monkeypatch.setattr(
        jobs,
        "queue_snapshot",
        lambda: [
            {
                "id": 7,
                "status": "active",
                "download_type": "audio",
                "playlist_mode": "playlist",
                "title": "AKIRA OST",
                "url": URL,
            }
        ],
    )
    page.refresh_now(active_snapshot())
    texts = label_texts(page.now_row)
    assert "AKIRA OST" in texts
    assert any("2 of 7" in text and "about 1 min left" in text for text in texts)
    assert any("Playlist" in text and "/music/akira" in text for text in texts)
    cancelled = []
    monkeypatch.setattr(jobs, "cancel_active_download", lambda: cancelled.append(True))
    button = button_with_label(page.now_row, messages.ACT_CANCEL)
    assert button is not None
    button.emit("clicked")
    assert cancelled == [True]


def test_queue_rows_offer_removal(page, monkeypatch):
    removed = []
    monkeypatch.setattr(jobs, "remove_queued", lambda job_id: removed.append(job_id) or True)
    monkeypatch.setattr(
        jobs,
        "queue_snapshot",
        lambda: [
            {"id": 5, "status": "active", "title": "running", "url": URL},
            {
                "id": 8,
                "status": "queued",
                "title": "Live at Montreux 1991",
                "url": f"{URL}&m",
                "download_type": "video",
                "playlist_mode": "single",
            },
        ],
    )
    page.refresh_queue()
    texts = label_texts(page.queue_rows)
    assert "Live at Montreux 1991" in texts and messages.ACT_UP_NEXT_EMPTY not in texts
    spoken = messages.ACT_REMOVE_FROM_QUEUE.format(title="Live at Montreux 1991")
    remove = next(w for w in walk(page.queue_rows) if accessible_name(w) == spoken)
    remove.emit("clicked")
    assert removed == [8]


def test_history_groups_results_and_counts(page):
    filled_history()
    page.refresh_history()
    words = label_texts(page.history_box)
    assert messages.ACT_TODAY in words and messages.ACT_YESTERDAY in words
    assert words.index(messages.ACT_TODAY) < words.index(messages.ACT_YESTERDAY)
    pills = pill_texts(page.history_box)
    assert pills.count(messages.ACT_RESULT_DONE) == 2  # two completed downloads
    assert messages.ACT_RESULT_FAILED in pills
    assert messages.ACT_RESULT_NOT_DOWNLOADED in pills
    assert messages.ACT_ENTRIES.format(n=4) in label_texts(page.history_card)


def test_search_and_the_problems_filter_narrow_the_list(page):
    filled_history()
    page.refresh_history()
    page.search.set_text("synth")
    words = label_texts(page.history_box)
    assert "Synth Repair Basics" in words and "Neo-Tokyo Ambience" not in words
    page.search.set_text("")
    page._on_filter_changed("problems")
    pills = pill_texts(page.history_box)
    assert messages.ACT_RESULT_DONE not in pills
    assert messages.ACT_RESULT_NOT_DOWNLOADED in pills


def test_show_folder_opens_the_downloads_folder(page, monkeypatch):
    filled_history()
    opened = {}
    monkeypatch.setattr(file_utils, "open_folder", lambda folder: opened.update(folder=folder))
    page.refresh_history()
    button = button_with_label(page.history_box, messages.ACT_SHOW_FOLDER)
    assert button is not None
    button.emit("clicked")
    assert opened["folder"] == "/music/neo"


def test_use_this_link_hands_the_url_to_the_download_page(page):
    filled_history()
    page.refresh_history()
    page._use_link(f"{URL}&4")
    assert page.window.current_page() == "download"
    assert page.window.download_page.link_entry.get_text() == f"{URL}&4"


def test_clear_older_asks_before_removing(page, monkeypatch):
    filled_history()
    settings.download_history.append(
        {
            "url": f"{URL}&old",
            "title": "Old thing",
            "status": "completed",
            "timestamp": stamp(10, days=40),
            "download_type": "audio",
        }
    )
    answers = {}

    def fake_confirm(_parent, title, _body, _confirm_label, **kwargs):
        answers["title"] = title
        answers["yes"] = kwargs.get("on_answer")

    monkeypatch.setattr(activity_module.kit, "confirm", fake_confirm)
    page._confirm_clear(30)
    assert "older than 30 days" in answers["title"]
    answers["yes"](True)
    assert all(entry["title"] != "Old thing" for entry in settings.download_history)


def test_remove_from_history_clears_one_entry(page):
    filled_history()
    page.refresh_history()
    entry = next(e for e in history.merged_entries() if e["title"] == "Bot check link")
    page._remove_entry(entry["id"])
    assert len(history.merged_entries()) == 3


def test_empty_history_shows_the_empty_state(page):
    assert page.history_empty.get_visible() is True
    assert messages.ACT_EMPTY_TITLE in label_texts(page.history_empty)


def test_history_scrolls_inside_its_card_so_the_window_stays_800(page, window):
    """The history list lives in a ScrolledWindow: with a full fake history the
    page's natural height stays within the 800 px window."""
    filled_history()
    for i in range(12):  # a long history would once grow the window past 800 px
        settings.download_history.append(
            {
                "url": f"{URL}&{i}",
                "title": f"Filler {i}",
                "status": "completed",
                "download_type": "audio",
                "timestamp": stamp(1 + i / 24.0, days=3),
            }
        )
    page.refresh_history()
    assert isinstance(page.history_scroll, Gtk.ScrolledWindow)
    minimum, natural = window.measure(Gtk.Orientation.VERTICAL, -1)[:2]
    assert natural <= 800, f"window wants {natural} px tall"


def test_type_tiles_are_kit_sized_squares(page):
    filled_history()
    page.refresh_history()
    row = next(
        child
        for child in walk(page.history_box)
        if isinstance(child, Gtk.Box) and child.get_parent() is page.history_box
    )
    tile = row.get_first_child()  # the row's tile
    min_w, nat_w = tile.measure(Gtk.Orientation.HORIZONTAL, -1)[:2]
    min_h, nat_h = tile.measure(Gtk.Orientation.VERTICAL, -1)[:2]
    # the kit's lt-icon-tile size (its CSS min size wins over a smaller request); never stretched
    assert min_w == nat_w == min_h == nat_h <= 48
