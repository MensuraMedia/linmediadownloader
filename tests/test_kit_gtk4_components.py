"""GTK 4 components: behaviour and accessible names (needs a display: xvfb-run).

GTK 3 and GTK 4 cannot load in one process, so this module skips when Gtk 3.0 is already
loaded (a full pytest run loads it through the GTK 3 tests). Run the GTK 4 tests on their
own process: xvfb-run -a python3 -m pytest tests/test_gtk4_*.py"""

import importlib.util
import os
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

from lintheme import apply  # noqa: E402
from lintheme.gtk4 import components as ui  # noqa: E402


@pytest.fixture(autouse=True)
def themed():
    Gtk.init()
    errors = []
    apply.install(None, errors)
    assert errors == []


def children(box):
    """A Gtk.Box's children (GTK 4 removed get_children)"""
    ch, out = box.get_first_child(), []
    while ch:
        out.append(ch)
        ch = ch.get_next_sibling()
    return out


def test_segmented_value_and_callback():
    seen = []
    seg = ui.Segmented([("d", "Draft"), ("n", "Normal"), ("h", "High")], "n", seen.append, "Quality")
    assert seg.get_value() == "n"
    seg.set_value("h")
    assert seg.get_value() == "h" and seen[-1] == "h"
    assert ui.accessible_name(seg) == "Quality"
    with pytest.raises(ValueError):
        ui.Segmented([("a", "A")])


def test_stepper_clamps_and_disables_ends():
    st = ui.Stepper(1, 1, 99, accessible_name="Copies")
    assert not st._minus.get_sensitive()
    st.set_value(500)
    assert st.get_value() == 99 and not st._plus.get_sensitive()
    assert ui.accessible_name(st._plus) == "Increase copies"


def test_status_chip_speaks_device_and_state():
    chip = ui.StatusChip("Canon TR150", "error")
    assert "Can't reach" in ui.accessible_name(chip)
    assert chip.has_css_class("lt-error")
    chip.set_status("Canon TR150", "ok")
    assert chip.has_css_class("lt-ok") and not chip.has_css_class("lt-error")


def test_rail_active_and_badge():
    rail = ui.NavRail()
    rail.add_item("print", "Print", "printer")
    rail.add_item("activity", "Activity", "clock-counter-clockwise")
    rail.set_active("activity")
    assert rail._items["activity"].has_css_class("lt-active")
    rail.set_badge("activity", 1, "1 job printing")
    assert rail._badges["activity"].get_visible()
    assert ui.accessible_name(rail._items["activity"]) == "Activity, 1 job printing"
    rail.set_badge("activity", None)
    assert not rail._badges["activity"].get_visible()
    assert ui.accessible_name(rail._items["activity"]) == "Activity"


def test_action_bar_switches_state_before_show():
    bar = ui.ActionBar()
    bar.done("Printed 3 pages", "62 s")
    assert bar._left.get_visible_child_name() == "done"
    bar.busy("Printing page 2 of 3", 0.5)
    assert bar._left.get_visible_child_name() == "busy"


def test_step_ladder_names_each_step():
    ladder = ui.StepLadder(["Cable", "Test the link", "Power-cycle"], 1)
    names = [ui.accessible_name(box) for box, _n in ladder._pills]
    assert names == [
        "Step 1, Cable: done",
        "Step 2, Test the link: current step",
        "Step 3, Power-cycle: not started",
    ]


def test_icon_buttons_and_disabled_reasons_are_explained():
    b = ui.icon_button("dots-three", "Main menu")
    assert ui.accessible_name(b) == "Main menu" and b.get_tooltip_text() == "Main menu"
    assert ui.accessible_name(ui.button("Print", kind="primary", big=True)) == "Print"  # label fallback
    pb = ui.button("Print", kind="primary", big=True)
    row = ui.disabled_with_reason(pb, "Load paper first")
    assert not pb.get_sensitive()
    assert any(isinstance(w, Gtk.Label) and w.get_text() == "Load paper first" for w in children(row))


def test_gauge_says_low_in_words():
    g = ui.Gauge("Black", 8, low_at=15)
    assert ui.accessible_name(g) == "Black: 8% · Low"
    assert ui.accessible_name(ui.Gauge("Photo black", None)) == "Photo black: Not reported"


def test_gallery_gtk4_builds_every_component():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "gallery_gtk4.py"
    )
    spec = importlib.util.spec_from_file_location("gallery_gtk4", path)
    gallery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gallery)
    win = gallery.build()
    assert win.get_child() is not None  # the whole gallery page built without a display-visible run


def test_stepper_range_and_action_bar_pulse():
    st = ui.Stepper(50, 1, 99, accessible_name="Copies")
    st.set_range(1, 20)
    assert st.get_value() == 20 and not st._plus.get_sensitive()
    bar = ui.ActionBar()
    bar.pulse("Sending 2 pages…")
    assert bar.state() == "busy"


def test_keyboard_focus_ring_is_a_noop():
    window = Gtk.Window()
    assert ui.keyboard_focus_ring(window) is window  # :focus-visible already does the job


def test_select_ignores_the_mouse_wheel():
    """Scrolling past a dropdown must not change it"""
    combo = ui.select([("a", "A"), ("b", "B"), ("c", "C")], "a")
    ctrl = combo._lt_no_wheel
    assert ctrl.get_propagation_phase() == Gtk.PropagationPhase.CAPTURE  # before the dropdown's own
    assert ctrl.emit("scroll", 0.0, 1.0) is True  # claimed: the default handler never runs
    assert combo.get_active_id() == "a"


def test_homogeneous_segmented_buttons_fill_equal_slots():
    seg = ui.Segmented([("a", "Documents"), ("b", "Envelopes"), ("c", "My templates")])
    seg.set_homogeneous(True)
    seg.fit_label("My templates · 99")
    for b in seg._buttons.values():
        assert b.get_hexpand()
    minimum, natural = seg.measure(Gtk.Orientation.HORIZONTAL, -1)[:2]
    assert natural >= 3 * seg._buttons["a"].get_size_request()[0]  # three slots, each fitting the longest


def test_confirm_answers_through_the_callback():
    answers = []
    window = Gtk.Window()
    dialog = ui.confirm(
        window,
        "Delete the saved profiles?",
        "This removes the two profiles you saved.",
        "Delete",
        destructive=True,
        detail_mono="/home/user/.config/lindemo/profiles",
        on_answer=answers.append,
    )
    assert dialog.get_modal() and dialog.get_transient_for() is window
    area = dialog.get_child()  # content box: title, body, mono, then the button row
    buttons = children(children(area)[-1])
    assert ui.accessible_name(buttons[0]) == "Cancel" and ui.accessible_name(buttons[1]) == "Delete"
    buttons[1].emit("clicked")  # the verb answers
    assert answers == [True]
    dialog = ui.confirm(window, "Start the copy?", "2 pages, 300 dpi.", "Start", on_answer=answers.append)
    dialog.emit("close-request")  # the window's close button cancels, like Esc
    assert answers == [True, False]
