# ui/pages/file_control.py
"""The File Control page: every way the app renames files, in one place (user,
2026-10-19). It took the Tidy-names popover, undo/redo and the playlist rename from
the Library, and the filler words and character replacements from Settings.

Left column: what to rename (one playlist or all files), the playlist's own name,
the tidy operations, and the word lists the operations use. Right column: the full
before/after list of the chosen operation, undo/redo and the one button that applies
it. Nothing renames until that button is pressed. Below 960 px the columns stack."""

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from modules import playlists as library  # noqa: E402
from modules.config import user_settings  # noqa: E402
from ui import messages  # noqa: E402

logger = logging.getLogger("lmd.ui.file_control")

C = tokens.COLOR
FILLER_SHOWN = 12  # tags shown before "Show N more"
REPLACE_CHARS = 6  # replacement fields: they share a row with "becomes" and a button
PREVIEW_SHOWN = 300  # before/after rows drawn; the count above says how many change in all
PREVIEW_MIN_H = 360

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
# operations whose result depends on the word lists below: re-preview when they change
USES_WORDS = {"remove_filler", "apply_replacements", "clean"}


def _clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def _ellipsized_factory():
    """Dropdown cells that shorten long playlist names, so a long name never widens the window"""
    factory = Gtk.SignalListItemFactory()

    def setup(_factory, item):
        label = Gtk.Label(xalign=0.0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        item.set_child(label)

    def bind(_factory, item):
        item.get_child().set_text(item.get_item().get_string())

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    return factory


class FileControlPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.scope = "playlist"  # or "all"
        self.playlists = []  # library.list_playlists() rows, in dropdown order
        self.target = None  # the chosen playlist row
        self.operation = None
        self.planned = []
        self._words_open = False
        self._painting = False
        self._build()
        self.refresh()
        window.on_layout(self._on_layout)
        self.connect("map", lambda *_a: self.refresh())

    # ================================================================ layout
    def _build(self):
        page = kit.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), "lt-page")
        head = Gtk.Box(spacing=12)
        title = kit.text(messages.PAGE_FILE_CONTROL, "lt-title")
        title.set_hexpand(True)
        head.append(title)
        head.append(kit.text(messages.FC_CAPTION, "lt-caption", wrap=True))
        page.append(head)

        self.columns = Gtk.Box(spacing=12)
        self.columns.set_homogeneous(True)
        self.col_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.col_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.col_left.append(self._build_target_card())
        self.col_left.append(self._build_tidy_card())
        self.col_left.append(self._build_words_card())
        self.col_left.append(self._build_replacements_card())
        self.col_right.append(self._build_preview_card())
        self.columns.append(self.col_left)
        self.columns.append(self.col_right)
        scroller = kit.scrolled(self.columns)
        scroller.set_vexpand(True)
        page.set_vexpand(True)
        page.append(scroller)
        self.append(page)
        self.append(self.actionbar)

    def _on_layout(self, mode):
        self.columns.set_orientation(
            Gtk.Orientation.HORIZONTAL if mode == "wide" else Gtk.Orientation.VERTICAL
        )
        self.columns.set_homogeneous(mode == "wide")

    # -- what to rename
    def _build_target_card(self):
        card = kit.Card(messages.FC_CARD_TARGET)
        self.scope_seg = kit.Segmented(
            [("playlist", messages.FC_ONE_PLAYLIST), ("all", messages.LIB_ALL_FILES)],
            "playlist",
            self._on_scope,
            messages.FC_CARD_TARGET,
        )
        self.scope_seg.set_homogeneous(True)
        card.add_row(self.scope_seg)

        self.playlist_names = Gtk.StringList.new([])
        self.playlist_choice = kit.no_wheel(kit.css(Gtk.DropDown(model=self.playlist_names), "lt-select"))
        self.playlist_choice.set_factory(_ellipsized_factory())
        self.playlist_choice.set_hexpand(True)
        kit.name(self.playlist_choice, messages.FC_PLAYLIST)
        self.playlist_choice.connect("notify::selected", self._on_playlist_chosen)
        self.playlist_row = kit.field_row(messages.FC_PLAYLIST, self.playlist_choice, label_width=64)
        card.add_row(self.playlist_row)

        self.rename_entry = kit.entry(accessible_name=messages.FC_PLAYLIST_NAME, width_chars=12)
        self.rename_entry.set_hexpand(True)
        self.rename_entry.connect("activate", lambda *_a: self.apply_rename())
        self.rename_entry.connect("changed", lambda *_a: self._paint_rename_button())
        self.rename_button = kit.button(messages.FC_RENAME_GO, on_click=lambda *_a: self.apply_rename())
        self.rename_row = kit.field_row(
            messages.FC_PLAYLIST_NAME, kit.hbox(self.rename_entry, self.rename_button, spacing=8), label_width=64
        )
        card.add_row(self.rename_row)
        self.rename_note = kit.text("", "lt-caption", wrap=True)
        self.rename_note.set_visible(False)
        card.add_row(self.rename_note)
        self.no_playlists = kit.text(messages.FC_NO_PLAYLISTS, "lt-muted", wrap=True)
        card.add_row(self.no_playlists)
        return card

    # -- the operations
    def _build_tidy_card(self):
        card = kit.Card(messages.LIB_TIDY_NAMES)
        self.op_buttons = {}
        for heading, operations in TIDY_GROUPS:
            if heading:
                card.add_row(kit.text(heading, "lt-caption"))
            grid = Gtk.Grid(column_spacing=8, row_spacing=8)
            grid.set_column_homogeneous(True)
            for index, (label, operation) in enumerate(operations):
                op_button = kit.button(label, on_click=lambda *_, op=operation: self.select(op))
                op_button.set_hexpand(True)
                grid.attach(op_button, index % 2, index // 2, 1, 1)
                self.op_buttons[operation] = op_button
            card.add_row(grid)
        return card

    # -- filler words (from Settings)
    def _build_words_card(self):
        card = kit.Card(
            messages.FC_CARD_FILLER,
            action=(messages.SET_RESET_DEFAULTS, self._confirm_reset),
        )
        card.add_row(kit.text(messages.SET_FILLER_NOTE, "lt-muted", wrap=True))
        self.words_box = Gtk.FlowBox()
        self.words_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.words_box.set_homogeneous(False)  # each tag as wide as its word, not a column
        self.words_box.set_max_children_per_line(30)
        self.words_box.set_min_children_per_line(1)
        self.words_box.set_column_spacing(6)
        self.words_box.set_row_spacing(6)
        card.add_row(self.words_box)
        self.more_words = kit.button("", kind="link", on_click=self._toggle_words)
        card.add_row(self.more_words)
        self.word_entry = kit.entry(
            placeholder=messages.SET_ADD_WORD, accessible_name=messages.SET_ADD_WORD, width_chars=12
        )
        self.word_entry.set_hexpand(True)
        self.word_entry.connect("activate", lambda *_a: self._add_word())
        add = kit.button(messages.SET_ADD, on_click=lambda *_a: self._add_word())
        self.word_note = kit.text("", "lt-caption")
        card.add_row(kit.hbox(self.word_entry, add))
        card.add_row(self.word_note)
        return card

    # -- character replacements (from Settings)
    def _build_replacements_card(self):
        card = kit.Card(messages.SET_REPLACEMENTS)
        card.add_row(kit.text(messages.FC_REPLACEMENTS_NOTE, "lt-muted", wrap=True))
        self.replacements_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_row(self.replacements_box)
        self.replacement_note = kit.text("", "lt-error-text")
        card.add_row(self.replacement_note)
        return card

    # -- the preview
    def _build_preview_card(self):
        card = kit.Card(messages.FC_PREVIEW_TITLE)
        self.preview_words = kit.text(messages.FC_PICK_OPERATION, "lt-caption", wrap=True)
        card.add_row(self.preview_words)
        self.op_note = kit.text("", "lt-caption", wrap=True)
        self.op_note.set_visible(False)
        card.add_row(self.op_note)
        self.preview_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        preview_scroll = kit.scrolled(self.preview_rows, min_height=PREVIEW_MIN_H)
        preview_scroll.set_vexpand(True)
        kit.css(preview_scroll, "lmd-preview")
        card.add_row(preview_scroll, expand=True)

        self.undo_button = kit.icon_button("arrow-counter-clockwise", messages.LIB_UNDO, on_click=self._undo)
        self.redo_button = kit.icon_button("arrow-clockwise", messages.LIB_REDO, on_click=self._redo)
        self.apply_button = kit.button(messages.FC_APPLY_NONE, kind="primary", on_click=lambda *_a: self.apply())
        self.apply_button.set_sensitive(False)
        # undo, redo and apply sit in the page's action bar: always in view, however long the lists
        self.actionbar = kit.ActionBar()
        self.actionbar.add_action(self.undo_button)
        self.actionbar.add_action(self.redo_button)
        self.actionbar.add_action(self.apply_button)
        return card

    # ================================================================ state
    def refresh(self):
        """Re-read the playlists and the word lists, then repaint everything"""
        try:
            self.playlists = library.list_playlists() or []
        except Exception:
            logger.exception("listing playlists failed")
            self.playlists = []
        self._painting = True
        try:
            names = [p["name"] for p in self.playlists]
            self.playlist_names.splice(0, self.playlist_names.get_n_items(), names)
            paths = [p["path"] for p in self.playlists]
            keep = self.target["path"] if self.target else None
            index = paths.index(keep) if keep in paths else 0
            self.target = self.playlists[index] if self.playlists else None
            if self.playlists:
                self.playlist_choice.set_selected(index)
        finally:
            self._painting = False
        self._paint_target()
        self._paint_words()
        self._paint_replacements()
        self._paint_stack_buttons()
        self._paint_preview()

    def show_playlist(self, path):
        """Open on one playlist (the Library's "Rename files" button)"""
        self.scope_seg.set_value("playlist")
        self.scope = "playlist"
        self.target = next((p for p in self.playlists if p["path"] == path), {"path": path})
        self.refresh()

    def _on_scope(self, value):
        self.scope = value
        self._paint_target()
        self._paint_preview()

    def _on_playlist_chosen(self, *_args):
        if self._painting:
            return
        index = self.playlist_choice.get_selected()
        if 0 <= index < len(self.playlists):
            self.target = self.playlists[index]
        self._paint_target()
        self._paint_preview()

    def _paint_target(self):
        one = self.scope == "playlist"
        has = bool(self.playlists)
        self.playlist_row.set_visible(one and has)
        self.rename_row.set_visible(one and has)
        self.no_playlists.set_visible(one and not has)
        self.rename_note.set_visible(False)
        if self.target:
            self.rename_entry.set_text(self.target.get("name", ""))
        self._paint_rename_button()

    def _paint_rename_button(self):
        name = self.rename_entry.get_text().strip()
        current = (self.target or {}).get("name", "")
        self.rename_button.set_sensitive(bool(name) and name != current)

    def _paint_stack_buttons(self):
        state = library.stack_state()
        can_undo, can_redo = state.get("can_undo", False), state.get("can_redo", False)
        self.undo_button.set_sensitive(can_undo)
        self.redo_button.set_sensitive(can_redo)
        self.undo_button.set_tooltip_text(messages.LIB_UNDO if can_undo else messages.LIB_UNDO_NONE)
        self.redo_button.set_tooltip_text(messages.LIB_REDO if can_redo else messages.LIB_REDO_NONE)

    def file_count(self):
        if self.scope == "all":
            try:
                return len(library.list_all_media())
            except Exception:
                return 0
        return (self.target or {}).get("file_count") or 0

    # ================================================================ preview + apply
    def select(self, operation):
        self.operation = operation
        for other, button in self.op_buttons.items():
            (kit.css if other == operation else kit.uncss)(button, "lmd-selected")
        self._paint_preview()

    def _plan(self):
        if not self.operation:
            return []
        try:
            if self.scope == "all":
                return library.preview_global(self.operation) or []
            if not self.target:
                return []
            return library.preview_operation(self.target["path"], self.operation) or []
        except Exception:
            logger.exception("previewing %s failed", self.operation)
            return []

    def _paint_preview(self):
        self.planned = self._plan()
        _clear_box(self.preview_rows)
        is_delete = self.operation == "delete_long"
        self.op_note.set_text(messages.LIB_OP_DELETE_LONG_NOTE if is_delete else "")
        self.op_note.set_visible(is_delete)
        changed, total = len(self.planned), self.file_count()
        if not self.operation:
            self.preview_words.set_text(messages.FC_PICK_OPERATION)
        elif self.scope == "playlist" and not self.target:
            self.preview_words.set_text(messages.FC_NO_PLAYLISTS)
        elif changed:
            self.preview_words.set_text(messages.LIB_PREVIEW.format(k=changed, n=total))
        else:
            self.preview_words.set_text(messages.LIB_PREVIEW_NONE)
        for old, new in self.planned[:PREVIEW_SHOWN]:
            self.preview_rows.append(self._preview_row(old, new, is_delete))
        if changed > PREVIEW_SHOWN:
            self.preview_rows.append(
                kit.text(messages.FC_PREVIEW_MORE.format(n=changed - PREVIEW_SHOWN), "lt-caption")
            )
        if changed:
            label = messages.LIB_MOVE_K if is_delete else messages.LIB_RENAME_K
            self.apply_button.set_label(label.format(k=changed))
        else:
            self.apply_button.set_label(messages.FC_APPLY_NONE)
        self.apply_button.set_sensitive(changed > 0)
        self.apply_button.set_tooltip_text("" if changed else messages.LIB_PREVIEW_NONE)
        self._paint_actionbar()

    def _paint_actionbar(self):
        """What Apply will do, in words: the change, then where"""
        if not self.operation:
            self.actionbar.idle(messages.FC_PICK_OPERATION, "")
            return
        names = {op: label for _heading, ops in TIDY_GROUPS for label, op in ops}
        where = messages.LIB_ALL_FILES if self.scope == "all" else (self.target or {}).get("name", "")
        self.actionbar.idle(self.preview_words.get_text(), f"{names[self.operation]} · {where}")

    @staticmethod
    def _preview_row(old, new, is_delete):
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        before = kit.text(old, "lt-mono", "lmd-dim")
        before.set_ellipsize(Pango.EllipsizeMode.MIDDLE)  # keeps the extension in view
        before.set_tooltip_text(old)
        row.append(before)
        after_words = messages.FC_TO_TRASH if is_delete else new
        after = kit.text(after_words, "lt-mono")
        after.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        after.set_tooltip_text(after_words)
        row.append(kit.hbox(kit.text(messages.LIB_PREVIEW_BECOMES, "lt-caption"), after, spacing=8))
        return row

    def apply(self):
        """The only place a tidy operation runs"""
        if not self.operation or not self.planned:
            return
        try:
            if self.scope == "all":
                result = library.global_operation(self.operation)
            else:
                result = library.apply_operation(self.target["path"], self.operation)
        except Exception:
            logger.exception("applying %s failed", self.operation)
            return
        logger.info("tidy %s: %s", self.operation, {k: v for k, v in result.items() if k != "moves"})
        self._after_change()

    def apply_rename(self):
        if not self.target:
            return
        name = self.rename_entry.get_text().strip()
        if not name or name == self.target.get("name"):
            return
        old_path = self.target["path"]
        result = library.rename_playlist(old_path, name)
        if result.get("status") == "success":
            new_path, new_name = result.get("path") or old_path, result.get("name") or name
            self.target = dict(self.target, name=new_name, path=new_path)
            self._after_change(renamed=(old_path, new_path))
            self.rename_note.set_text(messages.FC_RENAMED.format(name=new_name))
            kit.uncss(self.rename_note, "lt-error-text")
        else:
            self.rename_note.set_text(result.get("message", ""))
            kit.css(self.rename_note, "lt-error-text")
        self.rename_note.set_visible(True)

    def _undo(self):
        library.undo_last()
        self._after_change()

    def _redo(self):
        library.redo_last()
        self._after_change()

    def _after_change(self, renamed=None):
        """Repaint here and let the Library show the new names"""
        self.refresh()
        library_page = getattr(self.window, "library_page", None)
        if library_page is not None:
            library_page.files_changed(renamed)

    # ================================================================ word lists
    def _paint_words(self):
        words = list(user_settings.get_settings().get("filler_words") or [])
        _clear_box(self.words_box)
        shown = words if self._words_open else words[:FILLER_SHOWN]
        for word in shown:
            self.words_box.append(self._word_tag(word))
        child = self.words_box.get_first_child()
        while child:  # the tags' remove buttons take focus, not their cells
            child.set_can_focus(False)
            child.set_halign(Gtk.Align.START)
            child = child.get_next_sibling()
        hidden = len(words) - len(shown)
        if hidden or self._words_open and len(words) > FILLER_SHOWN:
            self.more_words.set_label(
                messages.SET_MORE_WORDS.format(n=hidden) if hidden else messages.SET_FEWER_WORDS
            )
            self.more_words.set_visible(True)
        else:
            self.more_words.set_visible(False)

    def _word_tag(self, word):
        tag = kit.css(Gtk.Box(spacing=4), "lt-pill", "lmd-tag")
        tag.append(Gtk.Label(label=word))
        spoken = messages.SET_REMOVE_WORD.format(word=word)
        remove = kit.icon_button("x", spoken, on_click=lambda *_, w=word: self._remove_word(w))
        kit.css(remove, "lmd-tag-x")  # a 32 px target (the guide's floor) keeps the pill compact
        remove.set_child(kit.icon("x", 14))
        remove.set_valign(Gtk.Align.CENTER)
        tag.set_valign(Gtk.Align.CENTER)
        tag.append(remove)
        return tag

    def _toggle_words(self, *_args):
        self._words_open = not self._words_open
        self._paint_words()

    def _words_changed(self):
        if self.operation in USES_WORDS:
            self._paint_preview()

    def _add_word(self, *_args):
        word = self.word_entry.get_text().strip().lower()
        if not word:
            return
        words = list(user_settings.get_settings().get("filler_words") or [])
        if word in words:
            self.word_note.set_text(messages.SET_WORD_EXISTS)
            return
        user_settings.save_settings({"filler_words": words + [word]})
        self.word_entry.set_text("")
        self.word_note.set_text(messages.SET_WORD_ADDED)
        self._paint_words()
        self._words_changed()

    def _remove_word(self, word):
        words = [w for w in (user_settings.get_settings().get("filler_words") or []) if w != word]
        user_settings.save_settings({"filler_words": words})
        self._paint_words()
        self._words_changed()

    def _confirm_reset(self, *_args):
        kit.confirm(
            self.window,
            messages.SET_RESET_TITLE,
            messages.SET_RESET_BODY,
            messages.SET_RESET_GO,
            destructive=True,
            cancel_label=messages.SET_RESET_KEEP,
            on_answer=lambda yes: self._reset_tidy() if yes else None,
        )

    def _reset_tidy(self):
        user_settings.reset_settings(["filler_words", "char_replacements"])
        self._words_open = False
        self._paint_words()
        self._paint_replacements()
        self._words_changed()

    def _paint_replacements(self):
        _clear_box(self.replacements_box)
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        for index, row in enumerate(rows):
            self.replacements_box.append(self._replacement_row(index, row))
        self.replacements_box.append(self._add_replacement_row())

    def _replacement_row(self, index, row):
        box = Gtk.Box(spacing=8)
        frm = kit.entry(value=row.get("from", ""), accessible_name=messages.SET_FROM, width_chars=REPLACE_CHARS)
        frm.set_hexpand(True)
        frm.connect("activate", lambda *_a, e=frm, i=index: self._save_replacement(i, "from", e))
        to = kit.entry(value=row.get("to", ""), accessible_name=messages.SET_TO, width_chars=REPLACE_CHARS)
        to.set_hexpand(True)
        to.connect("activate", lambda *_a, e=to, i=index: self._save_replacement(i, "to", e))
        remove = kit.icon_button(
            "x", messages.SET_REMOVE_REPLACEMENT, on_click=lambda *_, i=index: self._remove_replacement(i)
        )
        box.append(frm)
        box.append(kit.text(messages.SET_BECOMES, "lt-muted"))
        box.append(to)
        box.append(remove)
        return box

    def _add_replacement_row(self):
        box = Gtk.Box(spacing=8)
        self.new_from = kit.entry(
            placeholder=messages.SET_FROM, accessible_name=messages.SET_FROM, width_chars=REPLACE_CHARS
        )
        self.new_from.set_hexpand(True)
        self.new_to = kit.entry(placeholder=messages.SET_TO, accessible_name=messages.SET_TO, width_chars=REPLACE_CHARS)
        self.new_to.set_hexpand(True)
        self.new_to.connect("activate", lambda *_a: self._add_replacement())
        add = kit.button(messages.SET_ADD, on_click=lambda *_a: self._add_replacement())
        kit.name(add, messages.SET_ADD_REPLACEMENT)
        box.append(self.new_from)
        box.append(kit.text(messages.SET_BECOMES, "lt-muted"))
        box.append(self.new_to)
        box.append(add)
        return box

    def _add_replacement(self):
        frm = self.new_from.get_text().strip()
        to = self.new_to.get_text().strip()
        if not frm:
            self.replacement_note.set_text(messages.SET_REPLACEMENT_NEEDS_FROM)
            return
        self.replacement_note.set_text("")
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        rows.append({"from": frm, "to": to})
        user_settings.save_settings({"char_replacements": rows})
        self._paint_replacements()
        self._words_changed()

    def _save_replacement(self, index, key, entry):
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        if index < len(rows):
            rows[index][key] = entry.get_text()
            user_settings.save_settings({"char_replacements": rows})
            self._words_changed()

    def _remove_replacement(self, index):
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        if index < len(rows):
            del rows[index]
            user_settings.save_settings({"char_replacements": rows})
            self._paint_replacements()
            self._words_changed()

