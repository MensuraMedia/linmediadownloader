"""
Icons: Phosphor v2.0.8 (regular weight, MIT, lintheme/icons/LICENSE-phosphor), bundled.

The SVGs draw with currentColor; it is replaced by the requested colour (by
default the theme's text colour) before rendering, so icons follow the theme
and need no icon theme installed. Toolkit-neutral: returns a GdkPixbuf, which
GTK 3 shows with Gtk.Image.new_from_pixbuf and GTK 4 with
Gtk.Picture / Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(p)).

Add an icon: copy its SVG from ~/projects/assets/Icons/phosphoricons/regular/
into lintheme/icons/ (names and search tags: that folder's INDEX.txt). Icons only one
app uses stay in that app (resources/icons/phosphor/regular/), registered once at
start-up with add_icon_dir(); the kit's own folder is searched first.
"""

import functools
import os

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

from lintheme import tokens  # noqa: E402

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
_dirs = [ICON_DIR]


def add_icon_dir(path):
    """Also look for icons in `path` (an app's own Phosphor SVGs), after the kit's folder"""
    path = os.path.abspath(path)
    if path not in _dirs:
        _dirs.append(path)
        pixbuf.cache_clear()


def _path(name):
    for d in _dirs:
        p = os.path.join(d, f"{name}.svg")
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(f"no icon named {name!r} in {', '.join(_dirs)}")


def names():
    """Every icon name the kit and the registered app folders provide"""
    return sorted({f[:-4] for d in _dirs for f in os.listdir(d) if f.endswith(".svg")})


@functools.lru_cache(maxsize=256)
def pixbuf(name, size=20, color=None):
    """The icon `name` at `size` px in `color` (default: theme text colour)"""
    with open(_path(name), encoding="utf-8") as f:
        svg = f.read().replace("currentColor", color or tokens.COLOR["text"])
    loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
    loader.set_size(size, size)
    loader.write(svg.encode())
    loader.close()
    return loader.get_pixbuf()
