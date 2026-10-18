# ui/widgets/track_list.py
"""The track rows the preview and the progress views share: number, title, a
status pill (icon + word), length. Built on Gtk.ListView + Gio.ListStore +
Gtk.SignalListItemFactory so a 500-item playlist stays fast: rows are recycled
and a poll only touches the items whose status changed.

Row states (TrackItem.state): pending · skip_duplicate · skip_long · waiting ·
downloading · done · not_downloaded. Dimmed rows are the skipped ones.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject, Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk4 import components as kit  # noqa: E402
from ui import messages  # noqa: E402

C = tokens.COLOR
PILL_WIDE = 190
COMPACT_HEIGHT = 420

# state -> (icon, message template, pill kind, dim)
PREVIEW_PILLS = {
    "skip_duplicate": ("copy", messages.PILL_HAVE, None, True),
    "skip_long": ("clock-counter-clockwise", messages.PILL_LONG, "attention", True),
}
ACTIVE_PILLS = {
    "done": ("check-circle", messages.PILL_DONE, "ok", False),
    "downloading": ("circle-notch", messages.PILL_DOWNLOADING, "busy", False),
    "skip_duplicate": ("copy", messages.PILL_SKIP_HAVE, None, True),
    "skip_long": ("clock-counter-clockwise", messages.PILL_SKIP_LONG, "attention", True),
    "not_downloaded": (None, messages.PILL_NOT_DOWNLOADED, "error", False),
    "waiting": (None, messages.PILL_WAITING, None, False),
}
_COUNTED = ("done", "downloading", "waiting")


class TrackItem(GObject.Object):
    """One row's display fields; assigning a property notifies bound rows only when changed."""

    number = GObject.Property(type=int, default=0)
    title = GObject.Property(type=str, default="")
    length = GObject.Property(type=str, default="")
    state = GObject.Property(type=str, default="pending")
    progress = GObject.Property(type=float, default=-1.0)

    def set_fields(self, **fields):
        for key, value in fields.items():
            if getattr(self, key) != value:
                setattr(self, key, value)


class TrackRow(Gtk.Box):
    """One recycled row; bind(item) wires it to a TrackItem's properties."""

    def __init__(self):
        super().__init__(spacing=12)
        kit.css(self, "lt-row")
        self._item, self._handlers, self._shown_pct = None, [], None
        self.number = Gtk.Label(xalign=1.0)
        self.number.set_width_chars(2)
        self.number.set_valign(Gtk.Align.CENTER)  # number, title block, pill and length
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)  # share one centre
        title_box.set_valign(Gtk.Align.CENTER)
        self.title = Gtk.Label(xalign=0.0)
        self.title.set_ellipsize(3)  # end: long titles shorten, the length column stays put
        self.title.set_hexpand(True)
        self.bar = Gtk.ProgressBar()
        self.bar.set_hexpand(False)
        self.bar.set_size_request(180, -1)
        kit.name(self.bar, "Track progress")
        title_box.append(self.title)
        title_box.append(self.bar)
        self.pill_box = Gtk.Box(spacing=8)
        self.pill_box.set_size_request(PILL_WIDE, -1)
        self.pill_box.set_halign(Gtk.Align.END)
        self.pill_box.set_valign(Gtk.Align.CENTER)
        self.length = Gtk.Label(xalign=1.0)
        self.length.set_width_chars(6)
        self.length.set_valign(Gtk.Align.CENTER)
        self.append(self.number)
        self.append(title_box)
        self.append(self.pill_box)
        self.append(self.length)
        self.show_state("pending", None)

    def bind(self, item):
        self.unbind()
        self._item = item
        for prop, cb in (
            ("number", self._sync_number),
            ("title", self._sync_title),
            ("length", self._sync_length),
            ("state", self._sync_state),
            ("progress", self._sync_progress),
        ):
            self._handlers.append(item.connect(f"notify::{prop}", cb))
        self._sync_number()
        self._sync_title()
        self._sync_length()
        self._sync_state()
        self._sync_progress()

    def unbind(self):
        for handler in self._handlers:
            self._item.disconnect(handler)
        self._handlers, self._item = [], None

    # -- property callbacks
    def _sync_number(self, *_a):
        self.number.set_text(str(self._item.number) if self._item else "")

    def _sync_title(self, *_a):
        self.title.set_text(self._item.title if self._item else "")

    def _sync_length(self, *_a):
        self.length.set_text(self._item.length if self._item else "")

    def _sync_state(self, *_a):
        if self._item:
            self.show_state(self._item.state, self._item)

    def _sync_progress(self, *_a):
        if not self._item:
            return
        fraction = self._item.progress
        downloading = self._item.state == "downloading" and fraction is not None and fraction >= 0
        self.bar.set_visible(downloading)
        if downloading:
            self.bar.set_fraction(max(0.0, min(1.0, fraction)))
            pct = int(fraction * 100)
            if pct != self._shown_pct:  # keep the pill's percent words moving with the bar
                self._shown_pct = pct
                icon_name, template, kind, _dim = ACTIVE_PILLS["downloading"]
                self._rebuild_pill(icon_name, template, kind, self._item)

    # -- one row's look for a state
    def show_state(self, state, item):
        icon_name, template, kind, dim = ACTIVE_PILLS.get(
            state, PREVIEW_PILLS.get(state, (None, "", None, False))
        )
        kit.uncss(self, "lmd-dim")
        if dim:
            kit.css(self, "lmd-dim")
        self._rebuild_pill(icon_name, template, kind, item)
        self._shown_pct = int((item.progress or 0) * 100) if item and state == "downloading" else None
        self._sync_progress()

    def _rebuild_pill(self, icon_name, template, kind, item):
        pill_words = template.format(p=int((item.progress or 0) * 100)) if item else template
        child = self.pill_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.pill_box.remove(child)
            child = nxt
        if pill_words:
            pill = kit.css(Gtk.Box(spacing=6), "lt-pill", f"lt-{kind}" if kind else None)
            if icon_name:
                colour = {
                    "ok": C["ok"],
                    "busy": C["busy"],
                    "attention": C["attention"],
                    "error": C["error"],
                }.get(kind)
                pill.append(kit.icon(icon_name, 14, colour))
            pill.append(Gtk.Label(label=pill_words))
            pill.set_valign(Gtk.Align.CENTER)
            self.pill_box.append(pill)


class TrackList(Gtk.Box):
    """The bordered list: a column-header row and the recycling ListView below it."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        kit.css(self, "lt-card", "lmd-list")
        head = Gtk.Box(spacing=12)
        kit.css(head, "lt-thead")
        num = Gtk.Label(label=messages.COL_NUM, xalign=1.0)
        num.set_width_chars(2)
        title = Gtk.Label(label=messages.COL_TITLE, xalign=0.0)
        title.set_hexpand(True)
        status = Gtk.Label(label=messages.COL_STATUS)
        status_box = Gtk.Box()
        status_box.set_size_request(PILL_WIDE, -1)
        status_box.set_halign(Gtk.Align.END)
        status_box.append(status)
        length = Gtk.Label(label=messages.COL_LENGTH, xalign=1.0)
        length.set_width_chars(6)
        for widget in (num, title, status_box, length):
            head.append(widget)
        self.append(head)

        self.store = Gio.ListStore.new(TrackItem)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        factory.connect("unbind", self._unbind)
        self.view = Gtk.ListView(model=Gtk.NoSelection(model=self.store), factory=factory)
        self.view.set_hexpand(True)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_child(self.view)
        self.scroll.set_vexpand(True)
        self.scroll.set_min_content_height(120)
        self.append(self.scroll)
        self._keys = []
        kit.name(self.view, messages.TRACKS)

    # -- factory
    def _setup(self, _factory, item):
        item.set_child(TrackRow())

    def _bind(self, _factory, item):
        item.get_child().bind(item.get_item())

    def _unbind(self, _factory, item):
        item.get_child().unbind()

    # -- content
    def set_entries(self, entries):
        """Show a preview's entries (pill = why it would be skipped, else nothing yet)."""
        self.store.remove_all()
        self._keys = []
        for entry in entries or []:
            item = TrackItem()
            item.set_fields(
                number=entry.get("index") or len(self._keys) + 1,
                title=entry.get("title") or "",
                length=clock(entry.get("duration")),
                state=(
                    "skip_duplicate"
                    if entry.get("skip") == "duplicate"
                    else "skip_long" if entry.get("skip") == "long" else "pending"
                ),
                progress=-1.0,
            )
            self.store.append(item)
            self._keys.append(entry.get("id") or entry.get("title") or "")

    def set_raw(self, rows):
        """Rows straight from a snapshot's per-track states (no preview to match against)."""
        self.store.remove_all()
        self._keys = []
        for i, (key, track) in enumerate(rows, 1):
            item = TrackItem()
            state = track.get("state") or "waiting"
            item.set_fields(
                number=i,
                title=track.get("title") or key,
                state=state if state in ACTIVE_PILLS else "waiting",
                progress=(track.get("progress") or 0) / 100 if state == "downloading" else -1.0,
            )
            self.store.append(item)
            self._keys.append(key)

    def apply_states(self, states, final=False):
        """Merge per-track states (keyed by video id, else title) into the shown rows."""
        for i in range(self.store.get_n_items()):
            item = self.store.get_item(i)
            key = self._keys[i] if i < len(self._keys) else ""
            track = (states or {}).get(key)
            state = (track or {}).get("state")
            if state == "downloading":
                item.set_fields(
                    state="downloading",
                    progress=((track.get("progress") or 0) / 100),
                )
            elif state in ("done", "skipped_long", "skipped_duplicate"):
                mapped = {"skipped_long": "skip_long", "skipped_duplicate": "skip_duplicate"}
                item.set_fields(state=state if state == "done" else mapped[state], progress=100.0)
            elif final:
                item.set_fields(state="not_downloaded", progress=-1.0)
            elif item.state in ("pending",):
                item.set_fields(state="waiting", progress=-1.0)
            elif item.state == "downloading":
                item.set_fields(state="waiting", progress=-1.0)
        return self.counts()

    def counts(self):
        """How many rows sit in each state, for the pane's headline counts."""
        found = {"done": 0, "downloading": 0, "waiting": 0, "skip": 0, "not_downloaded": 0, "pending": 0}
        for i in range(self.store.get_n_items()):
            state = self.store.get_item(i).state
            if state in _COUNTED:
                found[state] += 1
            elif state in ("skip_long", "skip_duplicate"):
                found["skip"] += 1
            else:
                found["pending"] += 1
        return found

    def set_compact(self, compact):
        """Narrow window: a fixed height, so the list scrolls inside the one column."""
        if compact:
            self.scroll.set_size_request(-1, COMPACT_HEIGHT)
        else:
            self.scroll.set_size_request(-1, -1)


def clock(seconds):
    """3:42 / 1:02:03; blank when the length is unknown"""
    if seconds is None:
        return ""
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
