# ui/pages/settings.py
"""The Settings page: two columns of cards in one scrolling page ("Changes save
as you make them" — every control saves at once through
user_settings.save_settings, no Save button, no confirm on leave).

Slow work never blocks the UI: the tool versions, browser discovery, the yt-dlp
update and the diagnostics zip all run in worker threads and report back with
GLib.idle_add. Below 960 px the two columns stack into one.
"""

import logging
import os
import threading
from datetime import date

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from modules import tools
from modules.config import paths, settings, user_settings
from modules.download import access
from modules.utils import file_utils
from ui import messages
from ui.pages.download import tilde

logger = logging.getLogger("lmd.ui.settings")

C = tokens.COLOR
FILLER_SHOWN = 12


def _clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def _run_in_thread(work, on_done):
    """work() in a daemon thread; on_done(result) on the main loop"""

    def runner():
        try:
            result = work()
        except Exception as exc:  # a worker crash must not hang the page
            logger.exception("settings worker failed")
            result = exc
        GLib.idle_add(lambda: (on_done(result), False)[1])

    threading.Thread(target=runner, daemon=True, name="lmd-settings").start()


class SettingsPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._tools_read = False
        self._updating = False
        self._words_open = False
        self._build()
        self._load_values()
        window.on_layout(self._on_layout)

    # ================================================================ layout
    def _build(self):
        page = kit.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), "lt-page")
        head = Gtk.Box(spacing=12)
        title = kit.text(messages.PAGE_SETTINGS, "lt-title")
        title.set_hexpand(True)
        head.append(title)
        head.append(kit.text(messages.SET_CAPTION, "lt-caption"))
        page.append(head)

        self.columns = Gtk.Box(spacing=12)
        self.columns.set_homogeneous(True)
        self.col_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.col_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.col_left.append(self._build_downloads_card())
        self.col_left.append(self._build_tidy_card())
        self.col_right.append(self._build_tools_card())
        self.col_right.append(self._build_signin_card())
        self.col_right.append(self._build_privacy_card())
        self.col_right.append(self._build_about_card())
        self.columns.append(self.col_left)
        self.columns.append(self.col_right)
        scroller = kit.scrolled(self.columns)
        scroller.set_vexpand(True)  # take the height the window has; long content scrolls inside
        page.set_vexpand(True)
        page.append(scroller)
        self.append(page)
        # the tool versions and the browser scan run once, when the page is first shown
        self.connect("map", lambda *_a: (self._read_tools_once(), self.discover_signin()))

    def _on_layout(self, mode):
        self.columns.set_orientation(
            Gtk.Orientation.HORIZONTAL if mode == "wide" else Gtk.Orientation.VERTICAL
        )
        self.columns.set_homogeneous(mode == "wide")

    # ================================================================ Downloads
    def _build_downloads_card(self):
        card = kit.Card(messages.SET_CARD_DOWNLOADS)
        self.folder_label = kit.text("")
        folder_box = kit.css(
            kit.hbox(kit.icon("folder-simple", 18, C["text_muted"]), self.folder_label, spacing=8),
            "lt-entry",
        )
        folder_box.set_hexpand(True)
        kit.name(folder_box, messages.SET_FOLDER_NAME)
        self.use_default = kit.button(messages.SET_USE_DEFAULT, kind="link", on_click=self._use_default)
        change = kit.button(messages.SET_CHANGE, on_click=self._change_folder)
        card.add_row(kit.hbox(folder_box, self.use_default, change))
        self.folder_error = kit.text("", "lt-error-text")
        self.folder_error.set_visible(False)  # shown only with a message (no empty gap)
        card.add_row(self.folder_error)
        self.folder_note = kit.text("", "lt-caption")
        card.add_row(self.folder_note)

        self.format_seg = kit.Segmented(
            [("audio", messages.FORMAT_AUDIO), ("video", messages.FORMAT_VIDEO)],
            "audio",
            self._save_format,
            messages.SET_FORMAT_NAME,
        )
        card.add_row(kit.field_row(messages.SET_FORMAT, self.format_seg, label_width=110))

        self.quality_seg = kit.Segmented(
            [
                ("1080", messages.QUALITY_1080),
                ("720", messages.QUALITY_720),
                ("480", messages.QUALITY_480),
            ],
            "1080",
            self._save_quality,
            messages.SET_QUALITY_NAME,
        )
        card.add_row(kit.field_row(messages.SET_QUALITY, self.quality_seg, label_width=110))

        low, high = user_settings.LONG_MINUTES_RANGE
        self.minutes = kit.Stepper(7, low, high, self._save_minutes, messages.SET_LONG_NAME, unit="")
        card.add_row(
            kit.hbox(
                kit.text(messages.SET_LONG_MEANS, "lt-field-label"),
                self.minutes,
                kit.text(messages.SET_LONG_NOTE, "lt-caption"),
                spacing=12,
            )
        )
        return card

    def _load_values(self):
        values = user_settings.get_settings()
        self._paint_folder(values.get("download_folder") or "")
        self.format_seg.set_value(values.get("download_type") or "audio")
        self.quality_seg.set_value(str(values.get("video_quality") or "1080"))
        self.minutes.set_value(int(values.get("long_minutes") or 7))
        self._paint_words()
        self._paint_replacements()
        self._paint_signin_choice()

    # -- folder
    def _paint_folder(self, saved):
        folder = settings.download_folder(create=False)
        self.folder_label.set_text(tilde(folder))
        self.use_default.set_visible(bool(saved))
        default = tilde(settings.default_download_folder())
        self.folder_note.set_text(messages.SET_FOLDER_NOTE.format(path=default))
        self.folder_error.set_text("")
        self.folder_error.set_visible(False)

    def _change_folder(self, *_args):
        dialog = Gtk.FileDialog()
        try:
            dialog.set_initial_folder(Gio.File.new_for_path(settings.download_folder(create=False)))
        except Exception:
            logger.debug("could not set the folder picker's start folder")
        dialog.select_folder(self.window, None, self._folder_chosen)

    def _folder_chosen(self, dialog, result):
        try:
            chosen = dialog.select_folder_finish(result)
        except GLib.Error as exc:
            logger.info("the folder picker was dismissed: %s", exc.message)
            return
        path = chosen.get_path() if chosen else None
        if not path or not self._folder_writable(path):
            self.folder_error.set_text(messages.SET_FOLDER_DENIED)
            self.folder_error.set_visible(True)
            return
        user_settings.save_settings({"download_folder": path})
        self._paint_folder(path)

    @staticmethod
    def _folder_writable(path):
        try:
            os.makedirs(path, exist_ok=True)
            return os.access(path, os.W_OK)
        except OSError:
            return False

    def _use_default(self, *_args):
        user_settings.save_settings({"download_folder": ""})
        self._paint_folder("")

    # -- format / quality / minutes
    def _save_format(self, value):
        user_settings.save_settings({"download_type": value})

    def _save_quality(self, value):
        user_settings.save_settings({"video_quality": value})

    def _save_minutes(self, value):
        user_settings.save_settings({"long_minutes": value})

    # ================================================================ Tidy names
    def _build_tidy_card(self):
        card = kit.Card(
            messages.SET_CARD_TIDY,
            action=(messages.SET_RESET_DEFAULTS, self._confirm_reset),
        )
        card.add_row(kit.text(messages.SET_FILLER_NOTE, "lt-muted"))
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
            placeholder=messages.SET_ADD_WORD, accessible_name=messages.SET_ADD_WORD, width_chars=18
        )
        self.word_entry.set_hexpand(True)
        self.word_entry.connect("activate", lambda *_a: self._add_word())
        add = kit.button(messages.SET_ADD, on_click=lambda *_a: self._add_word())
        self.word_note = kit.text("", "lt-caption")
        card.add_row(kit.hbox(self.word_entry, add))
        card.add_row(self.word_note)

        card.add_row(kit.text(messages.SET_REPLACEMENTS, "lt-muted"))
        self.replacements_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_row(self.replacements_box)
        return card

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

    def _remove_word(self, word):
        words = [w for w in (user_settings.get_settings().get("filler_words") or []) if w != word]
        user_settings.save_settings({"filler_words": words})
        self._paint_words()

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

    # -- replacements
    def _paint_replacements(self):
        _clear_box(self.replacements_box)
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        for index, row in enumerate(rows):
            self.replacements_box.append(self._replacement_row(index, row))
        self.replacements_box.append(self._add_replacement_row())

    def _replacement_row(self, index, row):
        box = Gtk.Box(spacing=8)
        frm = kit.entry(value=row.get("from", ""), accessible_name=messages.SET_FROM, width_chars=10)
        frm.connect("activate", lambda *_a, e=frm, i=index: self._save_replacement(i, "from", e))
        to = kit.entry(value=row.get("to", ""), accessible_name=messages.SET_TO, width_chars=10)
        to.connect("activate", lambda *_a, e=to, i=index: self._save_replacement(i, "to", e))
        remove = kit.icon_button(
            "x", messages.SET_REMOVE_REPLACEMENT, on_click=lambda *_, i=index: self._remove_replacement(i)
        )
        box.append(frm)
        box.append(kit.text(messages.SET_BECOMES, "lt-muted"))
        box.append(to)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        box.append(spacer)
        box.append(remove)
        return box

    def _add_replacement_row(self):
        box = Gtk.Box(spacing=8)
        self.new_from = kit.entry(
            placeholder=messages.SET_FROM, accessible_name=messages.SET_FROM, width_chars=10
        )
        self.new_to = kit.entry(placeholder=messages.SET_TO, accessible_name=messages.SET_TO, width_chars=10)
        self.replacement_note = kit.text("", "lt-error-text")
        self.new_to.connect("activate", lambda *_a: self._add_replacement())
        add = kit.button(messages.SET_ADD_REPLACEMENT, on_click=lambda *_a: self._add_replacement())
        box.append(self.new_from)
        box.append(kit.text(messages.SET_BECOMES, "lt-muted"))
        box.append(self.new_to)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        box.append(spacer)
        box.append(add)
        return box

    def _add_replacement(self):
        frm = self.new_from.get_text().strip()
        to = self.new_to.get_text().strip()
        if not frm:
            self.replacement_note.set_text(messages.SET_REPLACEMENT_NEEDS_FROM)
            return
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        rows.append({"from": frm, "to": to})
        user_settings.save_settings({"char_replacements": rows})
        self._paint_replacements()

    def _save_replacement(self, index, key, entry):
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        if index < len(rows):
            rows[index][key] = entry.get_text()
            user_settings.save_settings({"char_replacements": rows})

    def _remove_replacement(self, index):
        rows = list(user_settings.get_settings().get("char_replacements") or [])
        if index < len(rows):
            del rows[index]
            user_settings.save_settings({"char_replacements": rows})
            self._paint_replacements()

    # ================================================================ Tools
    def _build_tools_card(self):
        card = kit.Card(messages.SET_CARD_TOOLS)
        self.ytdlp_status = Gtk.Box(spacing=8)
        self.ytdlp_caption = kit.text("", "lt-caption")
        self.update_button = kit.button(messages.SET_CHECK_UPDATE, on_click=self._update_ytdlp)
        card.add_row(
            kit.hbox(
                self.ytdlp_status,
                self._words_block(self.ytdlp_caption),
                self.update_button,
                expand_last=True,
            )
        )
        self.update_status = Gtk.Box(spacing=8)  # spinner + words, or the result
        card.add_row(self.update_status)
        self.update_details = Gtk.Expander(label=messages.SET_DETAILS)
        self.update_detail_text = kit.text("", "lt-mono", wrap=True, selectable=True)
        self.update_details.set_child(self.update_detail_text)
        self.update_details.set_visible(False)
        card.add_row(self.update_details)

        self.ffmpeg_status = Gtk.Box(spacing=8)
        self.ffmpeg_caption = kit.text("", "lt-caption")
        card.add_row(kit.hbox(self.ffmpeg_status, self._words_block(self.ffmpeg_caption), expand_last=True))
        card.add_row(kit.text(messages.SET_RESTART_NOTE, "lt-caption"))
        return card

    @staticmethod
    def _words_block(caption):
        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        block.set_hexpand(True)
        block.append(caption)
        return block

    def _read_tools_once(self):
        if self._tools_read:
            return
        self._tools_read = True

        def read():
            return tools.ytdlp_version(), tools.ffmpeg_version()

        _run_in_thread(read, self._paint_tools)

    def _paint_tools(self, result):
        if isinstance(result, Exception):
            logger.warning("reading the tool versions failed: %s", result)
            return
        ytdlp, (ffmpeg_version, ffmpeg_path) = result
        self._set_tool_row(self.ytdlp_status, self.ytdlp_caption, messages.SET_YTDLP, ytdlp, "")
        self._set_tool_row(
            self.ffmpeg_status, self.ffmpeg_caption, messages.SET_FFMPEG, ffmpeg_version, ffmpeg_path
        )
        self.update_button.set_sensitive(tools.can_update_ytdlp())
        if not tools.can_update_ytdlp():
            self.update_button.set_tooltip_text(messages.SET_UPDATE_BLOCKED)

    @staticmethod
    def _set_tool_row(status_box, caption, name, version, path):
        ok = version is not None
        _clear_box(status_box)
        status_box.append(kit.status_icon("ok" if ok else "attention", 18))
        status_box.append(kit.text(name, "lt-strong"))
        words = messages.SET_READY if ok else messages.SET_NEEDS_YOU
        status_box.append(kit.text(words, "lt-ok-text" if ok else "lt-attention-text"))
        detail = version if ok else messages.SET_FROM_SYSTEM
        if ok and path:
            detail = f"{version} · {tilde(path)}"
        caption.set_text(detail)

    def _update_ytdlp(self, *_args):
        """pip-install the newest yt-dlp off the main loop; the result in plain words"""
        if self._updating:
            return
        self._updating = True
        self.update_button.set_sensitive(False)
        before = tools.ytdlp_version()
        spinner = Gtk.Spinner()
        spinner.start()
        _clear_box(self.update_status)
        self.update_status.append(spinner)
        self.update_status.append(kit.text(messages.SET_UPDATING, "lt-caption"))
        _run_in_thread(tools.update_ytdlp, lambda result: self._paint_update(result, before))

    def _paint_update(self, result, before):
        self._updating = False
        self.update_button.set_sensitive(tools.can_update_ytdlp())
        if isinstance(result, Exception):
            result = {"ok": False, "before": before, "after": before, "output": str(result)}
        _clear_box(self.update_status)
        if result.get("ok"):
            after = result.get("after")
            if after and after != result.get("before"):
                words = messages.SET_UPDATED.format(before=result.get("before"), after=after)
            else:
                words = messages.SET_ALREADY_NEW.format(version=after or before)
            self.update_status.append(kit.text(words, "lt-caption"))
            self.update_details.set_visible(False)
        else:
            self.update_status.append(kit.text(messages.SET_UPDATE_FAILED, "lt-caption"))
            self.update_detail_text.set_text(result.get("output") or "")
            self.update_details.set_visible(True)
        logger.info("yt-dlp update finished: ok=%s", result.get("ok"))

    # ================================================================ Sign-in
    def _build_signin_card(self):
        card = kit.Card(messages.SET_CARD_SIGNIN)
        self._signin_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_row(kit.field_row(messages.SET_SIGNIN_NAME, self._signin_holder, label_width=110))
        self._refresh_signin_options([])
        self.signin_now = kit.text(messages.SET_SIGNIN_CHECKING, "lt-caption")
        card.add_row(self.signin_now)
        card.add_row(kit.text(messages.SET_SIGNIN_NOTE, "lt-muted", wrap=True))
        return card

    def _refresh_signin_options(self, profiles):
        """(Re)build the dropdown: Automatic, one entry per profile, Off. Labels show
        the browser and its profile folder, never cookie details."""
        choice = user_settings.get_settings().get("browser_access") or "auto"
        options = [("auto", messages.SET_SIGNIN_AUTO)]
        for profile in profiles:
            options.append((profile.path, f"{profile.browser} · {os.path.basename(profile.path)}"))
        if choice not in ("auto", "off") and not any(value == choice for value, _label in options):
            # a profile picked earlier that discovery has not (yet) found: keep it listed, so
            # building the list never quietly replaces the saved choice with "Automatic"
            options.append((choice, messages.SET_SIGNIN_SAVED.format(name=os.path.basename(choice))))
        options.append(("off", messages.SET_SIGNIN_OFF))
        self._profiles = list(profiles)
        _clear_box(self._signin_holder)
        # no handler while the saved value is selected: selecting it would save it again
        self.signin_choice = kit.select(options, choice, None, messages.SET_SIGNIN_NAME)
        self.signin_choice.connect(
            "notify::selected", lambda *_a: self._save_signin(self.signin_choice.get_active_id())
        )
        self.signin_choice.set_hexpand(True)
        self._signin_holder.append(self.signin_choice)

    def _paint_signin_choice(self):
        """Show the saved choice (the list is rebuilt once discovery reports the profiles)"""
        self._refresh_signin_options(getattr(self, "_profiles", []))

    def _save_signin(self, value):
        user_settings.save_settings({"browser_access": value})
        self._read_signin_now()

    def _read_signin_now(self):
        def work():
            described = access.current(refresh=True).describe()
            browser = described.get("browser")
            runtime = described.get("js_runtime")
            words = browser or ""
            if runtime:
                words = f"{words} · {runtime}" if words else str(runtime)
            return words

        _run_in_thread(work, self._paint_signin_now)

    def _paint_signin_now(self, words):
        choice = user_settings.get_settings().get("browser_access") or "auto"
        if choice == "off":
            self.signin_now.set_text(messages.SET_SIGNIN_OFF_NOW)
        elif isinstance(words, Exception) or not words:
            self.signin_now.set_text(messages.SET_SIGNIN_NONE)
        else:
            self.signin_now.set_text(messages.SET_SIGNIN_NOW.format(words=words))

    # ================================================================ Privacy
    def _build_privacy_card(self):
        card = kit.Card(messages.SET_CARD_PRIVACY)
        card.add_row(
            kit.key_values(
                [
                    (messages.SET_KEPT_HERE, messages.SET_KEPT_HERE_VALUE),
                    (messages.SET_FOLDER_KEY, tilde(paths.DATA_DIR)),
                    (messages.SET_NETWORK, messages.SET_NETWORK_VALUE),
                ]
            )
        )
        card.add_row(
            kit.hbox(
                kit.button(
                    messages.SET_OPEN_DATA, on_click=lambda *_a: file_utils.open_folder(paths.DATA_DIR)
                ),
                kit.button(messages.SET_SAVE_DIAGNOSTICS, on_click=self._save_diagnostics),
            )
        )
        self.diag_status = Gtk.Box(spacing=8)
        card.add_row(self.diag_status)
        return card

    def _save_diagnostics(self, *_args):
        dialog = Gtk.FileDialog()
        dialog.set_initial_name(f"linmediadownloader-diagnostics-{date.today().isoformat()}.zip")
        dialog.save(self.window, None, self._diagnostics_target_chosen)

    def _diagnostics_target_chosen(self, dialog, result):
        try:
            target = dialog.save_finish(result)
        except GLib.Error as exc:
            logger.info("the diagnostics picker was dismissed: %s", exc.message)
            return
        path = target.get_path() if target else None
        if not path:
            return
        _clear_box(self.diag_status)  # a box: the words go in a label inside it
        self.diag_status.append(kit.text(messages.SET_DIAG_SAVING, "lt-caption"))

        def work():
            return tools.save_diagnostics(path)

        _run_in_thread(work, self._paint_diagnostics)

    def _paint_diagnostics(self, result):
        if isinstance(result, Exception) or not result:
            _clear_box(self.diag_status)
            self.diag_status.append(kit.text(messages.SET_DIAG_FAILED, "lt-caption"))
            return
        _clear_box(self.diag_status)
        self.diag_status.append(kit.text(messages.SET_DIAG_SAVED.format(path=tilde(result)), "lt-caption"))
        self.diag_status.append(
            kit.button(
                messages.SET_SHOW_FILE,
                on_click=lambda *_a, path=result: file_utils.show_file(path),
                small=True,
            )
        )

    # ================================================================ About
    def _build_about_card(self):
        card = kit.Card(messages.SET_CARD_ABOUT)
        gtk_words = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}"
        card.add_row(
            kit.key_values(
                [
                    (messages.SET_VERSION, messages.SET_VERSION_VALUE.format(gtk=gtk_words)),
                    (messages.SET_LICENCE, messages.SET_LICENCE_VALUE),
                ]
            )
        )
        card.add_row(
            kit.hbox(
                kit.button(messages.SET_SHORTCUTS, on_click=self._show_shortcuts),
                kit.button(messages.SET_HELP, on_click=self._show_help),
                kit.button(messages.SET_CREDITS, on_click=self._show_credits),
            )
        )
        return card

    def _small_window(self, title, content):
        window = Gtk.Window(transient_for=self.window, modal=True, title=title)
        kit.css(window, "lt-root", "lt-dialog")
        window.set_default_size(460, 420)
        area = kit.scrolled(content)
        for edge in ("top", "bottom", "start", "end"):
            getattr(area.get_child(), f"set_margin_{edge}")(20)
        window.set_child(area)
        window.present()
        return window

    def _show_shortcuts(self, *_args):
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for keys, meaning in messages.SHORTCUT_ROWS:
            row = Gtk.Box(spacing=12)
            keys_label = kit.text(keys, "lt-kbd")
            row.append(keys_label)
            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            row.append(spacer)
            row.append(kit.text(meaning))
            rows.append(row)
        self._small_window(messages.SET_SHORTCUTS_TITLE, rows)

    def _show_help(self, *_args):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for question, answer in messages.HELP_SECTIONS:
            content.append(kit.text(question, "lt-heading", wrap=True))
            content.append(kit.text(answer, wrap=True))
        self._small_window(messages.HELP_TITLE, content)

    def _show_credits(self, *_args):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.append(kit.text(messages.SET_CREDITS_TITLE, "lt-heading"))
        content.append(kit.text(messages.SET_CREDITS_WORDS, wrap=True))
        self._small_window(messages.SET_CREDITS_TITLE, content)

    # ================================================================ discovery
    def discover_signin(self):
        """Called on first map: browser discovery in a worker (tests patch this)"""

        def work():
            return access.discover_profiles()

        _run_in_thread(
            work,
            lambda profiles: self._refresh_signin_options(
                [] if isinstance(profiles, Exception) else profiles
            ),
        )
