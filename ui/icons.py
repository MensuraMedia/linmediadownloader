#!/usr/bin/env python3
# ui/icons.py
# The app's own Phosphor icons (resources/icons/phosphor/regular/), registered with
# lintheme so lintheme.gtk4.components.icon() finds them next to the kit's icons.

import os

from lintheme import icons

APP_ICON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "icons", "phosphor", "regular"
)

# Every icon the 2.0 screens use (docs/design/mockups-gtk4/), kit icons included, so a
# test can prove each one exists: a missing icon draws nothing and fails silently.
USED = (
    # rail and header
    "download-simple",
    "clock-counter-clockwise",
    "music-notes",
    "gear-six",
    "files",
    "dots-three",
    # status (lintheme.status)
    "check-circle",
    "circle-notch",
    "hand",
    "link-break",
    # Download
    "link",
    "clipboard-text",
    "music-note",
    "film-strip",
    "folder-simple",
    "folder-open",
    "copy",
    "arrow-clockwise",
    "x",
    "play",
    # Activity, Library, Settings
    "magnifying-glass",
    "pencil-simple",
    "text-aa",
    "caret-down",
    "arrow-counter-clockwise",
    "arrow-down",
    "trash",
    "pause",
    "skip-back",
    "skip-forward",
    "speaker-high",
    "minus",
    "plus",
)


def register():
    """Make the app's icons available to lintheme (call once at start-up)"""
    icons.add_icon_dir(APP_ICON_DIR)
