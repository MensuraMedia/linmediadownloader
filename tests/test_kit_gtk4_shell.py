"""GTK 4 shell: pages, rail, chip, keyboard shortcuts, layout modes (needs a display: xvfb-run).

GTK 3 and GTK 4 cannot load in one process, so this module skips when Gtk 3.0 is already
loaded. Run the GTK 4 tests on their own process: xvfb-run -a python3 -m pytest tests/test_gtk4_*.py"""

import sys

import pytest
from conftest import requires_display

pytestmark = requires_display

gi = pytest.importorskip("gi")
if "gi.repository.Gtk" in sys.modules:  # another test module already picked a toolkit
    if sys.modules["gi.repository.Gtk"].get_major_version() != 4:
        pytest.skip("Gtk 3.0 already loaded in this process", allow_module_level=True)
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from lintheme import apply, tokens  # noqa: E402
from lintheme.gtk4.shell import DashboardWindow  # noqa: E402


@pytest.fixture(autouse=True)
def themed():
    Gtk.init()
    errors = []
    apply.install(None, errors)
    assert errors == []


@pytest.fixture()
def app():
    return Gtk.Application(application_id="org.mensuramedia.LinThemeTests4")


def children(box):
    """A Gtk.Box's children (GTK 4 removed get_children)"""
    ch, out = box.get_first_child(), []
    while ch:
        out.append(ch)
        ch = ch.get_next_sibling()
    return out


def make_window(application, n=3):
    win = DashboardWindow(application, "LinDemo", "printer")
    for i in range(n):
        win.add_page(f"p{i}", f"Page {i}", "printer", Gtk.Label(label=f"Page {i}"), bottom=(i == n - 1))
    return win


def test_pages_switch_and_update_the_rail_and_crumb(app):
    win = make_window(app)
    assert win.current_page() == "p0" and win._crumb.get_text() == "/ Page 0"
    win.show_page("p1")
    assert win.current_page() == "p1" and win._crumb.get_text() == "/ Page 1"
    assert win.rail._items["p1"].has_css_class("lt-active")
    assert not win.rail._items["p0"].has_css_class("lt-active")


def test_bottom_page_lands_in_the_rails_bottom_section(app):
    win = make_window(app)
    assert win.rail._items["p2"] in children(win.rail._bottom)
    assert win.rail._items["p0"] in children(win.rail._top)


def test_alt_number_shortcuts_switch_pages(app):
    win = make_window(app)
    assert win._goto(2) and win.current_page() == "p2"  # what the Alt+3 shortcut runs
    assert not win._goto(8) and win.current_page() == "p2"  # Alt+9 with only three pages: nothing


def test_chip_opens_the_device_page_by_default(app):
    win = make_window(app)
    win.chip.set_status("Canon TR150", "ok")
    win.chip.emit("clicked")
    assert win.current_page() == "p2"  # the third page, like the GTK 3 shell


def test_layout_modes_follow_the_window_width(app):
    seen = []
    win = make_window(app)  # built at the 1280 default: wide from the start
    win.on_layout(seen.append)
    assert seen == ["wide"]
    assert not win.rail.has_css_class("lt-compact")
    win.set_default_size(tokens.LAYOUT["two_pane"] - 1, 540)  # unmapped: default-width decides
    assert seen == ["wide", "compact"]
    assert win.rail.has_css_class("lt-compact")
    win.set_default_size(1280, 860)
    assert seen == ["wide", "compact", "wide"]


def test_a_narrow_first_window_starts_compact(app):
    win = DashboardWindow(app, "LinDemo", "printer")
    win.set_default_size(800, 540)
    win.add_page("only", "Only", "printer", Gtk.Label(label="Only"))
    assert win._mode == "compact"  # set by the initial width check, before any resize
