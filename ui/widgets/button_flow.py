# ui/widgets/button_flow.py
"""A row of equal-width buttons that wraps onto more lines in a narrow pane instead of
widening the window (a plain Box asks for the width of all its buttons side by side)."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def button_flow(*buttons):
    flow = Gtk.FlowBox()
    flow.set_selection_mode(Gtk.SelectionMode.NONE)
    flow.set_homogeneous(True)
    flow.set_max_children_per_line(len(buttons))
    flow.set_column_spacing(8)
    flow.set_row_spacing(8)
    flow.set_valign(Gtk.Align.START)
    for button in buttons:
        flow.append(button)
        cell = button.get_parent()
        cell.set_can_focus(False)  # the buttons take focus, not the cells
        # a hidden button hides its cell too, so it leaves no gap in the row
        cell.set_visible(button.get_visible())
        button.connect("notify::visible", lambda b, _p, c=cell: c.set_visible(b.get_visible()))
    return flow
