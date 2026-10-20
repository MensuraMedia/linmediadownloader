# ui/tray.py
"""The panel (system tray) icon: click it to hide or show the window, so a download
keeps running out of the way (user, 2026-10-19).

GTK 4 has no tray API and the usual libraries (XApp.StatusIcon, AyatanaAppIndicator)
link GTK 3, which cannot load beside GTK 4. So this speaks the freedesktop
StatusNotifierItem protocol over D-Bus directly, with a com.canonical.dbusmenu menu:
Cinnamon (xapp-sn-watcher), KDE, and GNOME with the AppIndicator extension show it.
When no panel takes the icon, Tray.available stays False and closing the window
quits as before. Nothing here may break the app: every D-Bus error is logged only.
"""

import logging
import os

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gio, GLib  # noqa: E402

logger = logging.getLogger("lmd.ui.tray")

ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
WATCHER = ("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher")
ICON_SIZES = (16, 22, 24, 32, 48)

ITEM_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg name="status" type="s"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg type="i" name="id"/>
      <arg type="u" name="timestamp"/>
    </signal>
  </interface>
</node>
"""

# menu item ids
TOGGLE, STATUS, SEPARATOR, QUIT = 1, 2, 3, 4


def icon_pixmaps(svg_path):
    """The icon as ARGB32 (network byte order) pixmaps, for panels that ignore IconThemePath"""
    pixmaps = []
    for size in ICON_SIZES:
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(svg_path, size, size)
        except GLib.Error:
            continue
        if not pixbuf.get_has_alpha():
            pixbuf = pixbuf.add_alpha(False, 0, 0, 0)
        width, height, stride = pixbuf.get_width(), pixbuf.get_height(), pixbuf.get_rowstride()
        data = pixbuf.get_pixels()
        argb = bytearray()
        for y in range(height):
            row = data[y * stride : y * stride + width * 4]
            for x in range(0, width * 4, 4):
                r, g, b, a = row[x : x + 4]
                argb += bytes((a, r, g, b))
        pixmaps.append((width, height, bytes(argb)))
    return pixmaps


class Tray:
    """One panel icon for the app.

    words: dict with 'title', 'show', 'hide', 'quit', 'idle' (the status line when nothing runs).
    on_toggle(): hide or show the window. on_quit(): leave the app.
    is_shown(): whether the window is on screen (for the menu's Show/Hide word)."""

    def __init__(self, app_id, icon_dir, words, on_toggle, on_quit, is_shown):
        self.app_id = app_id
        self.icon_dir = icon_dir
        self.words = words
        self.on_toggle, self.on_quit, self.is_shown = on_toggle, on_quit, is_shown
        self.available = False
        self.status_text = words["idle"]
        self._revision = 1
        self._bus = None
        self._ids = []
        self._name_id = 0
        svg = os.path.join(icon_dir, "hicolor", "scalable", "apps", f"{app_id}.svg")
        self._pixmaps = icon_pixmaps(svg) if os.path.isfile(svg) else []
        try:
            self._start()
        except Exception:
            logger.exception("the panel icon could not start; the window works without it")

    # ================================================================ setup
    def _start(self):
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        item_info = Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0]
        menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self._ids.append(
            self._bus.register_object(ITEM_PATH, item_info, self._item_call, self._item_get, None)
        )
        self._ids.append(
            self._bus.register_object(MENU_PATH, menu_info, self._menu_call, self._menu_get, None)
        )
        self.bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._name_id = Gio.bus_own_name_on_connection(
            self._bus, self.bus_name, Gio.BusNameOwnerFlags.NONE, self._named, None
        )
        # a panel restarted later (Cinnamon reload) brings up a new watcher: register again
        Gio.bus_watch_name_on_connection(
            self._bus, WATCHER[0], Gio.BusNameWatcherFlags.NONE, lambda *_a: self._register(), None
        )

    def _named(self, *_args):
        self._register()

    def _register(self):
        if self._bus is None:
            return
        self._bus.call(
            WATCHER[0],
            WATCHER[1],
            WATCHER[2],
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self.bus_name,)),
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
            self._registered,
        )

    def _registered(self, bus, result):
        try:
            bus.call_finish(result)
            self.available = True
            logger.info("panel icon registered as %s", self.bus_name)
        except GLib.Error as error:
            self.available = False
            logger.info("no panel takes tray icons (%s); closing the window quits", error.message)

    def stop(self):
        if self._bus is None:
            return
        for reg_id in self._ids:
            self._bus.unregister_object(reg_id)
        if self._name_id:
            Gio.bus_unown_name(self._name_id)
        self._ids, self._name_id, self.available = [], 0, False

    # ================================================================ updates
    def set_status(self, text):
        """The words under the icon (tooltip) and in the menu, e.g. 'Downloading · 3 of 7'"""
        if text == self.status_text:
            return
        self.status_text = text
        self._emit_item("NewToolTip")
        self._emit_menu_props([(STATUS, {"label": GLib.Variant("s", text)})])

    def window_changed(self):
        """The window was shown or hidden: the menu's first item says the other"""
        self._emit_menu_props([(TOGGLE, {"label": GLib.Variant("s", self._toggle_label())})])

    def _emit_item(self, signal):
        if self._bus is None:
            return
        try:
            self._bus.emit_signal(None, ITEM_PATH, "org.kde.StatusNotifierItem", signal, None)
        except GLib.Error:
            logger.debug("emitting %s failed", signal, exc_info=True)

    def _emit_menu_props(self, changes):
        if self._bus is None:
            return
        try:
            self._bus.emit_signal(
                None,
                MENU_PATH,
                "com.canonical.dbusmenu",
                "ItemsPropertiesUpdated",
                GLib.Variant("(a(ia{sv})a(ias))", (changes, [])),
            )
        except GLib.Error:
            logger.debug("updating the panel menu failed", exc_info=True)

    # ================================================================ the item
    def _tooltip(self):
        return GLib.Variant("(sa(iiay)ss)", ("", [], self.words["title"], self.status_text))

    def _item_get(self, _bus, _sender, _path, _iface, prop):
        values = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", self.app_id),
            "Title": GLib.Variant("s", self.words["title"]),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", self.app_id),
            "IconThemePath": GLib.Variant("s", self.icon_dir),
            "IconPixmap": GLib.Variant("a(iiay)", self._pixmaps),
            "OverlayIconName": GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", ""),
            "ToolTip": self._tooltip(),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
        }
        return values.get(prop)

    def _item_call(self, _bus, _sender, _path, _iface, method, _params, invocation):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self._toggle)
        invocation.return_value(None)  # ContextMenu and Scroll: the panel shows the menu itself

    def _toggle(self):
        self.on_toggle()
        self.window_changed()
        return False

    # ================================================================ the menu
    def _toggle_label(self):
        return self.words["hide"] if self.is_shown() else self.words["show"]

    def _items(self):
        return {
            TOGGLE: {"label": GLib.Variant("s", self._toggle_label())},
            STATUS: {"label": GLib.Variant("s", self.status_text), "enabled": GLib.Variant("b", False)},
            SEPARATOR: {"type": GLib.Variant("s", "separator")},
            QUIT: {"label": GLib.Variant("s", self.words["quit"])},
        }

    def _layout(self):
        items = self._items()
        children = [
            GLib.Variant("(ia{sv}av)", (item_id, items[item_id], [])) for item_id in (TOGGLE, STATUS, SEPARATOR, QUIT)
        ]
        root = (0, {"children-display": GLib.Variant("s", "submenu")}, children)
        return GLib.Variant("(u(ia{sv}av))", (self._revision, root))

    def _menu_get(self, _bus, _sender, _path, _iface, prop):
        values = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", [self.icon_dir]),
        }
        return values.get(prop)

    def _menu_call(self, _bus, _sender, _path, _iface, method, params, invocation):
        try:
            if method == "GetLayout":
                invocation.return_value(self._layout())
            elif method == "GetGroupProperties":
                ids, _names = params.unpack()
                items = self._items()
                wanted = ids or list(items)
                rows = [(i, items[i]) for i in wanted if i in items]
                invocation.return_value(GLib.Variant("(a(ia{sv}))", (rows,)))
            elif method == "GetProperty":
                item_id, prop = params.unpack()
                value = self._items().get(item_id, {}).get(prop, GLib.Variant("s", ""))
                invocation.return_value(GLib.Variant("(v)", (value,)))
            elif method == "Event":
                item_id, event, _data, _time = params.unpack()
                if event == "clicked":
                    GLib.idle_add(self._clicked, item_id)
                invocation.return_value(None)
            elif method == "EventGroup":
                (events,) = params.unpack()
                for item_id, event, _data, _time in events:
                    if event == "clicked":
                        GLib.idle_add(self._clicked, item_id)
                invocation.return_value(GLib.Variant("(ai)", ([],)))
            elif method == "AboutToShow":
                invocation.return_value(GLib.Variant("(b)", (False,)))
            elif method == "AboutToShowGroup":
                invocation.return_value(GLib.Variant("(aiai)", ([], [])))
            else:
                invocation.return_value(None)
        except Exception:
            logger.exception("panel menu call %s failed", method)
            invocation.return_value(None)

    def _clicked(self, item_id):
        if item_id == TOGGLE:
            self._toggle()
        elif item_id == QUIT:
            self.on_quit()
        return False
