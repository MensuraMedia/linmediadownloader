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
from modules.utils import file_utils  # noqa: E402
from ui import messages  # noqa: E402
from ui.pages.download import fmt_size  # noqa: E402
from ui.player import Player  # noqa: E402
from ui.widgets.player_bar import PlayerBar, clock_words  # noqa: E402

logger = logging.getLogger("lmd.ui.library")

C = tokens.COLOR
SIDEBAR_W = 320
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

# the Tidy-names groups: (heading or None, [(label, operation), …])
TIDY_GROUPS = (
    (
        messages.LIB_TIDY_CLEAN_UP,
        (
            (messages.LIB_OP_CLEAN, "clean"),
            (messages.LIB_OP_REMOVE_FILLER, "remove_filler"),
            (messages.LIB_OP_REMOVE_SPECIAL, "remove_special"),
            (messages.LIB_OP_REPLACE_SPACES, "replace_spaces"),
        ),
    ),
    (
        messages.LIB_TIDY_SHORTEN,
        (
            (messages.LIB_OP_TRUNCATE, "truncate"),
            (messages.LIB_OP_ABBREVIATE, "abbreviate_dupes"),
            (messages.LIB_OP_STANDARD, "standard_font"),
            (messages.LIB_OP_NUMBER, "number_prefix"),
        ),
    ),
    (
        messages.LIB_TIDY_CASE,
        (
            (messages.LIB_CASE_LOWER, "lower_case"),
            (messages.LIB_CASE_UPPER, "upper_case"),
            (messages.LIB_CASE_TITLE, "title_case"),
            (messages.LIB_CASE_CAMEL, "camel_case"),
        ),
    ),
    (
        None,
        (
            (messages.LIB_OP_REPLACEMENTS, "apply_replacements"),
            (messages.LIB_OP_DELETE_LONG, "delete_long"),
        ),
    ),
)


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


def badge_label(order, saved_hex, size=26):
    label = Gtk.Label(label=f"{order % 1000:03d}")
    kit.css(label, "lt-badge", f"lmd-badge-{badge_class(saved_hex)}")
    label.set_size_request(size, size)
    label.set_halign(Gtk.Align.CENTER)
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
        self.rename_button = kit.icon_button("pencil-simple", "", on_click=lambda: self._start_rename())
        self.title_box = Gtk.Box(spacing=8)
        self.title_box.append(self.title_label)
        self.title_box.append(self.rename_button)
        self.header.append(self.header_badge)
        self.header.append(self.title_box)
        filler = Gtk.Box()
        filler.set_hexpand(True)
        self.header.append(filler)
        self.pills = Gtk.Box(spacing=8)
        self.header.append(self.pills)
        self.rename_entry = kit.entry(accessible_name=messages.LIB_RENAME_APPLY, width_chars=20)
        self.rename_entry.set_visible(False)
        self.rename_entry.connect("activate", lambda *_a: self._apply_rename())
        self.rename_error = kit.text("", "lt-error-text")
        self.rename_error.set_visible(False)
        header_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header_block.append(self.header)
        header_block.append(self.rename_entry)
        header_block.append(self.rename_error)
        pane.append(header_block)

        toolbar = Gtk.Box(spacing=8)
        self.tidy_button = self._build_tidy_button()
        toolbar.append(self.tidy_button)
        self.undo_button = kit.icon_button("arrow-counter-clockwise", messages.LIB_UNDO, on_click=self._undo)
        self.redo_button = kit.icon_button("arrow-clockwise", messages.LIB_REDO, on_click=self._redo)
        toolbar.append(self.undo_button)
        toolbar.append(self.redo_button)
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
        toolbar = Gtk.Box(spacing=8)
        self.all_tidy_button = self._build_tidy_button(all_files=True)
        toolbar.append(self.all_tidy_button)
        pane.append(toolbar)
        self.all_store = Gio.ListStore.new(FileItem)
        self.all_view = self._build_table(self.all_store, with_folder=True)
        pane.append(self.all_view)
        return pane

    def _build_table(self, store, with_folder):
        selection = Gtk.SingleSelection(model=store)
        selection.set_autoselect(False)
        view = Gtk.ColumnView(model=selection)
        view.set_hexpand(True)
        view.set_vexpand(True)
        view.set_enable_rubberband(False)
        view.connect("activate", self._on_row_activated)
        self._attach_table_keys(view)
        view.append_column(
            _column(messages.LIB_COL_NAME, "name", _text_cell("name", expand=True), text=True, expand=True)
        )
        view.append_column(
            _column(messages.LIB_COL_LENGTH, "seconds", _text_cell("length_text", heading=True))
        )
        view.append_column(_column(messages.LIB_COL_SIZE, "size", _text_cell("size_text", heading=True)))
        if with_folder:
            view.append_column(_column(messages.LIB_COL_FOLDER, "folder", _text_cell("folder")))
        else:
            menu = _column("", "path", _menu_cell(self), sortable=False)
            menu.set_fixed_width(56)
            view.append_column(menu)
        # a ColumnView only scrolls inside a ScrolledWindow; bare, it reports the
        # height of every row and grows the window past 800 px
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(view)
        scroll.set_vexpand(True)
        frame = kit.css(Gtk.Box(), "lt-card", "lmd-list")
        frame.set_vexpand(True)
        frame.append(scroll)
        return frame

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
        self.header_badge.append(badge_label(item.get("order", 0), item.get("color"), size=36))
        self.title_label.set_text(item["name"])
        self.title_box.set_visible(True)  # a rename left unfinished on another playlist
        self.rename_button.set_tooltip_text(messages.LIB_RENAME.format(name=item["name"]))
        kit.name(self.rename_button, messages.LIB_RENAME.format(name=item["name"]))
        self.rename_entry.set_visible(False)
        self.rename_error.set_visible(False)
        self._paint_pills()
        self._paint_table()
        self._paint_stack_buttons()

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

    def _paint_stack_buttons(self):
        state = library.stack_state()
        self.undo_button.set_sensitive(state.get("can_undo", False))
        self.redo_button.set_sensitive(state.get("can_redo", False))
        if not state.get("can_undo"):
            self.undo_button.set_tooltip_text(messages.LIB_UNDO_NONE)
        else:
            self.undo_button.set_tooltip_text(messages.LIB_UNDO)
        if not state.get("can_redo"):
            self.redo_button.set_tooltip_text(messages.LIB_REDO_NONE)
        else:
            self.redo_button.set_tooltip_text(messages.LIB_REDO)

    def _undo(self):
        library.undo_last()
        self._after_operation()

    def _redo(self):
        library.redo_last()
        self._after_operation()

    def _open_folder(self):
        if self.selected:
            file_utils.open_folder(self.selected["path"])

    def _after_operation(self):
        self.refresh_sidebar()
        self._paint_playlist()

    # -- rename
    def _start_rename(self):
        if self.selected is None:
            return
        self.rename_entry.set_text(self.selected["name"])
        self.rename_entry.set_visible(True)
        self.rename_error.set_visible(False)
        self.title_box.set_visible(False)
        self.rename_entry.grab_focus()

    def _apply_rename(self):
        if self.selected is None:
            return
        name = self.rename_entry.get_text().strip()
        if not name:
            return
        result = library.rename_playlist(self.selected["path"], name)
        if result.get("status") == "success":
            self.selected = dict(
                self.selected,
                name=result.get("name") or name,
                path=result.get("path") or self.selected["path"],
            )
            self.rename_entry.set_visible(False)
            self.title_box.set_visible(True)
            self.refresh_sidebar()
            self._paint_playlist()
        else:
            self.rename_error.set_text(result.get("message", ""))
            self.rename_error.set_visible(True)

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
        if self.view_mode == "all":
            return self.all_store, ""
        return self.playlist_store, (self.selected or {}).get("name", "")

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

    # ================================================================ tidy names
    def _build_tidy_button(self, all_files=False):
        button = Gtk.MenuButton()
        kit.css(button, "lt-btn")
        button.set_child(
            kit.hbox(
                kit.icon("text-aa", 18),
                Gtk.Label(label=messages.LIB_TIDY_NAMES),
                kit.icon("caret-down", 14),
                spacing=8,
            )
        )
        popover = Gtk.Popover()
        popover.set_child(TidyNames(self, all_files))
        button.set_popover(popover)
        return button

    def apply_tidy(self, all_files, operation):
        """The popover's primary button: the only place a tidy operation runs"""
        try:
            if all_files:
                result = library.global_operation(operation)
            else:
                result = library.apply_operation(self.selected["path"], operation)
        except Exception:
            logger.exception("applying %s failed", operation)
            return
        logger.info("tidy %s: %s", operation, {k: v for k, v in result.items() if k != "moves"})
        self._refresh_after_file_change()
        self._paint_stack_buttons()

    def tidy_target(self, all_files):
        """The folder a preview runs over (None = every app folder)"""
        if all_files:
            return None
        return self.selected["path"] if self.selected else None

    def tidy_file_count(self, all_files):
        if all_files:
            try:
                return len(library.list_all_media())
            except Exception:
                return 0
        return (self.selected or {}).get("file_count") or 0


class TidyNames(Gtk.Box):
    """The Tidy-names popover content: groups, a live preview, one apply button.

    Each popover owns its own state, so the playlist and the All-files toolbars
    can both show one without sharing buttons."""

    def __init__(self, page, all_files):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.page = page
        self.all_files = all_files
        self.operation = None
        self.planned = []
        self.set_size_request(360, -1)
        for edge in ("top", "bottom", "start", "end"):
            getattr(self, f"set_margin_{edge}")(16)
        head = Gtk.Box(spacing=8)
        title = kit.text(messages.LIB_TIDY_NAMES, "lt-heading")
        title.set_hexpand(True)
        head.append(title)
        # refreshed on every preview: the popover is built before a playlist is selected
        self.count_note = kit.text(
            messages.LIB_TIDY_ALL.format(n=page.tidy_file_count(all_files)), "lt-caption"
        )
        head.append(self.count_note)
        self.append(head)
        self.op_buttons = {}
        for heading, operations in TIDY_GROUPS:
            if heading:
                self.append(kit.text(heading, "lt-caption"))
            grid = Gtk.Grid(column_spacing=8, row_spacing=8)
            for index, (label, operation) in enumerate(operations):
                op_button = kit.button(label, on_click=lambda *_, op=operation: self.select(op))
                op_button.set_hexpand(True)
                grid.attach(op_button, index % 2, index // 2, 1, 1)
                self.op_buttons[operation] = op_button
            self.append(grid)
        self.note = kit.text("", "lt-caption")
        self.append(self.note)
        self.preview_words = kit.text("", "lt-caption")
        self.preview_old = kit.text("", "lt-mono")
        self.preview_old.set_ellipsize(3)
        self.preview_old.set_xalign(0.0)
        self.preview_new = kit.text("", "lt-mono")
        self.preview_new.set_ellipsize(3)
        self.preview_new.set_xalign(0.0)
        frame = kit.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4), "lt-card")
        frame.append(self.preview_words)
        frame.append(self.preview_old)
        self.preview_becomes = kit.text("", "lt-caption")  # the word, muted; the new name in mono
        new_row = Gtk.Box(spacing=8)
        new_row.append(self.preview_becomes)
        new_row.append(self.preview_new)
        frame.append(new_row)
        self.append(frame)
        buttons = Gtk.Box(spacing=8)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(kit.button(messages.LIB_CLOSE, on_click=lambda: self.popdown()))
        self.apply_button = kit.button("", kind="primary", on_click=self.apply)
        self.apply_button.set_sensitive(False)
        self.apply_button.set_tooltip_text(messages.LIB_PREVIEW_NONE)
        buttons.append(self.apply_button)
        self.append(buttons)

    def popdown(self):
        popover = self.get_ancestor(Gtk.Popover)
        if popover is not None:
            popover.popdown()

    def select(self, operation):
        self.operation = operation
        for other, button in self.op_buttons.items():
            (kit.css if other == operation else kit.uncss)(button, "lmd-selected")
        is_delete = operation == "delete_long"
        self.note.set_text(messages.LIB_OP_DELETE_LONG_NOTE if is_delete else "")
        try:
            if self.all_files:
                planned = library.preview_global(operation)
            else:
                planned = library.preview_operation(self.page.tidy_target(False), operation)
        except Exception:
            logger.exception("previewing %s failed", operation)
            planned = []
        self.planned = planned
        changed = len(planned)
        total = self.page.tidy_file_count(self.all_files)
        self.count_note.set_text(messages.LIB_TIDY_ALL.format(n=total))
        if changed:
            self.preview_words.set_text(messages.LIB_PREVIEW.format(k=changed, n=total))
            old, new = planned[0]
            self.preview_old.set_text(old)
            self.preview_becomes.set_text(messages.LIB_PREVIEW_BECOMES)
            self.preview_new.set_text(new)
        else:
            self.preview_words.set_text(messages.LIB_PREVIEW_NONE)
            self.preview_old.set_text("")
            self.preview_becomes.set_text("")
            self.preview_new.set_text("")
        label = (
            messages.LIB_MOVE_K.format(k=changed) if is_delete else messages.LIB_RENAME_K.format(k=changed)
        )
        self.apply_button.set_label(label)
        self.apply_button.set_sensitive(changed > 0)
        self.apply_button.set_tooltip_text("" if changed else messages.LIB_PREVIEW_NONE)

    def apply(self, *_args):
        if not self.operation or not self.planned:
            return
        self.popdown()
        self.page.apply_tidy(self.all_files, self.operation)
