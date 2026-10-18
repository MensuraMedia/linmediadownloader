#!/usr/bin/env python3
# tools/shot_states.py
"""Render the 2.0 window in a chosen state from fake data (no network, no
download) and save a PNG, for review against the mockups:

    xvfb-run -a venv/bin/python tools/shot_states.py --state ready --out ready.png
    for s in ready downloading done error narrow; do ...; done

States map to the four Download mockups (Main, Downloading, Done, Error) plus the
narrow window (Narrow), all using the AKIRA OST playlist the mockups use.
"""

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("GSK_RENDERER", "cairo")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from modules.config.logging_config import setup_logging  # noqa: E402
from ui import icons, messages  # noqa: E402
from ui.window import MainWindow  # noqa: E402

logger = logging.getLogger("lmd.tools.shot_states")

URL = "https://www.youtube.com/playlist?list=PLctRJ2wzOvX"
TRACKS = [
    # (id, title, seconds, skip: None | 'long' | 'duplicate')
    ("a1", "Kaneda", 222, None),
    ("a2", "Battle Against Clown", 221, "duplicate"),
    ("a3", "Winds Over the Neo-Tokyo", 171, None),
    ("a4", "Tetsuo", 620, "long"),
    ("a5", "Doll's Polyphony", 120, None),
    ("a6", "Shohmyoh", 275, None),
    ("a7", "Mutation", 218, None),
    ("a8", "Exodus from the Underground Fortress", 196, None),
    ("a9", "Illusion", 418, None),
    ("a10", "Requiem", 262, "duplicate"),
]


def fake_preview():
    """The mockups' ready state: 10 videos, 7 to download, 3 skipped"""
    entries = [
        {
            "index": i,
            "id": tid,
            "title": title,
            "duration": seconds,
            "url": f"https://www.youtube.com/watch?v={tid}",
            "skip": skip,
        }
        for i, (tid, title, seconds, skip) in enumerate(TRACKS, 1)
    ]
    return {
        "url": URL,
        "kind": "playlist",
        "title": "AKIRA OST",
        "video_title": "",
        "entries": entries,
        "error": None,
    }


def fake_active_snapshot():
    """The mockups' downloading state: file 3 of 7 at 62 percent, one link queued"""
    tracks = {}
    for tid, title, _seconds, skip in TRACKS:
        if skip == "duplicate":
            tracks[tid] = {"title": title, "state": "skipped_duplicate"}
        elif skip == "long":
            tracks[tid] = {"title": title, "state": "skipped_long"}
    tracks["a1"] = {"title": "Kaneda", "state": "done", "progress": 100}
    tracks["a3"] = {"title": "Winds Over the Neo-Tokyo", "state": "done", "progress": 100}
    tracks["a5"] = {"title": "Doll's Polyphony", "state": "downloading", "progress": 62}
    return {
        "status": "downloading",
        "job_id": 1,
        "playlist_title": "AKIRA OST",
        "current_file": "Doll's Polyphony.mp3",
        "message": "Downloading: Doll's Polyphony.mp3",
        "progress": 62,
        "total_progress": 37,
        "completed_files": 2,
        "total_files": 7,
        "downloaded_bytes": 1_400_000,
        "total_bytes": 2_300_000,
        "speed": 1_400_000,
        "eta": 1,
        "is_playlist": True,
        "output_path": os.path.expanduser("~/Music"),
        "tracks": tracks,
        "queue_pending": 1,
    }


def fake_done_snapshot():
    """The mockups' finished state: 7 done, 3 skipped"""
    tracks = {}
    for tid, title, _seconds, skip in TRACKS:
        if skip == "duplicate":
            tracks[tid] = {"title": title, "state": "skipped_duplicate"}
        elif skip == "long":
            tracks[tid] = {"title": title, "state": "skipped_long"}
        else:
            tracks[tid] = {"title": title, "state": "done", "progress": 100}
    return {
        "status": "completed",
        "job_id": 1,
        "playlist_title": "AKIRA OST",
        "current_file": "",
        "message": "Download completed successfully!",
        "progress": 100,
        "total_progress": 100,
        "completed_files": 7,
        "total_files": 7,
        "is_playlist": True,
        "output_path": os.path.expanduser("~/Music/AKIRA OST"),
        "tracks": tracks,
        "queue_pending": 0,
    }


def fake_error_preview():
    """The mockups' can't-reach state: YouTube's bot check"""
    return {
        "url": "https://www.youtube.com/watch?v=Nja0Obgg2gU&list=PLctRJ2wzOvX",
        "kind": "video",
        "title": "",
        "video_title": "",
        "entries": [],
        "error": {
            "kind": "bot_check",
            "detail": (
                "ERROR: [youtube] Nja0Obgg2gU: Sign in to confirm you're not a bot.\n"
                "HTTP Error 429: Too Many Requests (3 attempts, 10:52:04 to 10:52:41)"
            ),
        },
    }


def bind_meta(page, started_ago=0.0):
    """What submit_download would have captured for this preview"""
    return {
        "job_id": 1,
        "url": URL,
        "options": {
            "output_dir": os.path.expanduser("~/Music"),
            "download_type": "audio",
            "skip_long": True,
            "ignore_dupes": True,
        },
        "title": "AKIRA OST",
        "scope": list(page.preview["entries"]),
        "started": time.monotonic() - started_ago,
    }


def install_fake_dedupe():
    """Make the library's duplicate manifest agree with the fake data: tracks a2 and
    a10 are 'already downloaded', so the preview marks, the switch captions and the
    snapshots' skipped_duplicate states all tell the same story."""
    from modules.download import dedupe

    dedupe._manifest = [
        {"id": tid, "title": title, "tokens": []}
        for tid, title, _seconds, skip in TRACKS
        if skip == "duplicate"
    ]


def apply_state(page, state):
    install_fake_dedupe()
    if state == "ready":
        page.load_preview(fake_preview())
        page.skip_long_row.switch.set_active(True)
        page.dupes_row.switch.set_active(True)
    elif state == "downloading":
        page.load_preview(fake_preview())
        page.skip_long_row.switch.set_active(True)
        page.dupes_row.switch.set_active(True)
        page._bind_active(bind_meta(page), fake_active_snapshot())
        # the queue card shows one waiting link, like the mockup
        page.queue_message.set_text(messages.QUEUE_WAITING.format(n=1))
    elif state == "done":
        page.load_preview(fake_preview())
        page.skip_long_row.switch.set_active(True)
        page.dupes_row.switch.set_active(True)
        page._bind_active(bind_meta(page, started_ago=221.0), fake_active_snapshot())
        page.apply_snapshot(fake_done_snapshot())
    elif state == "error":
        url = fake_error_preview()["url"]
        page._setting_text = True
        page.link_entry.set_text(url)
        page._setting_text = False
        page._enter_read_error(fake_error_preview())
    else:
        raise SystemExit(f"unknown state {state!r}")


# -- Activity and Library states ------------------------------------------------
def install_fake_history():
    """A believable merged history: today, yesterday, one failure, one link that
    never became a download."""
    from datetime import datetime, timedelta

    from modules.config import settings

    def at(hours, days=0, minutes=0):
        day = datetime.now() - timedelta(days=days)
        return day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            hours=hours, minutes=minutes
        )

    settings.download_history[:] = [
        {
            "url": f"{URL}&neo",
            "title": "Neo-Tokyo Ambience",
            "status": "completed",
            "download_type": "audio",
            "is_playlist": True,
            "output_dir": "~/Music/Neo-Tokyo",
            "timestamp": at(9, minutes=58).isoformat(timespec="seconds"),
        },
        {
            "url": f"{URL}&bot",
            "title": f"{URL}&bot",
            "status": "error",
            "download_type": "video",
            "is_playlist": False,
            "timestamp": at(8, minutes=52).isoformat(timespec="seconds"),
        },
        {
            "url": f"{URL}&synth",
            "title": "Synth Repair Basics, Part 3",
            "status": "completed",
            "download_type": "video",
            "is_playlist": False,
            "output_dir": "~/Videos",
            "timestamp": at(21, days=1, minutes=14).isoformat(timespec="seconds"),
        },
        {
            "url": f"{URL}&lofi",
            "title": "Lo-fi Study Mix 2026",
            "status": "cancelled",
            "download_type": "audio",
            "is_playlist": True,
            "output_dir": "~/Music",
            "timestamp": at(19, days=1, minutes=40).isoformat(timespec="seconds"),
        },
    ]
    settings.links_history[:] = [
        {
            "url": f"{URL}&x9",
            "title": "youtube.com/playlist?list=PLx9",
            "status": "started",
            "download_type": "audio",
            "playlist_mode": "playlist",
            "timestamp": at(18, days=1, minutes=2).isoformat(timespec="seconds"),
        },
    ]


def install_fake_queue(monkeypatch=None):
    """One running job (matching the Now card) and one waiting"""
    import unittest.mock as mock

    from modules.download import jobs

    active = {
        "id": 7,
        "url": URL,
        "title": "AKIRA OST",
        "status": "active",
        "download_type": "audio",
        "playlist_mode": "playlist",
        "queued_at": "",
    }
    queued = {
        "id": 8,
        "url": f"{URL}&montreux",
        "title": "Live at Montreux 1991",
        "status": "queued",
        "download_type": "video",
        "playlist_mode": "single",
        "queued_at": "",
    }
    patch = mock.patch.object(jobs, "queue_snapshot", lambda: [active, queued])
    patch.start()
    return patch


def apply_activity_state(window):
    install_fake_history()
    queue_patch = install_fake_queue()
    window.activity_page.refresh_now(fake_active_snapshot())
    window.activity_page.refresh_queue()
    window.activity_page.refresh_history()
    window.rail.set_badge("activity", 1, spoken="1 waiting")  # like the mockup
    window.set_chip(messages.CHIP_DOWNLOADING.format(i=3, M=7), "busy")
    window.show_page("activity")
    return queue_patch


def apply_library_state(window):
    """Fake playlists, files and a real (empty-ish) temp folder for the trash"""
    from modules import playlists as library

    root = os.path.join(os.environ.get("TMPDIR", "/tmp"), "lmd-shot-library")
    playlist_dir = os.path.join(root, "AKIRA OST_playlist")
    trash = os.path.join(playlist_dir, ".trash")
    os.makedirs(trash, exist_ok=True)
    for name in ("Kaneda_theme_Lyrics_xq7m.mp3", "Tetsuo_Full_Version.mp3", "Requiem_live_2019.mp3"):
        with open(os.path.join(trash, name), "wb") as handle:
            handle.write(b"0" * 32)

    playlists = [
        {
            "name": "AKIRA OST",
            "path": playlist_dir,
            "file_count": 10,
            "total_size": 41_000_000,
            "order": 14,
            "color": "#4c9dff",
            "mtime": 1,
        },
        {
            "name": "Neo-Tokyo Ambience",
            "path": os.path.join(root, "neo"),
            "file_count": 12,
            "total_size": 58_000_000,
            "order": 13,
            "color": "#5fd38d",
            "mtime": 2,
        },
        {
            "name": "Lo-fi Study Mix 2026",
            "path": os.path.join(root, "lofi"),
            "file_count": 4,
            "total_size": 19_000_000,
            "order": 12,
            "color": "#ffbf4d",
            "mtime": 3,
        },
        {
            "name": "Synth Repair Basics",
            "path": os.path.join(root, "synth"),
            "file_count": 6,
            "total_size": 1_200_000_000,
            "order": 11,
            "color": "#ff8a80",
            "mtime": 4,
        },
        {
            "name": "Road Trip 2025",
            "path": os.path.join(root, "road"),
            "file_count": 38,
            "total_size": 160_000_000,
            "order": 10,
            "color": "#7cb7ff",
            "mtime": 5,
        },
        {
            "name": "Piano Etudes",
            "path": os.path.join(root, "piano"),
            "file_count": 24,
            "total_size": 97_000_000,
            "order": 9,
            "color": "#aab2bd",
            "mtime": 6,
        },
    ]
    files = [
        {"filename": "AKIRA - Kaneda's Theme (Official Audio).mp3", "size": 5_100_000, "duration": 222},
        {"filename": "Battle Against Clown - AKIRA 1988 HD.mp3", "size": 5_100_000, "duration": 221},
        {"filename": "Doll's Polyphony [Remastered].mp3", "size": 2_800_000, "duration": 120},
        {"filename": "Exodus from the Underground Fortress.mp3", "size": 4_500_000, "duration": 196},
        {"filename": "Illusion (Live Mix 4K).mp3", "size": 9_600_000, "duration": 418},
        {"filename": "Kaneda's theme + Lyrics.mp3", "size": 5_100_000, "duration": 224},
        {"filename": "Mutation.mp3", "size": 5_000_000, "duration": 218},
        {"filename": "Requiem - AKIRA Original Soundtrack.mp3", "size": 6_000_000, "duration": 262},
        {"filename": "Shohmyoh.mp3", "size": 6_300_000, "duration": 275},
        {
            "filename": "Winds Over the Neo-Tokyo (Official Music Video).mp3",
            "size": 3_900_000,
            "duration": 171,
        },
    ]
    preview_pairs = [
        ("Winds Over the Neo-Tokyo (Official Music Video).mp3", "Winds Over the Neo-Tokyo.mp3"),
    ] * 6  # six names change, like the mockup

    import unittest.mock as mock

    patches = [
        mock.patch.object(library, "list_playlists", lambda: [dict(p) for p in playlists]),
        mock.patch.object(library, "list_playlist_files", lambda path: [dict(f) for f in files]),
        mock.patch.object(library, "trash_count", lambda path: 3),
        mock.patch.object(library, "stack_state", lambda: {"can_undo": True, "can_redo": False}),
        mock.patch.object(library, "preview_operation", lambda path, op: preview_pairs),
        mock.patch.object(
            library, "file_stats", lambda: {"total": 214, "duplicate_names": 3, "same_size": 5}
        ),
        mock.patch.object(
            library,
            "list_all_media",
            lambda: [
                dict(
                    f, name=f["filename"], path=os.path.join(playlist_dir, f["filename"]), folder="AKIRA OST"
                )
                for f in files
            ],
        ),
    ]
    for patch in patches:
        patch.start()
    page = window.library_page
    page.refresh_sidebar()
    page.select(playlists[0])
    window.show_page("library")
    return patches


def apply_library_tidy_state(window):
    # The popover is opened by open_tidy_popover() once the window is on screen:
    # popping it up under an unmapped window hangs GTK 4.
    return apply_library_state(window)


def open_tidy_popover(window):
    """Open Tidy names with a preview showing, like the mockup"""
    page = window.library_page
    page.tidy_button.popup()
    page.tidy_button.get_popover().get_child().select("remove_filler")
    return False


def apply_confirm_trash_state(window):
    """The Dialog mockup: the kit confirm window is kept for the extra render"""
    patches = apply_library_state(window)
    dialogs = []
    real_confirm = __import__("lintheme.gtk4.components", fromlist=["confirm"]).confirm

    def capturing_confirm(parent, *args, **kwargs):
        dialog = real_confirm(parent, *args, **kwargs)
        dialogs.append(dialog)
        return dialog

    import lintheme.gtk4.components as kit

    import unittest.mock as mock

    patch = mock.patch.object(kit, "confirm", capturing_confirm)
    patch.start()
    patches.append(patch)
    window.library_page._confirm_empty_trash()  # the Dialog mockup, with real trash files
    return patches, dialogs


def shoot_widget(widget, path):
    """Paint one widget (a popover's child, a dialog window) into its own PNG"""
    width = widget.get_width() or widget.get_allocated_width()
    height = widget.get_height() or widget.get_allocated_height()
    if not width or not height:  # unallocated: fall back to the measured size
        _min_w, width = widget.measure(Gtk.Orientation.HORIZONTAL, -1)[:2]
        _min_h, height = widget.measure(Gtk.Orientation.VERTICAL, -1)[:2]
    paint = Gtk.WidgetPaintable.new(widget)
    snapshot = Gtk.Snapshot()
    paint.snapshot(snapshot, width, height)
    native = widget.get_native()
    if native is None:
        logger.warning("cannot paint %s: no native surface", path)
        return
    texture = native.get_renderer().render_texture(snapshot.to_node(), None)
    texture.save_to_png(path)
    logger.info("saved %s", path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        required=True,
        choices=[
            "ready",
            "downloading",
            "done",
            "error",
            "narrow",
            "activity",
            "library",
            "library-tidy",
            "confirm-trash",
        ],
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    setup_logging()
    icons.register()
    state = "ready" if args.state == "narrow" else args.state
    # its own id: with the real one, a running app would just be raised and this would exit
    app = Gtk.Application(application_id="org.mensuramedia.LinMediaDownloader.Shots")

    def activate(application):
        window = MainWindow(application)
        if args.state == "narrow":
            window.set_default_size(720, 800)
        if args.state in ("activity", "library", "library-tidy", "confirm-trash"):
            window.download_page.poller.stop()  # no real download follows us here
        dialogs = []
        if args.state == "activity":
            apply_activity_state(window)
        elif args.state == "library":
            apply_library_state(window)
        elif args.state == "library-tidy":
            apply_library_tidy_state(window)
        elif args.state == "confirm-trash":
            _patches, dialogs = apply_confirm_trash_state(window)
        else:
            apply_state(window.download_page, state)

        def shoot():
            width, height = window.get_width(), window.get_height()
            paint = Gtk.WidgetPaintable.new(window)
            snapshot = Gtk.Snapshot()
            paint.snapshot(snapshot, width, height)
            texture = window.get_native().get_renderer().render_texture(snapshot.to_node(), None)
            texture.save_to_png(args.out)
            logger.info("saved %s (%s)", args.out, args.state)
            # a popover and a confirm are separate surfaces: the main shot cannot
            # show them, so each is rendered beside it as its own PNG
            if args.state == "library-tidy":
                tidy = window.library_page.tidy_button.get_popover().get_child()
                shoot_widget(tidy, f"{args.out}-popover.png")
            if args.state == "confirm-trash" and dialogs:
                shoot_widget(dialogs[0], f"{args.out}-dialog.png")
            window.download_page.poller.stop()
            window.activity_page.poller.stop()
            application.quit()
            return False

        window.present()
        if args.state == "library-tidy":
            GLib.timeout_add(500, open_tidy_popover, window)
        GLib.timeout_add(1200, shoot)

    app.connect("activate", activate)
    raise SystemExit(app.run([sys.argv[0]]))


if __name__ == "__main__":
    main()
