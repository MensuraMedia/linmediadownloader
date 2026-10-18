# ui/style.py
"""The app's own CSS: the few things the kit's `lt-` classes cannot express.

Every selector reuses kit classes and only adds an `lmd-` prefixed hook, and no
colour is written here (the app's colours come from lintheme.tokens via the
kit's stylesheet; these rules only adjust opacity and padding).
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

# Dimmed rows (skipped tracks) and the track list's card, whose rows carry their
# own horizontal padding like the mockups' `.list`.
CSS = """
.lmd-dim { opacity: 0.55; }
.lt-card.lmd-list { padding: 0; }
.lt-card.lmd-list .lt-row { padding: 0 16px; }
.lt-card.lmd-list .lt-thead { padding: 0 16px; }
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
