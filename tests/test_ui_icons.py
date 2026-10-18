#!/usr/bin/env python3
# tests/test_ui_icons.py
# Every icon the 2.0 screens use resolves to a bundled Phosphor SVG and renders.

import os

from lintheme import icons
from ui import icons as app_icons


def test_every_used_icon_exists_and_renders():
    app_icons.register()
    missing = [n for n in app_icons.USED if n not in icons.names()]
    assert missing == []
    for n in app_icons.USED:
        assert icons.pixbuf(n, 20).get_width() == 20


def test_app_icons_ship_with_their_licence():
    assert 'LICENSE-phosphor' in os.listdir(app_icons.APP_ICON_DIR)


def test_no_pill_carries_a_checkmark():
    """The user asked for no checkmark in any pill (2026-10-18)"""
    from ui.pages import activity
    from ui.widgets import track_list

    tables = list(track_list.ACTIVE_PILLS.values()) + list(activity.RESULT_PILLS.values())
    assert not [row for row in tables if row[0] and row[0].startswith("check")]
