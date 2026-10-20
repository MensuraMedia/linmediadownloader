# ui/widgets/ring.py
"""The overall-progress ring (the 1.x ring, kept for 2.0): a Cairo drawing of a
168 px circle with a 12 px stroke, the percentage in display type and the file
count as a caption; full and checked in the ok colour once everything is done.

Colours come from lintheme.tokens (track = border, arc = accent, done = ok); the
accessible label says the same numbers in words.
"""

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
import cairo  # noqa: E402
from gi.repository import Gtk, Pango, PangoCairo  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4.components import name  # noqa: E402
from ui import messages  # noqa: E402

SIZE = 168
STROKE = 12
RADIUS = 70
C = tokens.COLOR


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


class ProgressRing(Gtk.DrawingArea):
    """set_progress(fraction, done, total) while downloading; set_complete(total) after."""

    def __init__(self, scale=1.0):
        """scale draws the whole ring smaller or larger (the done ring is half size)"""
        super().__init__()
        self._scale = scale
        self.set_content_width(round(SIZE * scale))  # no set_content_size() in this python3-gi
        self.set_content_height(round(SIZE * scale))
        self.set_draw_func(self._draw)
        self._fraction = 0.0
        self._done_count = 0
        self._total = 0
        self._complete = False
        self._nothing = False
        name(self, messages.RING_A11Y_DONE.format(total=0))

    def set_progress(self, fraction, done_count, total):
        """Advance the arc; `done_count` of `total` files finished (words shown in the middle)."""
        self._fraction = max(0.0, min(1.0, fraction or 0.0))
        self._done_count, self._total, self._complete, self._nothing = done_count, total, False, False
        name(
            self,
            messages.RING_A11Y_PROGRESS.format(
                p=int(round(self._fraction * 100)), done=done_count, total=total
            ),
        )
        self.queue_draw()

    def set_complete(self, total):
        """All files downloaded: full ring in the ok colour with a check."""
        self._fraction, self._done_count, self._total, self._complete = 1.0, total, total, True
        self._nothing = False
        name(self, messages.RING_A11Y_DONE.format(total=total))
        self.queue_draw()

    def set_nothing(self):
        """Nothing was downloaded: full ring in the attention colour with a dash, never a check"""
        self._fraction, self._done_count, self._complete, self._nothing = 0.0, 0, False, True
        name(self, messages.RING_A11Y_NOTHING)
        self.queue_draw()

    # -- drawing
    def _draw(self, area, cr, width, height):
        cr.scale(self._scale, self._scale)  # everything below is drawn on the 168 px grid
        cx = cy = SIZE / 2
        cr.set_line_width(STROKE)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        if self._nothing:
            cr.set_source_rgb(*_rgb(C["attention"]))
            cr.new_sub_path()
            cr.arc(cx, cy, RADIUS, 0, 2 * math.pi)
            cr.stroke()
            cr.set_line_width(10)
            cr.move_to(cx - 26, cy)
            cr.line_to(cx + 26, cy)
            cr.stroke()
            return
        if self._complete:
            cr.set_source_rgb(*_rgb(C["ok"]))
            cr.new_sub_path()
            cr.arc(cx, cy, RADIUS, 0, 2 * math.pi)
            cr.stroke()
            self._check(cr)
            return
        cr.set_source_rgb(*_rgb(C["border"]))
        cr.new_sub_path()
        cr.arc(cx, cy, RADIUS, 0, 2 * math.pi)
        cr.stroke()
        if self._fraction > 0:
            cr.set_source_rgb(*_rgb(C["accent"]))
            cr.new_sub_path()
            cr.arc(cx, cy, RADIUS, -math.pi / 2, -math.pi / 2 + 2 * math.pi * self._fraction)
            cr.stroke()
        self._text(cr)

    def _check(self, cr):
        """The mockups' check: (62,86) to (77,101) to (107,69), rounded joins"""
        cr.set_source_rgb(*_rgb(C["ok"]))
        cr.set_line_width(10)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.move_to(62, 86)
        cr.line_to(77, 101)
        cr.line_to(107, 69)
        cr.stroke()

    def _text(self, cr):
        pct = int(round(self._fraction * 100))
        self._label(cr, f"{pct}%", tokens.TYPE["display"], C["text"], 84)
        count = messages.RING_COUNT.format(done=self._done_count, total=self._total)
        self._label(cr, count, tokens.TYPE["caption"], C["text_muted"], 108)

    def _label(self, cr, words, spec, colour, baseline_y):
        size, _line, weight = spec
        layout = self.create_pango_layout(words)
        font = Pango.FontDescription.from_string(tokens.FONT["family"])
        font.set_absolute_size(size * Pango.SCALE)  # type tokens are pixels, not points
        font.set_weight(Pango.Weight.MEDIUM if weight >= 500 else Pango.Weight.NORMAL)
        layout.set_font_description(font)
        layout_width = layout.get_pixel_size()[0]
        cr.set_source_rgb(*_rgb(colour))
        cr.move_to((SIZE - layout_width) / 2, baseline_y - size)
        PangoCairo.show_layout(cr, layout)
