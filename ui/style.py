# ui/style.py
"""The app's own CSS: the few things the kit's `lt-` classes cannot express.

Every selector reuses kit classes and only adds an `lmd-` prefixed hook, and no
colour is written here by hand (the values come from lintheme.tokens, applied
per tint class; the kit's stylesheet stays the only other source of colour).
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402

C = tokens.COLOR


def _tint_classes():
    """History tiles and playlist badges tinted with token colours"""
    rules = []
    for name, key in (
        ("ok", "ok"),
        ("attention", "attention"),
        ("error", "error"),
    ):
        rules.append(f".lmd-tile-{name} {{ background-color: {C[key + '_bg']}; }}")
    for name, key in (
        ("accent", "accent"),
        ("ok", "ok"),
        ("busy", "busy"),
        ("attention", "attention"),
        ("error", "error"),
        ("muted", "text_muted"),
    ):
        rules.append(f".lmd-badge-{name} {{ background-color: {C[key]}; color: {C['on_accent']}; }}")
        rules.append(f".lmd-seq-{name} {{ color: {C[key]}; }}")
    return "\n".join(rules)


CSS = f"""
.lmd-dim {{ opacity: 0.55; }}
.lmd-seq {{ font-size: 20px; font-weight: 600; font-feature-settings: "tnum"; }}
.lmd-seq.lmd-seq-large {{ font-size: 30px; }}
.lt-icon-btn.lmd-tag-x {{ min-width: 32px; min-height: 32px; padding: 0; }}
.lt-pill.lmd-tag {{ padding: 0 2px 0 10px; }}
.lt-card.lmd-list {{ padding: 0; }}
.lt-card.lmd-list .lt-row {{ padding: 0 12px; }}
.lt-card.lmd-list .lt-thead {{ padding: 0 12px; }}
.lmd-options .lt-field-label {{ min-width: 0; }}
.lmd-check check {{ min-width: 18px; min-height: 18px; border-radius: 4px; background-color: transparent;
    border: 2px solid {C['border_strong']}; color: {C['on_accent']}; -gtk-icon-size: 14px; }}
.lmd-check check:checked, .lmd-check check:indeterminate {{ background-color: {C['accent']}; border-color: {C['accent']}; }}
.lmd-check:focus-visible check {{ outline: 2px solid {C['accent']}; outline-offset: 2px; }}
.lt-card.lmd-list .lt-row progressbar > trough,
.lt-card.lmd-list .lt-row progressbar > trough > progress {{ min-width: 0; }}
.lmd-selected {{ background-color: {C['accent_soft']}; box-shadow: inset 0 0 0 2px {C['accent']}; }}
.lmd-swatch {{ min-width: 44px; min-height: 32px; border-radius: 8px; border: 2px solid {C['border_strong']}; }}
{_tint_classes()}
"""

_installed = False


def install():
    """Load the app CSS once for the default display (call after Gtk is ready)."""
    global _installed
    if _installed:
        return
    provider = Gtk.CssProvider()
    if hasattr(provider, "load_from_string"):  # GTK >= 4.12
        provider.load_from_string(CSS)
    else:
        provider.load_from_data(CSS, -1)
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    _installed = True
