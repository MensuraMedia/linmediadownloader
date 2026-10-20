# ui/pages/library.py
"""The Library page: playlists and every downloaded file on the left, the
selected playlist's files (or all files) on the right, the Tidy-names popover
with a live preview, undo/redo, the trash confirm, and the player bar.

Left column 320 px like the mockup; the file table is a sortable
Gtk.ColumnView. Everything destructive goes through the kit's confirm; tidy
operations only apply from the popover's primary button, after the preview.
"""

import logging
import os
from collections import Counter

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, Gio, GObject, Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from modules import playlists as library
from modules.config import user_settings  # noqa: E402
from modules.utils import file_utils  # noqa: E402
from ui import messages  # noqa: E402
from ui.pages.download import fmt_size  # noqa: E402
from ui.player import Player  # noqa: E402
from ui.widgets.player_bar import PlayerBar, clock_words  # noqa: E402

logger = logging.getLogger("lmd.ui.library")

C = tokens.COLOR
SIDEBAR_W = 320
SEQ_CHARS = 5  # a playlist number has up to five digits (1..99999)
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}

# the six token colours a playlist badge may wear (ui/style.py has the classes)
TOKEN_COLOURS = {
    C["accent"]: "accent",
    C["ok"]: "ok",
    C["busy"]: "busy",
    C["attention"]: "attention",
    C["error"]: "error",
    C["text_muted"]: "muted",
}
COLOUR_NAMES = {
    "accent": messages.LIB_COLOUR_ACCENT,
    "ok": messages.LIB_COLOUR_OK,
    "busy": messages.LIB_COLOUR_BUSY,
    "attention": messages.LIB_COLOUR_ATTENTION,
    "error": messages.LIB_COLOUR_ERROR,
    "muted": messages.LIB_COLOUR_MUTED,
}

def badge_class(saved_hex):
    """The lmd-badge-* class for a saved colour; unknown colours become accent"""
    return TOKEN_COLOURS.get((saved_hex or "").lower(), "accent")


# badge class name -> the token key behind it (for set_playlist_color)
COLOUR_KEYS = {
    "accent": "accent",
    "ok": "ok",
    "busy": "busy",
    "attention": "attention",
    "error": "error",
    "muted": "text_muted",
}


def badge_label(order, saved_hex, large=False):
    """A playlist's sequence number: the plain number in its colour, no badge (user,
    2026-10-19). Counts 1..99999, then wraps like the 1.x 000..999 badges did."""
    label = Gtk.Label(label=str(order % library.SEQ_WRAP))
    kit.css(label, "lmd-seq", "lmd-seq-large" if large else None, f"lmd-seq-{badge_class(saved_hex)}")
    if not large:  # in the sidebar the names line up whatever the number's length
        label.set_width_chars(SEQ_CHARS)
        label.set_xalign(1.0)
    label.set_valign(Gtk.Align.CENTER)
    return label


def _clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


class FileItem(GObject.Object):
    """One row of the file table"""

    name = GObject.Property(type=str, default="")
    length_text = GObject.Property(type=str, default="")
    seconds = GObject.Property(type=float, default=0.0)
    size = GObject.Property(type=float, default=0.0)
    size_text = GObject.Property(type=str, default="")
    folder = GObject.Property(type=str, default="")
    path = GObject.Property(type=str, default="")
    checked = GObject.Property(type=bool, default=False)  # ticked for "Delete selected"


def _text_cell(prop, heading=False, expand=False):
    """A cell factory that shows one FileItem string property"""
    factory = Gtk.SignalListItemFactory()

    def setup(_factory, item):
        label = Gtk.Label(xalign=1.0 if heading else 0.0)
        if expand:
            label.set_hexpand(True)
            label.set_ellipsize(3)  # end: long names shorten, the rest stays put
        item.set_child(label)

    def bind(_factory, item):
        item.get_child().set_text(getattr(item.get_item(), prop) or "")

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    return factory


class RowMenuButton(Gtk.MenuButton):
    """The 'More' menu of one file row (its popover is bound to the row's item)"""

    def __init__(self, page):
        super().__init__()
        kit.css(self, "lt-icon-btn")
        self.set_child(kit.icon("dots-three", 16))
        self._page = page
        self._item = None
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.END)

    def bind(self, item):
        self._item = item
        title = os.path.basename(item.path)
        spoken = messages.LIB_FILE_MORE.format(name=title)
        kit.name(self, spoken)
        self.set_tooltip_text(spoken)
        popover = Gtk.Popover()
        popover.set_child(self._page.build_file_menu(item))
        self.set_popover(popover)


def _menu_cell(page):
    factory = Gtk.SignalListItemFactory()

    def setup(_factory, item):
        item.set_child(RowMenuButton(page))

    def bind(_factory, item):
        item.get_child().bind(item.get_item())

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    return factory


def _check_cell(table):
    """A tick box per row, bound both ways to the row's FileItem.checked"""
    factory = Gtk.SignalListItemFactory()

    def setup(_factory, item):
        check = kit.css(Gtk.CheckButton(), "lmd-check")
        check.set_halign(Gtk.Align.CENTER)
        check._lmd_binding = None
        check.connect("toggled", lambda *_a: table.paint_checked())
        item.set_child(check)

    def bind(_factory, item):
        check, row = item.get_child(), item.get_item()
        flags = GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL
        check._lmd_binding = row.bind_property("checked", check, "active", flags)
        kit.name(check, messages.LIB_CHECK_FILE.format(name=row.name))

    def unbind(_factory, item):
        check = item.get_child()
        if check._lmd_binding is not None:
            check._lmd_binding.unbind()
            check._lmd_binding = None

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    factory.connect("unbind", unbind)
    return factory


def _column(title, prop, factory, text=False, sortable=True, expand=False):
    column = Gtk.ColumnViewColumn(title=title)
    column.set_factory(factory)
    if expand:
        column.set_expand(True)
    if sortable:
        if text:
            sorter = Gtk.StringSorter.new(Gtk.PropertyExpression.new(FileItem, None, prop))
        else:
            sorter = Gtk.NumericSorter.new(Gtk.PropertyExpression.new(FileItem, None, prop))
        column.set_sorter(sorter)
    return column


class FileTable(Gtk.Box):
    """A file table with its own search, filter and tick boxes (user, 2026-10-19).

    store (every file) -> FilterListModel (search + filter) -> SortListModel (the column
    headers) -> SingleSelection -> ColumnView. Ticked rows are deleted together: they
    move to their folder's trash, which the playlist's Trash pill empties for good."""

    def __init__(self, page, store, with_folder):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.page = page
        self.store = store
        self.with_folder = with_folder
        self.query = ""
        self.kind = "all"
        self._alike = set()
        self._bulk = False

        tools = Gtk.Box(spacing=8)
        self.search = kit.entry(
            placeholder=messages.LIB_SEARCH_FILES, accessible_name=messages.LIB_SEARCH_FILES, width_chars=10
        )
        self.search.set_hexpand(True)
        self.search.connect("changed", self._on_search)
        tools.append(self.search)
        options = [
            ("all", messages.LIB_FILTER_ALL),
            ("audio", messages.LIB_FILTER_AUDIO),
            ("video", messages.LIB_FILTER_VIDEO),
            ("alike", messages.LIB_FILTER_ALIKE),
        ]
        if not with_folder:  # lengths are known for a playlist's files only
            options.insert(3, ("long", messages.LIB_FILTER_LONG.format(n=self._long_minutes())))
        self.filter_choice = kit.select(options, "all", self._on_kind, messages.LIB_FILTER_NAME)
        tools.append(self.filter_choice)
        self.append(tools)

        picks = Gtk.Box(spacing=8)
        self.check_all = kit.css(Gtk.CheckButton(label=messages.LIB_SELECT_ALL), "lmd-check")
        self._check_all_handler = self.check_all.connect("toggled", self._on_check_all)
        picks.append(self.check_all)
        self.count_label = kit.text("", "lt-caption")
        self.count_label.set_hexpand(True)
        picks.append(self.count_label)
        self.delete_button = kit.button(
            messages.LIB_DELETE_NONE, kind="danger", icon_name="trash", on_click=self._confirm_delete
        )
        picks.append(self.delete_button)
        self.append(picks)

        self.filter = Gtk.CustomFilter.new(self._match)
        self.filtered = Gtk.FilterListModel(model=store, filter=self.filter)
        self.view = Gtk.ColumnView()
        self.sorted = Gtk.SortListModel(model=self.filtered, sorter=self.view.get_sorter())
        selection = Gtk.SingleSelection(model=self.sorted)
        selection.set_autoselect(False)
        self.view.set_model(selection)
        self.view.set_hexpand(True)
        self.view.set_vexpand(True)
        self.view.set_enable_rubberband(False)
        self.view.connect("activate", page._on_row_activated)
        page._attach_table_keys(self.view)
        check = _column("", "checked", _check_cell(self), sortable=False)
        check.set_fixed_width(44)
        self.view.append_column(check)
        self.view.append_column(
            _column(messages.LIB_COL_NAME, "name", _text_cell("name", expand=True), text=True, expand=True)
        )
        if not with_folder:
            self.view.append_column(
                _column(messages.LIB_COL_LENGTH, "seconds", _text_cell("length_text", heading=True))
            )
        self.view.append_column(_column(messages.LIB_COL_SIZE, "size", _text_cell("size_text", heading=True)))
        if with_folder:
            self.view.append_column(_column(messages.LIB_COL_FOLDER, "folder", _text_cell("folder")))
        else:
            menu = _column("", "path", _menu_cell(page), sortable=False)
            menu.set_fixed_width(56)
            self.view.append_column(menu)
        # a ColumnView only scrolls inside a ScrolledWindow; bare, it reports the
        # height of every row and grows the window past 800 px
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.view)
        scroll.set_vexpand(True)
        frame = kit.css(Gtk.Box(), "lt-card", "lmd-list")
        frame.set_vexpand(True)
        frame.append(scroll)
        self.append(frame)
        self.empty_note = kit.text(messages.LIB_FILTER_NONE, "lt-muted")
        self.empty_note.set_visible(False)
        self.append(self.empty_note)
        self.set_vexpand(True)

    # the ColumnView's model, for the page's row and keyboard handlers
    def get_model(self):
        return self.view.get_model()

    def visible(self):
        """The rows as shown: searched, filtered and sorted"""
        return [self.sorted.get_item(i) for i in range(self.sorted.get_n_items())]

    @staticmethod
    def _long_minutes():
        try:
            return int(user_settings.get_settings().get("long_minutes") or 7)
        except Exception:
            return 7

    # -- search and filter
    def _match(self, item):
        if self.query and self.query not in item.name.lower() and self.query not in item.folder.lower():
            return False
        ext = os.path.splitext(item.name)[1].lower()
        if self.kind == "audio":
            return ext not in VIDEO_EXTS
        if self.kind == "video":
            return ext in VIDEO_EXTS
        if self.kind == "long":
            return item.seconds > self._long_minutes() * 60
        if self.kind == "alike":
            return item.size > 0 and item.size in self._alike
        return True

    def _on_search(self, entry):
        self.query = entry.get_text().strip().lower()
        self.refilter()

    def _on_kind(self, kind):
        self.kind = kind or "all"
        self.refilter()

    def refilter(self):
        """Call after the store is refilled or a search/filter changes"""
        sizes = Counter(self.store.get_item(i).size for i in range(self.store.get_n_items()))
        self._alike = {size for size, count in sizes.items() if count > 1}
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self.empty_note.set_visible(self.store.get_n_items() > 0 and self.sorted.get_n_items() == 0)
        self.paint_checked()

    # -- ticks and delete
    def checked(self):
        """Ticked rows that the search and filter still show"""
        return [item for item in self.visible() if item.checked]

    def paint_checked(self):
        if self._bulk:
            return
        ticked, shown = len(self.checked()), self.sorted.get_n_items()
        self.count_label.set_text(messages.LIB_CHECKED.format(k=ticked, n=shown) if ticked else "")
        self.delete_button.set_sensitive(ticked > 0)
        label = messages.LIB_DELETE_K.format(k=ticked) if ticked else messages.LIB_DELETE_NONE
        self.delete_button.get_child().get_last_child().set_text(label)
        self.delete_button.set_tooltip_text("" if ticked else messages.LIB_DELETE_HOW)
        self.check_all.handler_block(self._check_all_handler)
        self.check_all.set_active(shown > 0 and ticked == shown)
        self.check_all.set_inconsistent(0 < ticked < shown)
        self.check_all.handler_unblock(self._check_all_handler)

    def _on_check_all(self, button):
        on = button.get_active()
        self._bulk = True  # one count update, not one per row
        try:
            for item in self.visible():
                item.checked = on
        finally:
            self._bulk = False
        self.paint_checked()

    def _confirm_delete(self):
        items = self.checked()
        if not items:
            return
        names = [item.name for item in items]
        kit.confirm(
            self.page.window,
            messages.LIB_DELETE_TITLE.format(k=len(items)),
            messages.LIB_DELETE_BODY,
            messages.LIB_DELETE_GO.format(k=len(items)),
            destructive=True,
            cancel_label=messages.LIB_DELETE_KEEP,
            detail_mono="\n".join(names),
            on_answer=lambda yes: self.page.trash_files([item.path for item in items]) if yes else None,
        )


class LibraryPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.view_mode = "playlists"
        self.selected = None
        self.query = ""
        self.player = Player()
        self._build()
        self.refresh_sidebar()
        self._select_first()
        # never leave audio running behind a closed window
        window.connect("close-request", lambda *_a: (self.player.stop(), False)[1])

    # ================================================================ build
    def _build(self):
        content = Gtk.Box()
        content.set_hexpand(True)
        content.set_vexpand(True)
        content.append(self._build_sidebar())
        self.right = kit.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), "lt-pane")
        self.right.set_hexpand(True)
        self.right_stack = Gtk.Stack()
        self.right_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.right_stack.set_transition_duration(tokens.MOTION["state_ms"])
        self.playlist_pane = self._build_playlist_pane()
        self.right_stack.add_named(self.playlist_pane, "playlist")
        self.right_stack.add_named(self._build_all_files_pane(), "all")
        self.empty_state = kit.EmptyState(
            "music-notes",
            messages.LIB_EMPTY_TITLE,
            messages.LIB_EMPTY_BODY,
            (messages.ACT_GO_TO_DOWNLOAD, lambda: self.window.show_page("download")),
        )
        self.right_stack.add_named(self.empty_state, "empty")
        self.right.append(self.right_stack)
        content.append(self.right)
        self.append(content)
        self.bar = PlayerBar(self.player, self.window)
        self.append(self.bar)

    def _build_sidebar(self):
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        kit.css(side, "lt-pane", "lt-pane-divider")
        side.set_size_request(SIDEBAR_W, -1)
        self.view_seg = kit.Segmented(
            [("playlists", messages.LIB_PLAYLISTS), ("all", messages.LIB_ALL_FILES)],
            "playlists",
            self._on_view_changed,
            messages.LIB_VIEW_NAME,
        )
        self.view_seg.set_homogeneous(True)
        side.append(self.view_seg)
        self.search = kit.entry(accessible_name=messages.LIB_SEARCH_NAME, width_chars=18)
        self.search.set_hexpand(True)
        self.search.connect("changed", self._on_search_changed)
        side.append(self.search)
        self.sidebar_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.sidebar_rows.set_vexpand(True)
        side.append(kit.scrolled(self.sidebar_rows))
        return side

    def _build_playlist_pane(self):
        pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.header = Gtk.Box(spacing=12)
        self.header_badge = Gtk.Box()
        self.title_label = kit.text("", "lt-title")
        self.title_label.set_halign(Gtk.Align.START)
        # a long folder name shortens with "…" (full name on hover); unshortened it set the
        # whole window's minimum width (1241 px for one long playlist name)
        self.title_label.set_ellipsize(3)
        self.title_label.set_hexpand(True)
        self.title_box = Gtk.Box(spacing=8)
        self.title_box.append(self.title_label)
        self.header.append(self.header_badge)
        self.header.append(self.title_box)
        filler = Gtk.Box()
        filler.set_hexpand(True)
        self.header.append(filler)
        self.pills = Gtk.Box(spacing=8)
        self.header.append(self.pills)
        header_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header_block.append(self.header)
        pane.append(header_block)

        toolbar = Gtk.Box(spacing=8)
        # renaming lives on the File Control page (user, 2026-10-19); this opens it here
        self.rename_files_button = kit.button(
            messages.LIB_RENAME_FILES,
            on_click=lambda: self.selected and self.window.open_in_file_control(self.selected["path"]),
            icon_name="files",
        )
        toolbar.append(self.rename_files_button)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)
        self.open_button = kit.button(
            messages.OPEN_FOLDER, on_click=lambda: self._open_folder(), icon_name="folder-open"
        )
        toolbar.append(self.open_button)
        pane.append(toolbar)

        self.playlist_store = Gio.ListStore.new(FileItem)
        self.playlist_view = self._build_table(self.playlist_store, with_folder=False)
        pane.append(self.playlist_view)
        return pane

    def _build_all_files_pane(self):
        pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        head = Gtk.Box(spacing=8)
        title = kit.text(messages.LIB_ALL_FILES, "lt-title")
        title.set_hexpand(True)
        head.append(title)
        self.stats_pills = Gtk.Box(spacing=8)
        head.append(self.stats_pills)
        pane.append(head)
        self.all_store = Gio.ListStore.new(FileItem)
        self.all_view = self._build_table(self.all_store, with_folder=True)
        pane.append(self.all_view)
        return pane

    def _build_table(self, store, with_folder):
        return FileTable(self, store, with_folder)

    def _attach_table_keys(self, view):
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_table_key)
        view.add_controller(keys)

    def _on_table_key(self, _ctrl, keyval, _keycode, state):
        if state & Gtk.accelerator_get_default_mod_mask():
            return False
        if keyval == Gdk.KEY_space:
            self.player.toggle()
            return True
        if keyval == Gdk.KEY_Right:
            self.player.seek_relative(5)
            return True
        if keyval == Gdk.KEY_Left:
            self.player.seek_relative(-2)
            return True
        if keyval in (Gdk.KEY_Up, Gdk.KEY_Down):
            step = 0.05 if keyval == Gdk.KEY_Up else -0.05
            self.player.set_volume(self.player.volume + step)
            self.bar.volume.set_value(self.player.volume)
            return True
        if keyval == Gdk.KEY_Delete:
            self._trash_selected_file()
            return True
        return False

    # ================================================================ sidebar
    def refresh_sidebar(self):
        _clear_box(self.sidebar_rows)
        try:
            items = library.list_playlists()
        except Exception:
            logger.exception("listing playlists failed")
            items = []
        query = self.query.strip().lower()
        if query:
            items = [i for i in items if query in (i["name"] or "").lower()]
        total = len(library.list_all_media()) if not query else None
        if total is not None:
            self.search.set_placeholder_text(messages.LIB_SEARCH_PLACEHOLDER.format(n=total))
        for item in items:
            self.sidebar_rows.append(self._playlist_row(item))
        if not items:
            self.sidebar_rows.append(
                kit.text(messages.LIB_EMPTY_TITLE if not query else messages.LIB_PREVIEW_NONE, "lt-muted")
            )

    def _playlist_row(self, item):
        row = kit.css(Gtk.Button(), "lt-list-btn")
        if self.selected and self.selected["path"] == item["path"]:
            kit.css(row, "lmd-selected")
        box = Gtk.Box(spacing=10)
        box.append(badge_label(item.get("order", 0), item.get("color")))
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        words.set_hexpand(True)
        name = kit.text(item["name"], "lt-strong")
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(3)
        count = (
            messages.LIB_FILE
            if item.get("file_count") == 1
            else messages.LIB_FILES.format(n=item.get("file_count") or 0)
        )
        words.append(name)
        words.append(kit.text(f"{count} · {fmt_size(item.get('total_size'))}", "lt-caption"))
        box.append(words)
        more = Gtk.MenuButton()
        kit.css(more, "lt-icon-btn")
        more.set_child(kit.icon("dots-three", 16))
        more.set_valign(Gtk.Align.CENTER)
        spoken = messages.LIB_MORE_FOR.format(name=item["name"])
        kit.name(more, spoken)
        more.set_tooltip_text(spoken)
        popover = Gtk.Popover()
        popover.set_child(self._playlist_menu(item))
        more.set_popover(popover)
        box.append(more)
        row.set_child(box)
        row.connect("clicked", lambda *_a, i=item: self.select(i))
        gesture = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture.connect(
            "pressed",
            lambda *_a, i=item, p=popover: (p.popup(),),
        )
        row.add_controller(gesture)
        return row

    def _playlist_menu(self, item):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(12)
        box.append(kit.text(messages.LIB_BADGE_COLOUR, "lt-caption"))
        swatches = Gtk.Box(spacing=8)
        for name, words in COLOUR_NAMES.items():
            swatch = Gtk.Button()
            kit.css(swatch, "lmd-swatch", f"lmd-badge-{name}")
            kit.name(swatch, words)
            swatch.set_tooltip_text(words)
            swatch.connect(
                "clicked",
                lambda *_a, i=item, n=name: self._set_badge_colour(i, n),
            )
            swatches.append(swatch)
        box.append(swatches)
        return box

    def _set_badge_colour(self, item, colour_name):
        hex_colour = C[COLOUR_KEYS[colour_name]]
        try:
            library.set_playlist_color(item["path"], hex_colour)
        except Exception:
            logger.exception("setting the badge colour failed")
        item["color"] = hex_colour
        self.refresh_sidebar()
        self._paint_playlist()

    def _on_view_changed(self, value):
        self.view_mode = value
        self._apply_view()

    def _on_search_changed(self, entry):
        self.query = entry.get_text()
        if self.view_mode == "playlists":
            self.refresh_sidebar()
            if not self.query and self.sidebar_rows.get_first_child() is None:
                self._select_first()
        else:
            self._paint_all_files()

    def _apply_view(self):
        self.right_stack.set_visible_child_name("all" if self.view_mode == "all" else "playlist")
        if self.view_mode == "all":
            self._paint_all_files()

    def _select_first(self):
        try:
            items = library.list_playlists()
        except Exception:
            items = []
        if items:
            self.select(items[0])
        else:
            self.selected = None
            self.right_stack.set_visible_child_name("empty")

    def show_file(self, path, play=True):
        """All files, narrowed to this one file by the search, and (by default) playing it"""
        self.view_mode = "all"
        self.view_seg.set_value("all")
        self.search.set_text(os.path.basename(path))  # the search handler repaints the list
        self._apply_view()
        if not play:
            return
        store, playlist_name = self._context()
        entries, index = self._entries_for(store, playlist_name, focus=path)
        if entries and any(entry[0] == path for entry in entries):
            self.player.play_list(entries, index)

    def select_by_path(self, path):
        """Show this folder (used by 'Play in Library' after a download); an empty
        path just keeps whatever is selected"""
        if not path:
            return
        try:
            items = library.list_playlists()
        except Exception:
            items = []
        for item in items:
            if item["path"] == path:
                self.view_mode = "playlists"
                self.view_seg.set_value("playlists")
                self.select(item)
                return
        self._select_first()

    def select(self, item):
        self.selected = item
        self.view_mode = "playlists"
        self.right_stack.set_visible_child_name("playlist")
        self.refresh_sidebar()
        self._paint_playlist()

    # ================================================================ playlist pane
    def _paint_playlist(self):
        item = self.selected
        if item is None:
            self.right_stack.set_visible_child_name("empty")
            return
        _clear_box(self.header_badge)
        self.header_badge.append(badge_label(item.get("order", 0), item.get("color"), large=True))
        self.title_label.set_text(item["name"])
        self.title_label.set_tooltip_text(item["name"])
        self._paint_pills()
        self._paint_table()

    def _paint_pills(self):
        _clear_box(self.pills)
        item = self.selected
        files = library.list_playlist_files(item["path"]) or []
        same_size = sum(
            count for count in Counter(f["size"] for f in files if f.get("size")).values() if count > 1
        )
        if same_size:
            pill = kit.pill(messages.LIB_LOOK_ALIKE.format(n=same_size), "attention")
            pill.set_valign(Gtk.Align.CENTER)
            self.pills.append(pill)
        trash = library.trash_count(item["path"])
        trash_pill = kit.button(
            messages.LIB_TRASH.format(n=trash) if trash else messages.LIB_TRASH_EMPTY,
            on_click=self._confirm_empty_trash,
            small=True,
        )
        kit.css(trash_pill, "lt-pill")  # a clickable pill, as in the mockup
        trash_pill.set_valign(Gtk.Align.CENTER)
        if not trash:
            trash_pill.set_sensitive(False)
            trash_pill.set_tooltip_text(messages.LIB_TRASH_EMPTY)
        self.pills.append(trash_pill)

    def _paint_table(self):
        item = self.selected
        files = library.list_playlist_files(item["path"]) if item else None
        self.playlist_store.remove_all()
        if not files:
            self.playlist_view.refilter()
            return
        # Name A to Z by default, as the mockup shows; the column headers re-sort
        for found in sorted(files, key=lambda f: f["filename"].lower()):
            entry = FileItem()
            name = found["filename"]
            entry.set_properties(
                name=name,
                seconds=found.get("duration") or 0.0,
                length_text=clock_words(found.get("duration")),
                size=found.get("size") or 0.0,
                size_text=fmt_size(found.get("size")),
                path=os.path.join(item["path"], name),
            )
            self.playlist_store.append(entry)
        self.playlist_view.refilter()

    def _open_folder(self):
        if self.selected:
            file_utils.open_folder(self.selected["path"])

    def files_changed(self, renamed=None):
        """File Control renamed something: follow a renamed playlist, then repaint"""
        if self.selected is not None:
            path = self.selected["path"]
            if renamed and path == renamed[0]:
                path = renamed[1]
            try:
                items = library.list_playlists()
            except Exception:
                items = []
            self.selected = next((p for p in items if p["path"] == path), None)
        self.refresh_sidebar()
        if self.view_mode == "all":
            self._paint_all_files()
        elif self.selected is None:
            self._select_first()
        else:
            self._paint_playlist()

    # -- trash
    def _confirm_empty_trash(self):
        item = self.selected
        if item is None:
            return
        trash = os.path.join(item["path"], ".trash")
        names = sorted(os.listdir(trash)) if os.path.isdir(trash) else []
        if not names:
            return
        kit.confirm(
            self.window,
            messages.LIB_EMPTY_TRASH_TITLE.format(name=item["name"]),
            messages.LIB_EMPTY_TRASH_BODY.format(n=len(names)),
            messages.LIB_EMPTY_TRASH_GO.format(n=len(names)),
            destructive=True,
            cancel_label=messages.LIB_EMPTY_TRASH_KEEP,
            detail_mono="\n".join(names),
            on_answer=lambda yes: self._empty_trash() if yes else None,
        )

    def _empty_trash(self):
        if self.selected is None:
            return
        try:
            library.empty_trash(self.selected["path"])
        except Exception:
            logger.exception("emptying the trash failed")
        self._paint_playlist()

    # -- the row menu
    def build_file_menu(self, item):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(12)
        path = item.path
        box.append(kit.button(messages.LIB_PLAY, on_click=lambda *_: self._play_path(path), small=True))
        box.append(
            kit.button(
                messages.LIB_SHOW_IN_FOLDER,
                on_click=lambda *_: file_utils.open_folder(os.path.dirname(path)),
                small=True,
            )
        )
        box.append(
            kit.button(
                messages.LIB_ADD_TO_FOLDER,
                on_click=lambda *_: self._add_to_folder_dialog(path),
                small=True,
            )
        )
        trash_button = kit.button(
            messages.LIB_MOVE_TO_TRASH, on_click=lambda *_: self._trash_file(path), small=True
        )
        trash_button.set_tooltip_text(messages.LIB_MOVE_TO_TRASH_NOTE)
        box.append(trash_button)
        return box

    def _play_path(self, path):
        store, playlist_name = self._context()
        entries, index = self._entries_for(store, playlist_name, focus=path)
        self.player.play_list(entries, index)

    def _context(self):
        """The rows to play through, in the order shown (searched, filtered, sorted)"""
        if self.view_mode == "all":
            return self.all_view.sorted, ""
        return self.playlist_view.sorted, (self.selected or {}).get("name", "")

    def _entries_for(self, store, playlist_name, focus=None):
        entries = []
        index = 0
        for i in range(store.get_n_items()):
            item = store.get_item(i)
            entries.append((item.path, os.path.splitext(item.name)[0], playlist_name))
            if focus is not None and item.path == focus:
                index = i
        return entries, index

    def _on_row_activated(self, view, position):
        item = view.get_model().get_item(position)
        if item is None:
            return
        store, playlist_name = self._context()
        entries, index = self._entries_for(store, playlist_name, focus=item.path)
        self.player.play_list(entries, index)

    def _selected_file(self):
        view = self.playlist_view if self.view_mode != "all" else self.all_view
        item = view.get_model().get_selected_item()
        return item.path if item is not None else None

    def _trash_selected_file(self):
        path = self._selected_file()
        if path:
            self._trash_file(path)

    def _trash_file(self, path):
        self.player.stop()
        try:
            result = library.delete_media_file(path)
        except Exception:
            logger.exception("moving a file to the trash failed")
            return
        if result.get("status") != "success":
            logger.warning("move to trash failed: %s", result.get("message"))
        self._refresh_after_file_change()

    def trash_files(self, paths):
        """Move the ticked files to their folders' trash (recoverable until it is emptied)"""
        self.player.stop()
        failed = 0
        for path in paths:
            try:
                result = library.delete_media_file(path)
            except Exception:
                logger.exception("moving %s to the trash failed", path)
                failed += 1
                continue
            if result.get("status") != "success":
                logger.warning("move to trash failed: %s", result.get("message"))
                failed += 1
        logger.info("moved %d of %d ticked files to the trash", len(paths) - failed, len(paths))
        self._refresh_after_file_change()

    def _refresh_after_file_change(self):
        self.refresh_sidebar()
        if self.view_mode == "all":
            self._paint_all_files()
        else:
            self._paint_playlist()

    def _add_to_folder_dialog(self, path):
        dialog = Gtk.Window(transient_for=self.window, modal=True)
        kit.css(dialog, "lt-root", "lt-dialog")
        dialog.set_title(messages.LIB_ADD_TO_FOLDER_TITLE.format(name=os.path.basename(path)))
        area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for edge in ("top", "bottom", "start", "end"):
            getattr(area, f"set_margin_{edge}")(20)
        dialog.set_child(area)
        area.append(
            kit.text(
                messages.LIB_ADD_TO_FOLDER_TITLE.format(name=os.path.basename(path)), "lt-heading", wrap=True
            )
        )
        area.append(kit.text(messages.LIB_ADD_TO_FOLDER_BODY, "lt-muted", wrap=True))
        name_entry = kit.entry(accessible_name=messages.LIB_ADD_TO_FOLDER, width_chars=24)
        area.append(name_entry)
        error = kit.text("", "lt-error-text")
        area.append(error)
        buttons = Gtk.Box(spacing=8)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(kit.button(messages.LIB_RENAME_CANCEL, on_click=lambda: dialog.destroy()))
        add = kit.button(
            messages.LIB_ADD, kind="primary", on_click=lambda: apply_folder(name_entry.get_text())
        )
        buttons.append(add)
        area.append(buttons)

        def apply_folder(name):
            if not name.strip():
                return
            result = library.add_to_folder(path, name.strip())
            if result.get("status") == "success":
                dialog.destroy()
                self.refresh_sidebar()
            else:
                error.set_text(result.get("message", ""))

        name_entry.connect("activate", lambda *_a: apply_folder(name_entry.get_text()))
        dialog.set_default_widget(add)
        dialog.present()

    # ================================================================ all files
    def _paint_all_files(self):
        try:
            stats = library.file_stats()
        except Exception:
            logger.exception("file stats failed")
            stats = {}
        _clear_box(self.stats_pills)
        total = stats.get("total") or 0
        self.stats_pills.append(kit.pill(messages.LIB_STATS_TOTAL.format(n=total)))
        if stats.get("duplicate_names"):
            self.stats_pills.append(
                kit.pill(messages.LIB_STATS_DUPES.format(n=stats["duplicate_names"]), "attention")
            )
        if stats.get("same_size"):
            self.stats_pills.append(kit.pill(messages.LIB_STATS_SIZES.format(n=stats["same_size"])))
        try:
            files = library.list_all_media()
        except Exception:
            logger.exception("listing all media failed")
            files = []
        query = self.query.strip().lower()
        if query:
            files = [f for f in files if query in f["name"].lower() or query in f["folder"].lower()]
        self.all_store.remove_all()
        for found in sorted(files, key=lambda f: (f["name"].lower(), f.get("folder", ""))):
            entry = FileItem()
            entry.set_properties(
                name=found["name"],
                size=found.get("size") or 0.0,
                size_text=fmt_size(found.get("size")),
                folder=found.get("folder", ""),
                path=found["path"],
            )
            self.all_store.append(entry)
        self.all_view.refilter()
