"""
Components for GTK 4 Lin* apps: the same building blocks as lintheme.gtk3, rebuilt on
GTK 4 (no libadwaita, which would restyle everything as Adwaita). Each component is a
plain Gtk widget (subclass or factory) styled only through `lt-` CSS classes.

Rules every component keeps (docs/05-UX.md):
- a status is an icon AND a word, never colour alone;
- every control has an accessible name; icon-only buttons get one explicitly;
- targets are at least SIZE['target_min'] px; the one main action per view is `big`;
- a disabled control says why, next to it;
- destructive actions go through `confirm(..., destructive=True)`, which names what goes.

Differences forced by GTK 4 (same names, changed mechanics):
- widgets are visible by default: no show_all(), and a hidden helper starts set_visible(False);
- containers use append()/set_child(), and a child that must expand sets hexpand/vexpand itself;
- `confirm()` cannot block (no Gtk.Dialog.run()): it shows a modal window and reports the
  answer through on_answer(bool).

Widgets are created visible-ready: just present() the window.
"""

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from lintheme import icons, status, tokens  # noqa: E402

C = tokens.COLOR


# ---------------------------------------------------------------- helpers
def css(widget, *classes):
    """Add `lt-` classes (or any) to a widget; returns it"""
    for c in classes:
        if c:
            widget.add_css_class(c)
    return widget


def uncss(widget, *classes):
    for c in classes:
        widget.remove_css_class(c)
    return widget


def name(widget, accessible_name):
    """Set the accessible name screen readers announce"""
    widget.update_property([Gtk.AccessibleProperty.LABEL], [accessible_name])
    widget._lt_name = accessible_name  # readable back: GTK 4 has no get_accessible()
    return widget


def accessible_name(widget):
    """What `name()` set on a widget (falling back to its own text), for tests.

    GTK 4 replaced ATK with the Gtk.Accessible interface, which has setters but no getter,
    so `name()` remembers what it set. Like ATK in GTK 3, a widget that was never named
    falls back to its label or text."""
    set_name = getattr(widget, "_lt_name", None)
    if set_name is not None:
        return set_name
    if hasattr(widget, "get_label"):  # buttons announce their label
        return widget.get_label() or ""
    if hasattr(widget, "get_text"):
        return widget.get_text() or ""
    return ""


def text(label, *classes, wrap=False, xalign=0.0, selectable=False):
    """A Label with classes; wrap for prose"""
    w = Gtk.Label(label=label, xalign=xalign)
    w.set_wrap(wrap)
    if wrap:
        w.set_max_width_chars(80)
    w.set_selectable(selectable)
    return css(w, *classes)


def markup(m, *classes, wrap=True):
    w = Gtk.Label(xalign=0)
    w.set_markup(m)
    w.set_wrap(wrap)
    return css(w, *classes)


def icon(icon_name, size=20, color=None, *classes):
    """A bundled Phosphor icon (recoloured; default theme text colour)"""
    img = Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(icons.pixbuf(icon_name, size, color)))
    # GTK 4 draws an Image at the theme's icon size (16 px), not the texture's size
    img.set_pixel_size(size)
    # ...and scales the texture to fill whatever it is allocated: a FILL-aligned icon in a
    # 40 px button would be drawn at 40 px. Centred, it keeps its own size.
    img.set_halign(Gtk.Align.CENTER)
    img.set_valign(Gtk.Align.CENTER)
    return css(img, *classes)


def status_icon(key, size=18):
    """The icon of a status in its colour"""
    st = status.status(key)
    colour = {"ok": C["ok"], "busy": C["busy"], "attention": C["attention"], "error": C["error"]}.get(
        key, C["text_muted"]
    )
    return icon(st.icon, size, colour)


def hbox(*children, spacing=12, expand_last=False):
    b = Gtk.Box(spacing=spacing)
    for i, ch in enumerate(children):
        last = i == len(children) - 1
        if expand_last and last:
            ch.set_hexpand(True)  # GTK 4 boxes have no pack-time expand: the child expands itself
        b.append(ch)
    return b


def vbox(*children, spacing=8):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    for ch in children:
        b.append(ch)
    return b


def spacer():
    s = Gtk.Box()
    s.set_hexpand(True)
    return s


# ---------------------------------------------------------------- buttons
def button(label, on_click=None, kind=None, small=False, big=False, tooltip=None, icon_name=None):
    """kind: None (secondary), 'primary', 'danger', 'link'"""
    b = Gtk.Button()
    if icon_name:
        b.set_child(
            hbox(
                icon(icon_name, 18, C["on_accent"] if kind == "primary" else None),
                Gtk.Label(label=label),
                spacing=8,
            )
        )
    else:
        b.set_label(label)
    if kind == "link":
        css(b, "lt-link")
    else:
        css(
            b,
            "lt-btn",
            "lt-" + kind if kind else None,
            "lt-small" if small else None,
            "lt-big" if big else None,
        )
    if on_click:
        b.connect("clicked", lambda *_: on_click())
    if tooltip:
        b.set_tooltip_text(tooltip)
    b.set_valign(Gtk.Align.CENTER)  # never stretched to a row's height
    return b


def icon_button(icon_name, accessible_name, on_click=None):
    """Icon-only button: always named for screen readers and tooltips"""
    b = css(Gtk.Button(), "lt-icon-btn")
    b.set_child(icon(icon_name, 20))
    b.set_tooltip_text(accessible_name)
    name(b, accessible_name)
    b.set_valign(Gtk.Align.CENTER)
    if on_click:
        b.connect("clicked", lambda *_: on_click())
    return b


def with_shortcut(btn, keys):
    """Show a shortcut hint (e.g. 'Ctrl+P') inside a button"""
    child = btn.get_child()
    label = child.get_text() if isinstance(child, Gtk.Label) else ""
    hint = text(keys, "lt-kbd")
    hint.set_valign(Gtk.Align.CENTER)
    box = hbox(Gtk.Label(label=label), hint, spacing=10)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)
    btn.set_child(box)  # replacing the child drops the old one: no remove() call needed
    return btn


def disabled_with_reason(btn, reason):
    """Disable a button and return a row that says why, beside it"""
    btn.set_sensitive(False)
    btn.set_tooltip_text(reason)
    return hbox(text(reason, "lt-muted"), btn, spacing=12)


# ---------------------------------------------------------------- status chip
class StatusChip(Gtk.Button):
    """Header chip: device + status word + icon. Click opens the device page."""

    def __init__(self, device="", key="none", on_click=None):
        super().__init__()
        css(self, "lt-chip")
        self.set_valign(Gtk.Align.CENTER)
        self._box = Gtk.Box(spacing=8)
        self._box.set_halign(Gtk.Align.CENTER)
        self._box.set_valign(Gtk.Align.CENTER)
        self.set_child(self._box)
        if on_click:
            self.connect("clicked", lambda *_: on_click())
        self.set_status(device, key)

    def set_status(self, device, key, detail=None):
        for c in ("lt-ok", "lt-busy", "lt-attention", "lt-error"):
            uncss(self, c)
        css(self, status.status(key).css)
        child = self._box.get_first_child()
        while child:  # GTK 4 boxes have no get_children(): walk the siblings
            nxt = child.get_next_sibling()
            self._box.remove(child)
            child = nxt
        self._box.append(status_icon(key, 18))
        words = Gtk.Label(label=status.chip_text(device, key))
        words.set_ellipsize(2)  # middle: keeps the device's start and the status word
        words.set_max_width_chars(40)
        words.set_width_chars(12)
        self._box.append(words)
        spoken = status.chip_text(device, key) + (f". {detail}" if detail else "")
        name(self, f"Device status: {spoken}. Open the device page")
        self.set_tooltip_text(detail or spoken)


# ---------------------------------------------------------------- navigation rail
class NavRail(Gtk.Box):
    """Vertical navigation: icon + label items, one active, optional count badge.

    on_select(page_id) is called when the user picks an item."""

    def __init__(self, on_select=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        css(self, "lt-rail")
        self._items, self._badges, self._labels = {}, {}, {}
        self._on_select = on_select
        # GTK 4 has no pack_end: a top box that takes the free space keeps _bottom at the bottom
        self._top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._top.set_vexpand(True)
        self._bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.append(self._top)
        self.append(self._bottom)

    def add_item(self, page_id, label, icon_name, bottom=False):
        b = css(Gtk.Button(), "lt-rail-item")
        name(b, label)
        b.set_tooltip_text(label)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        col.set_halign(Gtk.Align.CENTER)  # icon and label centred in the item, both ways
        col.set_valign(Gtk.Align.CENTER)
        over = Gtk.Overlay()
        over.set_child(icon(icon_name, tokens.SIZE["icon_nav"], None))
        badge = css(Gtk.Label(), "lt-badge")
        badge.set_halign(Gtk.Align.END)
        badge.set_valign(Gtk.Align.START)
        badge.set_visible(False)  # GTK 4 has no no_show_all: hidden until set_badge shows it
        over.add_overlay(badge)
        col.append(over)
        lab = Gtk.Label(label=label)
        col.append(lab)
        b.set_child(col)
        b.connect("clicked", lambda *_: self._on_select and self._on_select(page_id))
        (self._bottom if bottom else self._top).append(b)
        self._items[page_id], self._badges[page_id], self._labels[page_id] = b, badge, lab
        return b

    def set_active(self, page_id):
        for pid, b in self._items.items():
            (css if pid == page_id else uncss)(b, "lt-active")

    def set_badge(self, page_id, count=None, spoken=None):
        """A count badge on an item (None hides it)"""
        badge = self._badges[page_id]
        if count:
            badge.set_text(str(count))
            badge.set_visible(True)
            name(self._items[page_id], f"{self._labels[page_id].get_text()}, {spoken or count}")
        else:
            badge.set_visible(False)
            name(self._items[page_id], self._labels[page_id].get_text())

    def set_compact(self, compact):
        (css if compact else uncss)(self, "lt-compact")


# ---------------------------------------------------------------- containers
class Card(Gtk.Box):
    """A titled card: one concern per card. action=(label, callback) adds a text button."""

    def __init__(self, title=None, action=None, large=False, spacing=10):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        css(self, "lt-card", "lt-large" if large else None)
        if title or action:
            head = Gtk.Box(spacing=8)
            if title:
                title_label = text(title, "lt-heading")
                title_label.set_hexpand(True)  # the title takes the width the action leaves
                head.append(title_label)
            if action:
                head.append(button(action[0], action[1], kind="link"))
            self.append(head)

    def add_row(self, widget, expand=False):
        if expand:
            widget.set_vexpand(True)
        self.append(widget)
        return widget


def field_row(label, widget, hint=None, label_width=84):
    """'Label   [control]   hint' on one line"""
    lab = text(label, "lt-field-label")
    lab.set_size_request(label_width, -1)
    row = Gtk.Box(spacing=12)
    row.append(lab)
    if hint is None and isinstance(widget, (Gtk.DropDown, Gtk.Entry)):
        widget.set_hexpand(True)
    row.append(widget)
    if hint:
        note = text(hint, "lt-muted", wrap=True)
        note.set_max_width_chars(30)
        # a GTK 4 wrapping label asks only for its longest word; short hints must not wrap
        note.set_width_chars(min(len(hint), 30))
        row.append(note)
    return row


def key_values(pairs, value_classes=None):
    """A two-column list of (key, value); value_classes: {key: css class}"""
    grid = Gtk.Grid(column_spacing=16, row_spacing=6)
    for i, (k, v) in enumerate(pairs):
        key = text(k, "lt-muted", wrap=True)
        key.set_max_width_chars(28)
        grid.attach(key, 0, i, 1, 1)
        val = text(v, (value_classes or {}).get(k), wrap=True)
        val.set_max_width_chars(48)  # long values wrap instead of widening the window
        val.set_hexpand(True)
        val.set_xalign(1)
        val.set_justify(Gtk.Justification.RIGHT)
        grid.attach(val, 1, i, 1, 1)
    return grid


def icon_tile(icon_name):
    t = css(Gtk.Box(), "lt-icon-tile")
    img = icon(icon_name, 22, C["accent"])
    img.set_halign(Gtk.Align.CENTER)
    img.set_valign(Gtk.Align.CENTER)
    # GTK 3 packed it with expand + fill; here the image must expand itself to be centred
    img.set_hexpand(True)
    img.set_vexpand(True)
    t.append(img)
    return t


def item_row(icon_name, title, detail=None):
    """Icon tile + title + muted detail (a device, a document)"""
    info = vbox(text(title, "lt-strong"), spacing=0)
    if detail is not None:
        info.append(detail if isinstance(detail, Gtk.Widget) else text(detail, "lt-muted"))
    return hbox(icon_tile(icon_name), info, expand_last=True)


def status_line(key, words):
    """Status icon + words, e.g. 'Ready · Letter loaded'"""
    return hbox(status_icon(key, 16), text(words, "lt-muted"), spacing=6)


# ---------------------------------------------------------------- choices
SEG_GAP = 8  # px between the buttons of a segmented choice or a stepper


def keyboard_focus_ring(window):
    """Show the focus ring only while the keyboard is used: a no-op on GTK 4.

    GTK 4's :focus-visible does this by itself (a mouse click never leaves a ring), so
    unlike lintheme.gtk3 nothing has to intercept clicks. The function stays so an app's
    window setup code, and docs/05-UX.md 5.6, read the same on both toolkits."""
    return window


class Segmented(Gtk.Box):
    """2 to 4 mutually exclusive options as separate buttons (radio semantics, arrow keys move).

    GTK 4 replaced Gtk.RadioButton with grouped Gtk.ToggleButtons (set_group).
    options: [(value, label)]; on_change(value)."""

    def __init__(self, options, active=None, on_change=None, accessible_name=""):
        super().__init__()
        if not 2 <= len(options) <= 4:
            raise ValueError("Segmented takes 2 to 4 options; use Select for more")
        super().set_spacing(SEG_GAP)  # separate buttons, never joined
        css(self, "lt-seg")
        self._buttons = {}
        group = None
        for value, label in options:
            b = Gtk.ToggleButton(label=label, group=group)
            group = group or b
            self._buttons[value] = b
            self.append(b)
        self.set_value(active if active is not None else options[0][0])
        for value, b in self._buttons.items():
            b.connect("toggled", lambda btn, v=value: btn.get_active() and on_change and on_change(v))
        if accessible_name:
            name(self, accessible_name)

    def set_homogeneous(self, homogeneous):
        """Equal buttons: each fills its equal slot, so the gaps stay SEG_GAP"""
        super().set_homogeneous(homogeneous)
        for b in self._buttons.values():
            b.set_hexpand(homogeneous)  # GTK 4 has no child expand property: buttons expand themselves

    def fit_label(self, longest):
        """Size every button for the longest label it will show (e.g. 'My templates · 99'), so a
        changing label never moves the row; use with set_homogeneous(True)"""
        b = next(iter(self._buttons.values()))
        width = b.create_pango_layout(longest).get_pixel_size()[0]
        b.set_size_request(width + 2 * 14 + 2, -1)  # the label, lt-seg's 14 px padding, the border

    def get_value(self):
        return next((v for v, b in self._buttons.items() if b.get_active()), None)

    def set_value(self, value):
        self._buttons[value].set_active(True)

    def set_option_sensitive(self, value, sensitive, reason=None):
        b = self._buttons[value]
        b.set_sensitive(sensitive)
        b.set_tooltip_text(None if sensitive else reason)


class Stepper(Gtk.Box):
    """− value + (e.g. copies 1 to 99); typing is not needed, keys: +/- buttons, focusable"""

    def __init__(self, value=1, minimum=1, maximum=99, on_change=None, accessible_name="Value", unit=""):
        super().__init__()
        self.set_spacing(SEG_GAP)
        css(self, "lt-seg")
        self._v, self._min, self._max, self._cb, self._unit = value, minimum, maximum, on_change, unit
        self._minus = Gtk.Button(label="−")
        name(self._minus, f"Decrease {accessible_name.lower()}")
        self._plus = Gtk.Button(label="+")
        name(self._plus, f"Increase {accessible_name.lower()}")
        self._label = css(Gtk.Label(), "lt-value")
        self._label.set_width_chars(4 + len(unit))  # "15 mm" needs room for its unit
        self.append(self._minus)
        self.append(self._label)
        self.append(self._plus)
        self._minus.connect("clicked", lambda *_: self.set_value(self._v - 1, notify=True))
        self._plus.connect("clicked", lambda *_: self.set_value(self._v + 1, notify=True))
        name(self, accessible_name)
        self.set_value(value)

    def get_value(self):
        return self._v

    def set_range(self, minimum, maximum):
        """New limits (e.g. the printer's copies-supported); the value is clamped"""
        self._min, self._max = minimum, maximum
        self.set_value(self._v)

    def set_value(self, value, notify=False):
        self._v = max(self._min, min(self._max, value))
        self._label.set_text(f"{self._v}{self._unit}")
        self._minus.set_sensitive(self._v > self._min)
        self._plus.set_sensitive(self._v < self._max)
        if notify and self._cb:
            self._cb(self._v)


def no_wheel(widget):
    """The mouse wheel never changes this control: it scrolls the page around it instead.

    GTK 4 dropdowns change their choice on a wheel turn, so scrolling a long form past one
    silently changes a setting. Applied to every lt-select."""

    def on_scroll(ctrl, dx, dy):
        sw = widget.get_ancestor(Gtk.ScrolledWindow)
        if sw is not None:
            adj = sw.get_vadjustment()
            step = max(adj.get_step_increment(), 48)
            low, high = adj.get_lower(), adj.get_upper() - adj.get_page_size()
            adj.set_value(min(max(adj.get_value() + dy * step, low), high))
        return True  # claimed: the control itself never sees the wheel

    ctrl = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
    ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)  # ours first, before the dropdown's
    ctrl.connect("scroll", on_scroll)
    widget.add_controller(ctrl)
    widget._lt_no_wheel = ctrl  # kept for tests: GTK 4 has no scroll-event signal to emit
    return widget


class Select(Gtk.DropDown):
    """A dropdown for 5+ options, with the ComboBoxText-style id API GTK 4 dropped.

    get_active_id()/set_active_id() and options as [(id, label)] behave like the GTK 3
    select(); the ids live here, next to the string model."""

    def __init__(self, options, on_change=None):
        super().__init__(model=Gtk.StringList.new([label for _oid, label in options]))
        # from_strings() does this internally; a plain model has no expression, so items
        # would render blank until the selected item's text is looked up this way
        self.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        self._ids = [oid for oid, _label in options]
        self.set_selected(0)
        if on_change:
            self.connect("notify::selected", lambda *_: on_change(self.get_active_id()))

    def get_active_id(self):
        return self._ids[self.get_selected()]

    def set_active_id(self, active_id):
        self.set_selected(self._ids.index(active_id))


def select(options, active=None, on_change=None, accessible_name=""):
    """A dropdown (Gtk.DropDown) for 5+ options; options: [(id, label)]"""
    combo = no_wheel(css(Select(options, on_change), "lt-select"))
    if active is not None:
        combo.set_active_id(active)
    if accessible_name:
        name(combo, accessible_name)
    return combo


class SwitchRow(Gtk.Box):
    """Title + one-line description + switch (named after the title)"""

    def __init__(self, title, description=None, active=False, on_toggle=None):
        super().__init__(spacing=16)
        words = vbox(text(title, "lt-strong"), spacing=0)
        if description:
            words.append(text(description, "lt-muted", wrap=True))
        words.set_hexpand(True)
        self.append(words)
        self.switch = Gtk.Switch(active=active)
        self.switch.set_valign(Gtk.Align.CENTER)
        name(self.switch, title)
        if on_toggle:
            self.switch.connect("notify::active", lambda s, _p: on_toggle(s.get_active()))
        self.append(self.switch)


def entry(value="", placeholder="", accessible_name="", width_chars=12):
    e = css(Gtk.Entry(text=value, placeholder_text=placeholder), "lt-entry")
    e.set_width_chars(width_chars)
    if accessible_name:
        name(e, accessible_name)
    return e


def set_invalid(widget, invalid, message_label=None, message=""):
    """Mark an entry invalid and show the fix in `message_label`"""
    (css if invalid else uncss)(widget, "lt-invalid")
    if message_label is not None:
        message_label.set_text(message if invalid else "")
        (css if invalid else uncss)(message_label, "lt-error-text")


# ---------------------------------------------------------------- feedback
class Banner(Gtk.Box):
    """Inline message: kind 'ok' | 'busy' | 'attention' | 'error' | None.

    Write it as status.message(what, why, next_step); actions: [(label, callback, kind)]."""

    def __init__(self, kind, message_markup, actions=()):
        super().__init__(spacing=10)
        css(self, "lt-banner", f"lt-{kind}" if kind else None)
        if kind:
            ic = status_icon(kind, 20)
            ic.set_valign(Gtk.Align.START)
            self.append(ic)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.message = markup(message_markup)
        body.append(self.message)
        if actions:
            row = Gtk.Box(spacing=8)
            for label, cb, k in actions:
                row.append(button(label, cb, kind=k, small=True))
            body.append(row)
        body.set_hexpand(True)
        self.append(body)
        name(self, GLib.markup_escape_text(self.message.get_text()))


def pill(words, kind=None):
    """A small status word in a rounded outline (lists, tables)"""
    p = css(Gtk.Label(label=words), "lt-pill", f"lt-{kind}" if kind else None)
    p.set_halign(Gtk.Align.START)
    return p


class Gauge(Gtk.Box):
    """A level (ink, toner, battery, disk): coloured fill + outline + the number in words.

    colours: fixed physical colours, e.g. [INK cyan, magenta, yellow] stacked as stripes."""

    def __init__(self, title, percent, colours=None, low_at=None, note=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.percent, self.colours = percent, colours or [tokens.INK["black"]]
        head = Gtk.Box()
        title_label = text(title)
        title_label.set_hexpand(True)
        head.append(title_label)
        if percent is None:
            words = "Not reported"
        elif low_at is not None and percent <= low_at:
            words = f"{percent}% · Low"
        else:
            words = f"{percent}%"
        value = text(words, "lt-strong")
        if low_at is not None and percent is not None and percent <= low_at:
            css(value, "lt-attention-text")
        head.append(value)
        self.append(head)
        area = Gtk.DrawingArea()
        area.set_size_request(-1, 14)
        area.set_draw_func(self._draw)  # GTK 4 replaced the draw signal with a draw function
        self.append(area)
        if note:
            self.append(text(note, "lt-caption"))
        name(self, f"{title}: {words}")

    def _draw(self, area, cr, w, h):
        rgb = lambda hx: tuple(int(hx[i : i + 2], 16) / 255 for i in (1, 3, 5))  # noqa: E731
        cr.set_source_rgb(*rgb(tokens.PAPER["margin"]))  # a light, paper-like track: black ink stays visible
        _rounded(cr, 0.5, 0.5, w - 1, h - 1, 4)
        cr.fill_preserve()
        if self.percent is not None:
            cr.save()
            cr.clip()
            fill = (w - 2) * self.percent / 100
            band = (h - 2) / len(self.colours)
            for i, col in enumerate(self.colours):
                cr.set_source_rgb(*rgb(col))
                cr.rectangle(1, 1 + i * band, fill, band + 0.5)
                cr.fill()
            cr.restore()
        cr.set_source_rgb(*rgb(C["border_strong"]))
        cr.set_line_width(1)
        if self.percent is None:
            cr.set_dash([3, 2])
        _rounded(cr, 0.5, 0.5, w - 1, h - 1, 4)
        cr.stroke()


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def card_flow(cards, columns=3):
    """Cards side by side that reflow into fewer columns in a narrower window"""
    flow = Gtk.FlowBox()
    flow.set_selection_mode(Gtk.SelectionMode.NONE)
    flow.set_homogeneous(True)
    flow.set_max_children_per_line(columns)
    flow.set_min_children_per_line(1)
    flow.set_column_spacing(16)
    flow.set_row_spacing(16)
    for card in cards:
        flow.append(card)
    child = flow.get_first_child()
    while child:  # GTK 4 has no get_children(): walk the cells
        child.set_can_focus(False)  # the cards' own controls take focus, not the cells
        child = child.get_next_sibling()
    return flow


def scrolled(widget, min_height=-1):
    """Vertical scrolling for a pane that can outgrow the window (the options column)"""
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_propagate_natural_width(True)
    sw.set_child(widget)
    if min_height > 0:
        sw.set_min_content_height(min_height)
    return sw


def progress(fraction, accessible_name="Progress", width=320):
    bar = Gtk.ProgressBar(fraction=fraction)
    bar.set_size_request(width, -1)
    bar.set_valign(Gtk.Align.CENTER)
    name(bar, accessible_name)
    return bar


class Hero(Gtk.Box):
    """The big status block at the top of a device page"""

    def __init__(self, key, headline, lines=(), actions=()):
        super().__init__(spacing=20)
        css(self, "lt-hero", f"lt-{key}" if key in ("error", "attention") else None)
        mark = css(Gtk.Box(), "lt-hero-icon", f"lt-{key}" if key != "ok" else None)
        st = status.status(key)
        colour = {"ok": C["ok"], "busy": C["busy"], "attention": C["attention"], "error": C["error"]}.get(
            key, C["text"]
        )
        img = icon(st.icon, 30, colour)
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.CENTER)
        img.set_hexpand(True)
        img.set_vexpand(True)
        mark.append(img)
        mark.set_valign(Gtk.Align.CENTER)
        self.append(mark)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        words.append(text(headline, "lt-display"))
        self.lines = []  # the line labels, so a page can update one (e.g. "Checked 4 s ago")
        for i, line in enumerate(lines):
            label = text(line, "lt-strong" if i == len(lines) - 1 and key == "error" else None, wrap=True)
            self.lines.append(label)
            words.append(label)
        words.set_hexpand(True)
        self.append(words)
        acts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        acts.set_valign(Gtk.Align.CENTER)
        for label, cb, kind in actions:
            acts.append(button(label, cb, kind=kind))
        self.append(acts)
        name(self, f"{headline}. " + " ".join(lines))


class EmptyState(Gtk.Box):
    """Nothing here yet: icon, what will appear, and the one next action"""

    def __init__(self, icon_name, title, body, action=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        css(self, "lt-card")
        self.set_valign(Gtk.Align.FILL)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        inner.set_valign(Gtk.Align.CENTER)
        inner.set_halign(Gtk.Align.CENTER)
        circle = css(Gtk.Box(), "lt-empty-icon")
        img = icon(icon_name, 36, C["accent"])
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.CENTER)
        img.set_hexpand(True)
        img.set_vexpand(True)
        circle.append(img)
        circle.set_halign(Gtk.Align.CENTER)
        inner.append(circle)
        inner.append(text(title, "lt-heading", xalign=0.5))
        inner.append(text(body, "lt-muted", wrap=True, xalign=0.5))
        if action:
            b = button(action[0], action[1], kind="primary")
            b.set_halign(Gtk.Align.CENTER)
            inner.append(b)
        inner.set_vexpand(True)
        self.append(inner)


class StepLadder(Gtk.Box):
    """Guided steps, cheapest first: done ✓, now (highlighted), next (muted)"""

    def __init__(self, steps, current=0, done=False):
        super().__init__(spacing=8)
        self._steps, self._pills, self._done = steps, [], done
        for i, label in enumerate(steps):
            num = css(Gtk.Label(), "lt-step-num")
            num.set_valign(Gtk.Align.CENTER)  # keep it a circle, not a stretched pill
            pill_box = css(Gtk.Box(spacing=8), "lt-step")
            pill_box.append(num)
            pill_box.append(Gtk.Label(label=label))
            self._pills.append((pill_box, num))
            self.append(pill_box)
        self.set_current(current)

    def set_current(self, index):
        for i, (box, num) in enumerate(self._pills):
            for c in ("lt-done", "lt-now", "lt-next"):
                uncss(box, c)
            finished = i < index or (self._done and i == index)  # done=True: the current step fixed it
            state = "lt-done" if finished else "lt-now" if i == index else "lt-next"
            css(box, state)
            num.set_text("✓" if finished else str(i + 1))
            word = {"lt-done": "done", "lt-now": "current step", "lt-next": "not started"}[state]
            name(box, f"Step {i + 1}, {self._steps[i]}: {word}")


class ActionBar(Gtk.Box):
    """The sticky bottom bar: summary on the left, the main action on the right.

    States: idle(head, detail) · busy(words, fraction) · done(head, detail). The right side
    holds whatever buttons the page adds with add_action()."""

    def __init__(self):
        super().__init__(spacing=16)
        css(self, "lt-actionbar")
        self._left = Gtk.Stack()
        self._left.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._left.set_transition_duration(tokens.MOTION["state_ms"])
        self._head, self._detail = text("", "lt-strong"), text("", "lt-muted")
        for label in (self._head, self._detail):
            label.set_ellipsize(3)  # long summaries shorten instead of widening the window
            label.set_max_width_chars(90)
        idle = vbox(self._head, self._detail, spacing=0)
        self._left.add_named(idle, "idle")
        self._busy_words, self._bar = text("", "lt-strong"), progress(
            0, "Progress", width=240
        )  # fits half a screen
        busy = hbox(status_icon("busy", 22), vbox(self._busy_words, self._bar, spacing=6))
        self._left.add_named(busy, "busy")
        self._done_head, self._done_detail = text("", "lt-heading"), text("", "lt-muted")
        for label in (self._busy_words, self._done_head, self._done_detail):
            label.set_ellipsize(3)
            label.set_max_width_chars(90)
        mark = css(Gtk.Box(), "lt-done-mark")
        tick = icon("check", 26, C["ok"])
        tick.set_halign(Gtk.Align.CENTER)
        tick.set_valign(Gtk.Align.CENTER)
        mark.append(tick)
        done = hbox(mark, vbox(self._done_head, self._done_detail, spacing=0))
        self._left.add_named(done, "done")
        self._left.set_valign(Gtk.Align.CENTER)
        self._left.set_hexpand(True)
        self.append(self._left)
        self._right = Gtk.Box(spacing=10)
        self._right.set_valign(Gtk.Align.CENTER)
        self.append(self._right)

    def add_action(self, widget):
        self._right.append(widget)
        return widget

    def clear_actions(self):
        child = self._right.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._right.remove(child)
            child = nxt

    def idle(self, head, detail=""):
        self._head.set_text(head)
        self._detail.set_text(detail)
        self._left.set_visible_child_name("idle")

    def busy(self, words, fraction):
        self._busy_words.set_text(words)
        self._bar.set_fraction(fraction)
        name(self._bar, words)
        self._left.set_visible_child_name("busy")

    def pulse(self, words):
        """Busy with no known fraction: call repeatedly (e.g. every 200 ms)"""
        self._busy_words.set_text(words)
        self._bar.pulse()
        name(self._bar, words)
        self._left.set_visible_child_name("busy")

    def state(self):
        """'idle', 'busy' or 'done'"""
        return self._left.get_visible_child_name()

    def done(self, head, detail=""):
        self._done_head.set_text(head)
        self._done_detail.set_text(detail)
        self._left.set_visible_child_name("done")


# ---------------------------------------------------------------- dialogs
def confirm(
    parent,
    title,
    body,
    confirm_label,
    destructive=False,
    cancel_label="Cancel",
    detail_mono=None,
    on_answer=None,
):
    """Ask before acting, without blocking: on_answer(bool) gets the user's answer.

    The title asks; the buttons answer with verbs; Esc cancels. GTK 4 removed
    Gtk.Dialog.run(), so this builds the same dialog out of a modal Gtk.Window (not
    Gtk.AlertDialog, which offers no lt- styling and no verb buttons) and returns
    immediately; on_answer runs on the main loop, once, then the dialog closes."""
    dialog = Gtk.Window(transient_for=parent, modal=True, title=title)
    keyboard_focus_ring(dialog)  # a no-op on GTK 4 (:focus-visible), kept so both toolkits match
    css(dialog, "lt-root", "lt-dialog")
    area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    for m in ("start", "end", "top", "bottom"):  # GTK 4 has no border_width
        getattr(area, f"set_margin_{m}")(20)
    dialog.set_child(area)
    area.append(text(title, "lt-heading", wrap=True))
    area.append(text(body, wrap=True))
    if detail_mono:
        area.append(text(detail_mono, "lt-mono", selectable=True))
    buttons = Gtk.Box(spacing=8)
    buttons.set_halign(Gtk.Align.END)
    cancel = css(button(cancel_label), "lt-btn")
    ok = css(
        button(confirm_label),
        "lt-btn",
        "lt-danger" if destructive else "lt-primary",
        "lt-filled" if destructive else None,
    )
    buttons.append(cancel)
    buttons.append(ok)
    area.append(buttons)
    answered = False

    def answer(yes):
        nonlocal answered
        first = not answered
        answered = True
        if first and on_answer:
            on_answer(yes)
        dialog.destroy()

    cancel.connect("clicked", lambda *_: answer(False))
    ok.connect("clicked", lambda *_: answer(True))
    dialog.set_default_widget(cancel if destructive else ok)

    def on_close(*_):
        answer(False)  # the window's close button cancels, like GTK 3's dialog
        return True  # answer() destroyed the window already

    dialog.connect("close-request", on_close)

    def on_esc(*_a):
        answer(False)
        return True  # handled: nothing else in the dialog reacts to Esc

    keys = Gtk.ShortcutController()
    esc = Gtk.Shortcut.new(Gtk.KeyvalTrigger.new(Gdk.KEY_Escape, 0), Gtk.CallbackAction.new(on_esc))
    keys.add_shortcut(esc)
    dialog.add_controller(keys)
    # Focus the safe answer first: otherwise a selectable detail label takes focus and
    # GTK selects all of its text as the dialog opens
    dialog.set_focus(cancel if destructive else ok)
    dialog.present()
    return dialog
