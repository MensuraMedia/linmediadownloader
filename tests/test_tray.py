# tests/test_tray.py
# The panel icon's menu and close-to-panel rule, without the session bus: a Tray
# whose D-Bus start is skipped, and the App's close handler with fake windows.

import sys

import pytest

gi = pytest.importorskip("gi")
if "gi.repository.Gtk" in sys.modules and sys.modules["gi.repository.Gtk"].get_major_version() != 4:
    pytest.skip("Gtk 3.0 already loaded in this process", allow_module_level=True)

from ui import tray as tray_module  # noqa: E402

WORDS = {"title": "LMD", "show": "Show", "hide": "Hide", "quit": "Quit", "idle": "Ready"}


@pytest.fixture()
def tray(monkeypatch):
    monkeypatch.setattr(tray_module.Tray, "_start", lambda self: None)  # never the real panel
    events, shown = [], {"v": True}
    item = tray_module.Tray(
        "org.example.App", "/nowhere", WORDS,
        on_toggle=lambda: events.append("toggle"), on_quit=lambda: events.append("quit"),
        is_shown=lambda: shown["v"],
    )
    item.events, item.shown = events, shown
    return item


def test_menu_has_toggle_status_and_quit(tray):
    layout = tray._layout().unpack()
    revision, (root_id, _props, children) = layout
    labels = [child[1].get("label") or child[1].get("type") for child in children]
    assert labels == ["Hide", "Ready", "separator", "Quit"]
    tray.shown["v"] = False
    assert tray._items()[tray_module.TOGGLE]["label"].unpack() == "Show"


def test_clicks_toggle_and_quit(tray):
    tray._clicked(tray_module.TOGGLE)
    tray._clicked(tray_module.QUIT)
    assert tray.events == ["toggle", "quit"]


def test_status_shows_in_tooltip(tray):
    tray.set_status("Downloading · 3 of 7")
    assert tray._tooltip().unpack()[3] == "Downloading · 3 of 7"


def test_icon_pixmaps_are_argb(tmp_path):
    svg = tmp_path / "i.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
                   '<rect width="16" height="16" fill="#ff0000"/></svg>')
    pixmaps = tray_module.icon_pixmaps(str(svg))
    width, height, data = pixmaps[0]
    assert (width, height) == (16, 16) and len(data) == 16 * 16 * 4
    assert data[:4] == bytes((255, 255, 0, 0))  # alpha, red, green, blue


class FakePage:
    def __init__(self, state):
        self.state = state


class FakeWindow:
    def __init__(self, state):
        self.download_page = FakePage(state)
        self.visible = True

    def set_visible(self, on):
        self.visible = on


def test_closing_while_downloading_hides_to_the_panel(monkeypatch):
    from ui.app import App

    app = App.__new__(App)  # no GApplication registration needed for the rule
    app.tray = type("T", (), {"available": True, "window_changed": lambda self: None})()
    app._told_hidden = True  # no desktop notification from a test
    monkeypatch.setattr("ui.app.jobs.queue_snapshot", lambda: [])
    busy = FakeWindow("downloading")
    assert app._on_close(busy) is True and busy.visible is False
    idle = FakeWindow("ready")
    assert app._on_close(idle) is False  # nothing running: the window closes and the app quits
    app.tray.available = False
    assert app._on_close(FakeWindow("downloading")) is False  # no panel: never hide
