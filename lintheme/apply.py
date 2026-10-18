"""
Install the theme in a running GTK 3 or GTK 4 app.

    from lintheme import apply
    apply.install(window)          # after Gtk is imported, before or after show

It loads the generated CSS at USER priority (above the system theme, so Mint-Y,
Adwaita or any other theme can't override it), asks for the dark variant of the
system theme (dialogs, scrollbars and menus then match), adds `lt-root` to the
window, and reports CSS parsing errors instead of hiding them.
"""

import gi

from lintheme import css, tokens


def _gtk():
    """The Gtk module the app already imported (3 or 4)"""
    from gi.repository import Gtk

    return Gtk


def toolkit():
    """3 or 4: the GTK major version loaded in this process"""
    return _gtk().get_major_version()


def font_available(family=None):
    """True if the theme's font is installed (Ubuntu ships with Linux Mint and Ubuntu)"""
    family = family or tokens.FONT["family"]
    try:
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import PangoCairo

        return any(f.get_name() == family for f in PangoCairo.FontMap.get_default().list_families())
    except (ValueError, ImportError):
        return False


def install(window=None, errors=None):
    """Load the CSS for the running toolkit; returns the provider.

    errors: a list that receives (section, message) for each CSS problem."""
    Gtk = _gtk()
    major = Gtk.get_major_version()
    provider = Gtk.CssProvider()
    found = errors if errors is not None else []
    provider.connect("parsing-error", lambda _p, section, err: found.append((str(section), err.message)))
    text = css.build_css(major)
    settings = Gtk.Settings.get_default()
    if major == 3:
        from gi.repository import Gdk

        provider.load_from_data(text.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", True)
        if window is not None:
            window.get_style_context().add_class("lt-root")
    else:
        from gi.repository import Gdk

        if hasattr(provider, "load_from_string"):  # GTK >= 4.12
            provider.load_from_string(text)
        else:
            provider.load_from_data(text, -1)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", True)
        if window is not None:
            window.add_css_class("lt-root")
    if found and errors is None:
        for section, message in found:
            print(f"lintheme CSS: {section}: {message}")
    return provider


def animations_enabled():
    """False when the system turned animations off: then use 0 ms instead of tokens.MOTION"""
    settings = _gtk().Settings.get_default()
    return bool(settings and settings.get_property("gtk-enable-animations"))
