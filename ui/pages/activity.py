# ui/pages/activity.py
"""The Activity page: what is downloading now, what waits in the queue, and one
merged history of every link the user ever pasted (downloads plus links that
never became one), grouped by day, searchable and filterable.

The merging, grouping, filtering and clearing live in modules/history.py
(GTK-free, tested there). The Now card follows its own SnapshotPoller while the
page is visible and a download runs; the queue comes from jobs.queue_snapshot().
"""

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from modules import history
from modules.download import jobs  # noqa: E402
from modules.utils import file_utils  # noqa: E402
from ui import messages  # noqa: E402
from ui.pages.download import fmt_eta_left, tilde  # noqa: E402
from ui.poller import ACTIVE_STATUSES, SnapshotPoller, snapshot_copy  # noqa: E402

logger = logging.getLogger("lmd.ui.activity")

C = tokens.COLOR
RESULT_PILLS = {
    "done": (None, messages.ACT_RESULT_DONE, "ok"),  # no checkmark in pills (user)
    "partial": (None, messages.ACT_RESULT_PARTIAL, "attention"),
    "cancelled": (None, messages.ACT_RESULT_CANCELLED, None),
    "failed": ("link-break", messages.ACT_RESULT_FAILED, "error"),
    "not_downloaded": (None, messages.ACT_RESULT_NOT_DOWNLOADED, None),
}
# tile tint per result: (background, foreground) token colours


def _clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


# result -> the tint class ui/style.py generates from tokens (None = default tile)
RESULT_TILES = {
    "done": "lmd-tile-ok",
    "partial": "lmd-tile-attention",
    "failed": "lmd-tile-error",
}
RESULT_TILE_FG = {
    "done": C["ok"],
    "partial": C["attention"],
    "failed": C["error"],
}


def _tinted_tile(icon_name, result):
    """The 40 px type tile, tinted by the entry's result (ok/attention/error/muted).
    A fixed size request keeps it square: expanding children let it stretch."""
    tile = kit.css(Gtk.Box(), "lt-icon-tile", RESULT_TILES.get(result))
    tile.set_size_request(40, 40)
    tile.set_hexpand(False)  # set explicitly: the icon's expand must not spread to the row
    tile.set_vexpand(False)
    tile.set_halign(Gtk.Align.START)
    tile.set_valign(Gtk.Align.CENTER)
    mark = kit.icon(icon_name, 22, RESULT_TILE_FG.get(result, C["text_muted"]))
    mark.set_halign(Gtk.Align.CENTER)
    mark.set_valign(Gtk.Align.CENTER)
    mark.set_hexpand(True)  # a Box gives a child only its natural width: it must expand to centre
    mark.set_vexpand(True)
    tile.append(mark)
    return tile


def _pill_words(result):
    icon_name, words, kind = RESULT_PILLS.get(result, RESULT_PILLS["not_downloaded"])
    box = kit.css(Gtk.Box(spacing=6), "lt-pill", f"lt-{kind}" if kind else None)
    if icon_name:
        colour = {"ok": C["ok"], "attention": C["attention"], "error": C["error"]}.get(kind)
        box.append(kit.icon(icon_name, 14, colour))
    box.append(Gtk.Label(label=words))
    return box


class ActivityPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.query = ""
        self.kind_filter = "all"
        self.poller = SnapshotPoller(self.on_snapshot)

        self._build()
        self.refresh_history()
        self.refresh_queue()
        self.refresh_now(snapshot_copy())
        # The Now card tracks the running download only while the page is on screen
        self.connect("map", lambda *_a: self._sync_poller())
        self.connect("unmap", lambda *_a: self.poller.stop())

    # ================================================================ build
    def _build(self):
        page = kit.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), "lt-page")
        head = Gtk.Box(spacing=12)
        title = kit.text(messages.PAGE_ACTIVITY, "lt-title")
        title.set_hexpand(True)
        self.search = kit.entry(
            placeholder=messages.ACT_SEARCH_PLACEHOLDER,
            accessible_name=messages.ACT_SEARCH_NAME,
            width_chars=24,
        )
        self.search.set_hexpand(True)
        self.search.connect("changed", self._on_search_changed)
        self.filter_seg = kit.Segmented(
            [
                ("all", messages.ACT_ALL),
                ("audio", messages.ACT_AUDIO),
                ("video", messages.ACT_VIDEO),
                ("problems", messages.ACT_PROBLEMS),
            ],
            "all",
            self._on_filter_changed,
            messages.ACT_SHOW_NAME,
        )
        head.append(title)
        head.append(self.search)
        head.append(self.filter_seg)
        page.append(head)
        page.append(kit.hbox(self._build_now_card(), self._build_queue_card()))
        page.append(self._build_history_card())
        self.append(page)

    def _build_now_card(self):
        self.now_card = kit.Card(messages.ACT_NOW)
        self.now_card.set_hexpand(True)  # Now and Up next share the row equally
        self.now_row = Gtk.Box(spacing=12)
        self.now_card.add_row(self.now_row)
        return self.now_card

    def _build_queue_card(self):
        card = kit.Card(messages.ACT_UP_NEXT)
        card.set_hexpand(True)
        head = card.get_first_child()
        self.queue_note = kit.text(messages.ACT_UP_NEXT_NOTE, "lt-caption")
        head.append(self.queue_note)
        self.queue_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_row(self.queue_rows)
        return card

    def _build_history_card(self):
        self.history_card = kit.Card(messages.ACT_HISTORY)
        self.history_card.set_vexpand(True)
        head = self.history_card.get_first_child()
        self.history_note = kit.text(messages.ACT_HISTORY_NOTE, "lt-caption")
        head.append(self.history_note)
        self.history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        # long histories scroll inside the card, so the window stays 800 px tall
        self.history_scroll = Gtk.ScrolledWindow()
        self.history_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.history_scroll.set_child(self.history_box)
        self.history_card.add_row(self.history_scroll, expand=True)
        self.history_empty = kit.EmptyState(
            "clock-counter-clockwise",
            messages.ACT_EMPTY_TITLE,
            messages.ACT_EMPTY_BODY,
            (messages.ACT_GO_TO_DOWNLOAD, lambda: self.window.show_page("download")),
        )
        self.history_card.add_row(self.history_empty)
        footer = Gtk.Box(spacing=8)
        self.history_count = kit.text("", "lt-caption")
        self.history_count.set_hexpand(True)
        footer.append(self.history_count)
        footer.append(self._build_clear_older_menu())
        self.history_card.add_row(footer)
        return self.history_card

    def _build_clear_older_menu(self):
        button = Gtk.MenuButton()
        kit.css(button, "lt-link")
        button.set_label(messages.ACT_CLEAR_OLDER)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(rows, f"set_margin_{edge}")(12)
        popover = Gtk.Popover()
        for days in (30, 90, 365):
            choice = kit.button(
                messages.ACT_CLEAR_DAYS.format(d=days),
                on_click=lambda days=days, p=popover: (p.popdown(), self._confirm_clear(days)),
            )
            choice.set_hexpand(True)
            rows.append(choice)
        popover.set_child(rows)
        button.set_popover(popover)
        return button

    # ================================================================ Now + queue
    def on_snapshot(self, snap):
        self.refresh_now(snap)
        self.refresh_queue(snap)

    def refresh_now(self, snap):
        _clear_box(self.now_row)
        status = snap.get("status")
        if status not in ACTIVE_STATUSES:
            self.now_row.append(kit.text(messages.ACT_NOW_EMPTY, "lt-muted"))
            self._sync_poller()
            return
        icon = "film-strip" if self._is_video(snap) else "music-notes"
        self.now_row.append(_tinted_tile(icon, "done"))
        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        block.set_hexpand(True)
        block.set_valign(Gtk.Align.CENTER)  # one centred line: tile, text, button
        top = Gtk.Box(spacing=8)
        title = kit.text(snap.get("playlist_title") or snap.get("current_file") or "", "lt-strong")
        title.set_hexpand(True)
        title.set_ellipsize(3)
        eta = fmt_eta_left(snap.get("eta"))
        counts = (
            messages.ACT_NOW_COUNTS.format(
                done=snap.get("completed_files") or 0, total=snap.get("total_files") or 0, eta=eta
            )
            if eta
            else messages.ACT_NOW_COUNTS_NO_ETA.format(
                done=snap.get("completed_files") or 0, total=snap.get("total_files") or 0
            )
        )
        top.append(title)
        top.append(kit.text(counts, "lt-muted"))
        bar = Gtk.ProgressBar()
        bar.set_hexpand(True)
        fraction = (snap.get("total_progress") or 0) / 100
        bar.set_fraction(max(0.0, min(1.0, fraction)))
        kind = messages.ACT_KIND_PLAYLIST if snap.get("is_playlist") else messages.ACT_KIND_SINGLE
        block.append(top)
        block.append(bar)
        block.append(kit.text(self._now_caption(snap, kind), "lt-caption"))
        self.now_row.append(block)
        cancel = kit.button(messages.ACT_CANCEL, on_click=self._cancel_now, small=True)
        cancel.set_valign(Gtk.Align.CENTER)
        self.now_row.append(cancel)
        self._sync_poller()

    def _is_video(self, snap):
        """The snapshot carries no format; the active queue job does"""
        try:
            for job in jobs.queue_snapshot():
                if job.get("status") == "active" and job.get("id") == snap.get("job_id"):
                    return job.get("download_type") == "video"
        except Exception:
            logger.debug("queue snapshot unavailable while painting the Now card")
        return False

    def _now_caption(self, snap, kind):
        folder = tilde(snap.get("output_path") or "")
        fmt = messages.FORMAT_SUMMARY_VIDEO if self._is_video(snap) else messages.FORMAT_SUMMARY_AUDIO
        words = f"{kind} · {fmt}"
        return f"{words} · {folder}" if folder else words

    def _cancel_now(self):
        try:
            jobs.cancel_active_download()
        except Exception:
            logger.exception("cancelling from Activity failed")
        self.refresh_now(snapshot_copy())

    def refresh_queue(self, snap=None):
        _clear_box(self.queue_rows)
        try:
            queued = [job for job in jobs.queue_snapshot() if job.get("status") == "queued"]
        except Exception:
            logger.exception("reading the queue failed")
            queued = []
        if not queued:
            self.queue_rows.append(kit.text(messages.ACT_UP_NEXT_EMPTY, "lt-muted"))
            return
        for job in queued:
            self.queue_rows.append(self._queue_row(job))

    def _queue_row(self, job):
        row = Gtk.Box(spacing=12)
        icon = "film-strip" if job.get("download_type") == "video" else "music-notes"
        row.append(_tinted_tile(icon, "not_downloaded"))
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        words.set_hexpand(True)
        words.set_valign(Gtk.Align.CENTER)
        title = kit.text(job.get("title") or job.get("url") or "", "lt-strong")
        title.set_ellipsize(3)
        words.append(title)
        kind = (
            messages.ACT_KIND_SINGLE if job.get("playlist_mode") == "single" else messages.ACT_KIND_PLAYLIST
        )
        fmt = (
            messages.FORMAT_SUMMARY_VIDEO
            if job.get("download_type") == "video"
            else messages.FORMAT_SUMMARY_AUDIO
        )
        words.append(kit.text(f"{kind} · {fmt}", "lt-caption"))
        row.append(words)
        pill = kit.pill(messages.PILL_WAITING)
        pill.set_valign(Gtk.Align.CENTER)
        row.append(pill)
        spoken = messages.ACT_REMOVE_FROM_QUEUE.format(title=title.get_text())
        remove = kit.icon_button("x", spoken, on_click=lambda *_, j=job: self._remove_queued(j))
        row.append(remove)
        return row

    def _remove_queued(self, job):
        try:
            jobs.remove_queued(job.get("id"))
        except Exception:
            logger.exception("removing a queued job failed")
        self.refresh_queue()
        self.window.rail.set_badge("activity", self._queued_count() or None)

    @staticmethod
    def _queued_count():
        try:
            return sum(1 for j in jobs.queue_snapshot() if j.get("status") == "queued")
        except Exception:
            return 0

    def _sync_poller(self):
        """Poll while the page is visible AND something is running or waiting"""
        try:
            snap = snapshot_copy()
        except Exception:
            logger.exception("status snapshot failed")
            return
        busy = snap.get("status") in ACTIVE_STATUSES or snap.get("queue_pending")
        if self.get_mapped() and busy:
            self.poller.start()
        elif not busy:
            self.poller.stop()

    # ================================================================ History
    def _on_search_changed(self, entry):
        self.query = entry.get_text()
        self.refresh_history()

    def _on_filter_changed(self, value):
        self.kind_filter = value
        self.refresh_history()

    def refresh_history(self):
        _clear_box(self.history_box)
        entries = [
            entry
            for entry in history.merged_entries()
            if history.matches(entry, self.query, self.kind_filter)
        ]
        self.history_empty.set_visible(not entries and not self.query and self.kind_filter == "all")
        self.history_box.set_visible(bool(entries))
        for label, group in history.group_by_day(entries):
            self.history_box.append(kit.text(label, "lt-caption"))
            for entry in group:
                self.history_box.append(self._history_row(entry))
        total = len(history.merged_entries())
        self.history_count.set_text(
            messages.ACT_ENTRY if total == 1 else messages.ACT_ENTRIES.format(n=total)
        )

    def _history_row(self, entry):
        row = Gtk.Box(spacing=12)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        icon = "film-strip" if entry["kind"] == "video" else "music-notes" if entry["url"] else "link"
        row.append(_tinted_tile(icon, entry["result"]))
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        words.set_hexpand(True)
        words.set_valign(Gtk.Align.CENTER)
        title = kit.text(entry["title"], "lt-strong")
        title.set_ellipsize(3)
        words.append(title)
        words.append(kit.text(self._entry_caption(entry), "lt-caption"))
        row.append(words)
        pill = _pill_words(entry["result"])
        pill.set_valign(Gtk.Align.CENTER)
        row.append(pill)
        time_words = entry["when"].strftime("%H:%M") if entry["timestamp"] else ""
        time_label = kit.text(time_words, "lt-muted")
        time_label.set_valign(Gtk.Align.CENTER)
        row.append(time_label)
        action = self._entry_action(entry)
        if action is not None:
            action.set_valign(Gtk.Align.CENTER)
            row.append(action)
        more = self._more_menu(entry)
        more.set_valign(Gtk.Align.CENTER)
        row.append(more)
        return row

    def _entry_caption(self, entry):
        if entry["result"] == "failed":
            return messages.ACT_FAILED_CAPTION
        if entry["result"] == "not_downloaded":
            return messages.ACT_NOT_DOWNLOADED_CAPTION
        kind = messages.ACT_KIND_PLAYLIST if entry["is_playlist"] else messages.ACT_KIND_SINGLE
        folder = tilde(entry["folder"])
        return f"{kind} · {folder}" if folder else kind

    def _entry_action(self, entry):
        if entry["result"] == "done" and entry["folder"]:
            return kit.button(
                messages.ACT_SHOW_FOLDER,
                on_click=lambda *_, e=entry: file_utils.open_folder(e["folder"]),
                small=True,
            )
        if entry["result"] in ("failed", "cancelled", "partial") and entry["url"]:
            return kit.button(
                messages.TRY_AGAIN,
                on_click=lambda *_, e=entry: self._use_link(e["url"]),
                small=True,
            )
        if entry["result"] == "not_downloaded" and entry["url"]:
            return kit.button(
                messages.ACT_USE_THIS_LINK,
                on_click=lambda *_, e=entry: self._use_link(e["url"]),
                small=True,
            )
        return None

    def _use_link(self, url):
        self.window.show_page("download")
        self.window.download_page.use_link(url)

    def _more_menu(self, entry):
        button = Gtk.MenuButton()
        kit.css(button, "lt-icon-btn")
        button.set_child(kit.icon("dots-three", 18))
        spoken = messages.ACT_MORE_FOR.format(title=entry["title"] or entry["url"])
        kit.name(button, spoken)
        button.set_tooltip_text(spoken)
        popover = Gtk.Popover()
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(rows, f"set_margin_{edge}")(12)
        rows.append(
            kit.button(
                messages.ACT_COPY_LINK,
                on_click=lambda *_, e=entry: self._copy_link(e["url"]),
                small=True,
            )
        )
        rows.append(
            kit.button(
                messages.ACT_REMOVE_FROM_HISTORY,
                on_click=lambda *_, e=entry: self._remove_entry(e["id"]),
                small=True,
            )
        )
        popover.set_child(rows)
        button.set_popover(popover)
        return button

    def _copy_link(self, url):
        if url:
            self.get_display().get_clipboard().set(url)

    def _remove_entry(self, entry_id):
        history.remove_entry(entry_id)
        self.refresh_history()

    def _confirm_clear(self, days):
        count = history.count_older_than(days)
        if not count:
            return
        kit.confirm(
            self.window,
            messages.ACT_CLEAR_TITLE.format(n=count, d=days),
            messages.ACT_CLEAR_BODY,
            messages.ACT_CLEAR_GO.format(n=count),
            destructive=True,
            cancel_label=messages.ACT_CLEAR_KEEP,
            on_answer=lambda yes: self._clear_older(days) if yes else None,
        )

    def _clear_older(self, days):
        removed = history.clear_older_than(days)
        logger.info("cleared %d history entries older than %d days", removed, days)
        self.refresh_history()
