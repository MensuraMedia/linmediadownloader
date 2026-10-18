#!/usr/bin/env python3
"""
Component gallery (GTK 4): every lintheme.gtk4 component and state on one screen.

    python3 examples/gallery_gtk4.py
    xvfb-run -a -s "-screen 0 1400x1000x24" env GSK_RENDERER=cairo \
        python3 examples/gallery_gtk4.py --shot docs/images/gallery-gtk4.png
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from lintheme import apply, status, tokens  # noqa: E402
from lintheme.gtk4 import components as ui  # noqa: E402


def build(app=None):
    # Attached to the app, or Gtk.Application.run() quits before the --shot timer fires
    win = Gtk.ApplicationWindow(application=app, title="lintheme gallery (GTK 4)")
    win.set_default_size(1280, 860)
    apply.install(win)
    page = ui.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16), "lt-page")
    page.append(ui.text("Components and states · Graphite Night", "lt-title"))
    grid = Gtk.Grid(column_spacing=16, row_spacing=16, column_homogeneous=True)
    grid.set_vexpand(True)
    page.append(grid)

    chips = ui.Card("Status chip: icon + word, never colour alone")
    for key in ("ok", "busy", "attention", "error", "none"):
        chip = ui.StatusChip("Canon TR150", key)
        chip.set_halign(Gtk.Align.START)
        chips.add_row(chip)
    grid.attach(chips, 0, 0, 1, 1)

    buttons = ui.Card("Buttons")
    buttons.add_row(ui.hbox(ui.button("Print", kind="primary", big=True), ui.button("Secondary"), spacing=10))
    buttons.add_row(
        ui.hbox(
            ui.button("Cancel print", kind="danger"),
            ui.button("Text button", kind="link"),
            ui.icon_button("dots-three", "Main menu"),
            spacing=10,
        )
    )
    off = ui.button("Print", kind="primary", big=True)
    buttons.add_row(ui.disabled_with_reason(off, "Load paper first"))
    grid.attach(buttons, 1, 0, 1, 1)

    choices = ui.Card("Choices")
    choices.add_row(
        ui.field_row(
            "Quality", ui.Segmented([("d", "Draft"), ("n", "Normal"), ("h", "High")], "n", None, "Quality")
        )
    )
    choices.add_row(ui.field_row("Copies", ui.Stepper(2, 1, 99, accessible_name="Copies")))
    choices.add_row(
        ui.field_row("Size", ui.select([("letter", "Letter · 8.5 × 11 in"), ("a4", "A4 · 210 × 297 mm")]))
    )
    ok_entry = ui.entry("1-3, 5", accessible_name="Page range")
    choices.add_row(ui.field_row("Range", ok_entry, "4 pages"))
    bad = ui.entry("4-9", accessible_name="Page range")
    hint = ui.text("")
    ui.set_invalid(bad, True, hint, "This document has 3 pages. Try 1-3.")
    choices.add_row(ui.field_row("Range", bad))
    choices.add_row(hint)
    choices.add_row(ui.SwitchRow("Ink alerts", "Warns before printing. It never blocks printing.", True))
    grid.attach(choices, 2, 0, 1, 1)

    banners = ui.Card("Banners: what · why · next step")
    banners.add_row(ui.Banner("ok", status.message("<b>Printed 3 pages</b>", None, None)))
    banners.add_row(
        ui.Banner(
            "attention", status.message("<b>Load paper in the rear tray</b>", None, "Then press Print again")
        )
    )
    banners.add_row(
        ui.Banner(
            "error",
            status.message(
                "<b>The printer keeps dropping off USB</b>",
                "14 errors on port 3-3 in 10 minutes",
                "Try another USB cable first",
            ),
            [("Troubleshoot", None, "primary")],
        )
    )
    grid.attach(banners, 0, 1, 1, 1)

    levels = ui.Card("Gauges, pills, progress")
    levels.add_row(
        ui.Gauge("Colour", 60, [tokens.INK["cyan"], tokens.INK["magenta"], tokens.INK["yellow"]], low_at=15)
    )
    levels.add_row(ui.Gauge("Black", 8, low_at=15))
    levels.add_row(ui.Gauge("Photo black", None))
    levels.add_row(
        ui.hbox(
            ui.pill("Printed", "ok"),
            ui.pill("Stopped: USB link dropped", "error"),
            ui.pill("Queued", "busy"),
            spacing=8,
        )
    )
    levels.add_row(ui.progress(0.66, "Printing page 2 of 3", width=-1))
    grid.attach(levels, 1, 1, 1, 1)

    empty = ui.EmptyState(
        "clock-counter-clockwise",
        "Nothing printed yet",
        "Each print appears here with its settings.",
        ("Go to Print", None),
    )
    grid.attach(empty, 2, 1, 1, 1)

    page.append(
        ui.StepLadder(
            [
                "Power and cable",
                "Another USB cable",
                "Test the link",
                "Power-cycle",
                "Another socket",
                "System queues",
            ],
            2,
        )
    )
    win.set_child(page)
    return win


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot")
    a = ap.parse_args()
    app = Gtk.Application(application_id="org.mensuramedia.LinThemeGallery4")

    def activate(application):
        win = build(application)
        win.present()
        if a.shot:

            def shoot():
                w, h = win.get_width(), win.get_height()
                paint = Gtk.WidgetPaintable.new(win)
                snap = Gtk.Snapshot()
                paint.snapshot(snap, w, h)
                tex = win.get_native().get_renderer().render_texture(snap.to_node(), None)
                tex.save_to_png(a.shot)
                print("saved", a.shot)
                application.quit()
                return False

            GLib.timeout_add(1000, shoot)

    app.connect("activate", activate)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    main()
