"""
The dashboard shell for GTK 4 Lin* apps: header bar with the device status chip,
navigation rail, stacked pages. Every Lin* app is this shell plus its pages.

    win = DashboardWindow(app, "LinPrinter", "printer")
    win.add_page("print", "Print", "printer", PrintPage())
    win.add_page("activity", "Activity", "clock-counter-clockwise", ActivityPage())
    win.add_page("device", "Printer", "usb", DevicePage())
    win.add_page("settings", "Settings", "gear-six", SettingsPage(), bottom=True)
    win.chip.set_status("Canon TR150", "ok")
    win.present()

Keyboard: Alt+1…Alt+9 switch pages in rail order, through a Gtk.ShortcutController
(GTK 4 removed key-press-event). Below LAYOUT['two_pane'] px the rail goes compact and
`on_layout(mode)` is called with 'wide' or 'compact', so a page can fold its second pane
(the Print page folds its preview). GTK 4 has no size-allocate signal, and default-width
ignores maximize and tiling: before the window is shown the mode follows default-width;
once it is mapped it follows the width the window is actually given (the size_allocate
virtual method), applied on the next main-loop pass.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from lintheme import apply, tokens  # noqa: E402
from lintheme.gtk4.components import (  # noqa: E402
    NavRail,
    StatusChip,
    css,
    icon,
    icon_button,
    keyboard_focus_ring,
    text,
)


class DashboardWindow(Gtk.ApplicationWindow):
    def __init__(self, application, app_name, app_icon="printer", on_chip=None, on_menu=None):
        super().__init__(application=application, title=app_name)
        self.set_default_size(1280, 860)
        self.set_size_request(tokens.LAYOUT["min_width"], tokens.LAYOUT["min_height"])
        apply.install(self)
        keyboard_focus_ring(self)  # a no-op on GTK 4 (:focus-visible); same call as lintheme.gtk3
        self._pages, self._order, self._listeners = {}, [], []
        self._mode = None

        header = css(Gtk.HeaderBar(), "lt-header")
        brand = Gtk.Box(spacing=10)
        brand.append(icon(app_icon, 24, tokens.COLOR["accent"]))
        brand.append(text(app_name, "lt-brand"))
        self._crumb = text("", "lt-crumb")
        brand.append(self._crumb)
        header.pack_start(brand)
        menu = icon_button("dots-three", "Main menu: shortcuts, help, about", on_menu)
        header.pack_end(menu)
        self.chip = StatusChip(
            on_click=on_chip or (lambda: self.show_page(self._order[min(2, len(self._order) - 1)]))
        )
        header.pack_end(self.chip)
        self.set_titlebar(header)

        body = Gtk.Box()
        self.rail = NavRail(on_select=self.show_page)
        body.append(self.rail)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(tokens.MOTION["panel_ms"] if apply.animations_enabled() else 0)
        self.stack.set_hexpand(True)  # the stack takes the width the rail leaves (no pack-time expand)
        body.append(self.stack)
        self.set_child(body)

        keys = Gtk.ShortcutController()
        for n in range(9):  # Alt+1..Alt+9, checked against the pages that exist when pressed
            trigger = Gtk.KeyvalTrigger.new(getattr(Gdk, f"KEY_{n + 1}"), Gdk.ModifierType.ALT_MASK)
            goto = Gtk.CallbackAction.new(lambda *_a, n=n: self._goto(n))
            keys.add_shortcut(Gtk.Shortcut.new(trigger, goto))
        self.add_controller(keys)
        self._pending_mode = None
        self.connect("notify::default-width", self._on_default_width)
        self._apply_mode(self._mode_for(self.get_property("default-width")))  # before the first allocation

    # -- pages
    def add_page(self, page_id, label, icon_name, widget, bottom=False, crumb=None):
        self._pages[page_id] = (label, crumb or label)
        self._order.append(page_id)
        self.rail.add_item(page_id, label, icon_name, bottom=bottom)
        self.stack.add_named(widget, page_id)
        if len(self._order) == 1:
            self.show_page(page_id)
        return widget

    def show_page(self, page_id):
        self.stack.set_visible_child_name(page_id)
        self.rail.set_active(page_id)
        self._crumb.set_text("/ " + self._pages[page_id][1])

    def current_page(self):
        return self.stack.get_visible_child_name()

    # -- layout
    def on_layout(self, callback):
        """callback(mode): 'wide' or 'compact', now and on every change"""
        self._listeners.append(callback)
        if self._mode:
            callback(self._mode)

    @staticmethod
    def _mode_for(width):
        return "wide" if width >= tokens.LAYOUT["two_pane"] else "compact"

    def _on_default_width(self, *_a):
        if not self.get_mapped():  # not on screen yet: no allocation will tell us the width
            self._apply_mode(self._mode_for(self.get_property("default-width")))

    def do_size_allocate(self, width, height, baseline):
        Gtk.ApplicationWindow.do_size_allocate(self, width, height, baseline)
        mode = self._mode_for(width)
        if mode != self._mode and mode != self._pending_mode:
            # changing widgets during allocation would re-enter layout: switch on the next pass
            self._pending_mode = mode
            GLib.idle_add(self._apply_pending)

    def _apply_pending(self):
        mode, self._pending_mode = self._pending_mode, None
        if mode:
            self._apply_mode(mode)
        return False

    def _apply_mode(self, mode):
        if mode != self._mode:
            self._mode = mode
            self.rail.set_compact(mode == "compact")
            for cb in self._listeners:
                cb(mode)

    # -- keyboard
    def _goto(self, n):
        if n < len(self._order):
            self.show_page(self._order[n])
            return True
        return False
