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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, choices=["ready", "downloading", "done", "error", "narrow"])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    setup_logging()
    icons.register()
    state = "ready" if args.state == "narrow" else args.state
    app = Gtk.Application(application_id="org.mensuramedia.LinMediaDownloader")

    def activate(application):
        window = MainWindow(application)
        if args.state == "narrow":
            window.set_default_size(720, 800)
        apply_state(window.download_page, state)

        def shoot():
            width, height = window.get_width(), window.get_height()
            paint = Gtk.WidgetPaintable.new(window)
            snapshot = Gtk.Snapshot()
            paint.snapshot(snapshot, width, height)
            texture = window.get_native().get_renderer().render_texture(snapshot.to_node(), None)
            texture.save_to_png(args.out)
            logger.info("saved %s (%s)", args.out, args.state)
            window.download_page.poller.stop()
            application.quit()
            return False

        window.present()
        GLib.timeout_add(1200, shoot)

    app.connect("activate", activate)
    raise SystemExit(app.run([sys.argv[0]]))


if __name__ == "__main__":
    main()
