# GTK 4 upgrade plan

Status: **approved 2026-10-18**, in progress on `feat/2.0-gtk4` (1.x frozen as tag `v1.0.0`,
fixes on `release/1.x`). Phases 0–2 done; see the table in section 6.

This plan moves Linux Media Downloader from a Flask + PyWebView web UI to a native
**Python 3 + GTK 4** app styled with the Lin* kit (`lintheme`, theme **Graphite Night**).
It follows the two standards this project must keep:

- [LinAppTemplate GUI Guide and Design Reference](https://github.com/MensuraMedia/linapptemplate/blob/main/docs/design/GUI-GUIDE-AND-DESIGN-REFERENCE.md)
  and the rules distilled from it (`docs/05-UX.md` in that repo): four destinations, one main
  action per view, status = icon + word, messages = what · why · next step, WCAG 2.2 AA,
  Phosphor icons only, Ubuntu font, one theme.
- [Universal Instruction Set](https://github.com/MensuraMedia/universal-instruction-set): plan
  first, additive changes to `.claude/`, changelog + change manifest + decision log for every change.

Mockups (9 artboards, Graphite Night, 1200 × 800 like the guide's artboards): see the
**[gallery](mockups-gtk4/README.md)**; source and renders in [`mockups-gtk4/`](mockups-gtk4/),
editable canvas at <https://claude.ai/artifact/Xv1GvXnzBciwh6UqgYwC7w>.

## 1. What the app is today (examined 2026-10-18)

| Area | Today | Problem for a GTK 4 / Lin* app |
|---|---|---|
| UI stack | Flask blueprints + Jinja templates, rendered in PyWebView (WebKit2GTK) or a browser | A web view is exactly what the kit's stack forbids; WebKit2GTK caused the 2026-08-04 blank-window incident |
| Styling | Bootstrap 5.1.3 and Bootstrap Icons loaded **from cdn.jsdelivr.net at runtime** | Breaks offline use; foreign icon set; no tokens |
| Navigation | 10 sidebar items: Home, Pending, Playlists, Player, File Manager, History (`/backups`), Links, Settings, FAQ, About | Guide allows 4 destinations |
| Backend | `modules/download`, `modules/playlists.py`, `modules/config/*`, `modules/utils` | **Flask-free already** (only `modules/routes/*` import Flask), so a GTK front end can call them directly |
| State | Module-level singletons in `settings.py` (`current_download`, `download_queue`, histories); cancel flag via accessors | Works with GTK if the UI polls on the main loop (`GLib.timeout_add`) and never touches widgets from worker threads |
| Paths | `downloads/`, `backups/`, `data/`, `logs/` relative to the **current directory** (pending item since 2026-07-31) | Launching from the menu vs a terminal splits state; fix before the port |
| Local API | Unauthenticated JSON API on `127.0.0.1` (ephemeral port in `app.py`, fixed `:5000` in `browser_app.py`) | Goes away with the port; until then any local process can call it |
| Packaging | `install.sh`, `packaging/build-deb.sh` (version 1.0.0), hand-synced `AppDir/` copy | Dependencies change; `AppDir/` duplication should end |
| Tests | `tests/test_app.py`, 79 offline tests, mostly backend + Flask routes | Backend tests stay; route tests are replaced by widget tests under `xvfb-run` |

Machine checked (Linux Mint 22.3): GTK **4.14.5** (`gir1.2-gtk-4.0`), libadwaita 1.5 (not used),
GStreamer 1.24 base + good plugins. **Missing:** `libgtk-4-media-gstreamer` (needed for
`Gtk.MediaFile` playback). Distro `yt-dlp` is **2024.04.09**, too old for YouTube today;
`ffmpeg` here is a user copy in `~/.local/bin`, not the distro package.

## 2. Information architecture: 10 pages become 4 destinations

| Destination (rail) | Absorbs today's pages | Main action (48 px, bottom right) |
|---|---|---|
| **Download** | Home | Download (`Ctrl+Enter`); Cancel download (`Esc`) while running; Open folder when done |
| **Activity** | Pending (queue), History (`/backups`), Links | none: rows carry their own actions (Show folder, Try again, Use this link) |
| **Library** | Playlists, Player, File Manager ("All files" toggle) | Play / Pause in the player bar |
| **Settings** | Settings, FAQ, About (+ header menu) | none: changes save as they are made |

Every 1.0 function survives; none is removed. The header status chip reports the **tools**
(yt-dlp, ffmpeg) and the **last site reached**: Ready · Busy · Needs you · Can't reach.

## 3. The mockups

| # | Artboard | What it shows | Guide rules it exercises |
|---|---|---|---|
| 1 | Download: ready | Link · Format · Playlist · Save to cards; live preview of the playlist with skipped items marked; summary + Download | ≤ 4 option groups, preview beside options, recognition over recall |
| 2 | Download: in progress | The original progress ring kept (Cairo), current file bar, per-track status pills, queue another link, Cancel as big as Download | Doherty feedback, easy exit, status = icon + word |
| 3 | Download: finished | End moment: "Downloaded 7 tracks · 3 min 41 s", skipped items explained with a way to get them | Peak-end rule, focus moved to the next link |
| 4 | Download: can't reach | YouTube bot check as what · why · next step, details behind "Details", honest uncertainty on the yt-dlp age, Download disabled **with the reason** | Messages pattern, honest uncertainty, disabled says why |
| 5 | Activity | Now · Up next · History (grouped by day), filters, links that were never downloaded | Queue + history merged like LinPrinter's Activity |
| 6 | Library | Playlists with their sequence badges, file table, **Tidy names** popover with a live before/after preview, Undo/Redo, player bar | Recognition over recall, undo instead of confirm |
| 7 | Settings | Downloads defaults, Tidy names words, Tools (yt-dlp, ffmpeg, browser sign-in), Privacy, About | No AI / telemetry statement, About inside Settings |
| 8 | Confirm | Empty trash: title asks, verb buttons, Esc keeps them | Confirm only destructive actions |
| 9 | Narrow window | 720 px: compact rail, one column, preview collapsed to a strip | Reflow at 720 px |

## 4. Target architecture

```
linmediadownloader/
├── lintheme/                  # vendored from linapptemplate (copy, don't reference)
│   ├── tokens.py css.py status.py icons.py apply.py   # unchanged; build_css(4)
│   └── gtk4/                  # NEW: port of lintheme/gtk3 per 02-GTK.md's mapping
├── modules/                   # existing backend, kept
│   ├── config/ download/ playlists.py utils/
│   └── routes/                # retired after the port (Flask removed)
├── ui/                        # NEW
│   ├── app.py                 # Gtk.Application, single instance, actions + shortcuts
│   ├── window.py              # shell: HeaderBar, status chip, NavRail, Gtk.Stack
│   ├── poller.py              # GLib.timeout_add(250) snapshot of current_download / queue
│   ├── pages/download.py activity.py library.py settings.py
│   └── widgets/ring.py track_row.py tidy_popover.py player_bar.py
├── resources/icons/phosphor/regular/   # only the icons used, + LICENSE-phosphor
└── linmediadownloader.py      # entry point (replaces app.py / browser_app.py)
```

GTK 4 building blocks (no libadwaita, per the kit's decision):

| Mockup part | GTK 4.14 |
|---|---|
| Header, chip, menu | `Gtk.HeaderBar` via `set_titlebar`, chip = `Gtk.Button`, `Gtk.MenuButton` + `Gio.Menu` |
| Rail with badge | `Gtk.Box` of buttons, `Gtk.Overlay` + `Gtk.Label.lt-badge` |
| Pages | `Gtk.Stack` (crossfade 200 ms; 0 when `gtk-enable-animations` is off) |
| Segmented choices | separate `Gtk.ToggleButton`s joined with `set_group`, 8 px apart |
| Switch rows | `Gtk.Switch` with an accessible label |
| Track / history lists | `Gtk.ListView` + `Gio.ListStore` + `Gtk.SignalListItemFactory` (scales to long playlists) |
| Library file table | `Gtk.ColumnView` with sorters (Name, Length, Size) |
| Progress ring | `Gtk.DrawingArea.set_draw_func` + Cairo |
| Bars, scales | `Gtk.ProgressBar`, `Gtk.Scale` |
| Tidy names | `Gtk.Popover` anchored to its button |
| Player | `Gtk.MediaFile` (+ `Gtk.Video` for video), needs `libgtk-4-media-gstreamer` |
| Folder choice | `Gtk.FileDialog.select_folder` (async) |
| Confirm | `Gtk.AlertDialog` (async), verbs on buttons, cancel = Esc |
| Shortcuts | `Gtk.ShortcutController`: Alt+1…4 pages, Ctrl+V paste link, Ctrl+Enter download, Esc cancel, Space play/pause, Ctrl+Z / Ctrl+Shift+Z undo/redo |
| Narrow layout | `notify::default-width` (≥ 960 two panes, < 960 one column) |
| Focus ring | GTK 4 `:focus-visible` (keyboard only) from `build_css(4)` |

Threading: downloads keep their worker threads; the UI only reads snapshots on the main loop and
sends commands (enqueue, cancel) through the existing functions. Nothing blocks the main loop.

## 5. Departures from the standards (all approved 2026-10-18)

1. **Network.** Not a departure after all: "local only" means local *dependencies*, and online
   data sources are fine (user, 2026-10-18). Network traffic goes only through yt-dlp, only to
   links the user pastes; Settings says so. Runtime-fetched code (the 1.x CDN Bootstrap) is gone.
2. **Distro packages only.** Distro yt-dlp (2024.04) can't download from YouTube today.
   Proposal: yt-dlp in the app's venv (as today), updated only when the user presses
   "Update yt-dlp" (no silent updates). ffmpeg from the distro package.
3. **First GTK 4 consumer of the kit.** `lintheme` ships GTK 3 components; this app needs
   `lintheme/gtk4`. Proposal: build it here, then offer it back to linapptemplate.
4. **Status chip meaning.** No device here: the chip reports tools + site reachability.
5. **Playlist badge colours** are user-picked today. Proposal: keep the feature, limit the picker
   to the five status/accent token colours so contrast stays tested.
6. **Browser mode** (`browser_app.py`) and the Flask API are dropped.
7. **Name.** Mockups use "LinMediaDownloader" (Lin* family, matches the repo name); README and
   `.deb` say "Linux Media Downloader". Pick one.
8. **Version.** 1.0.0 today; the port would be **2.0.0**.

## 6. Phased plan (branch `feat/2.0-gtk4`, merged only when you are satisfied)

| Phase | Work | Done when |
|---|---|---|
| 0 Prep **(done)** | Fixed app-data dir (`modules/config/paths.py`, copy-only 1.x migration); download/queue/cancel logic moved from `routes/api.py` to `modules/download/jobs.py`; tests isolated from real data | 92 tests pass; no cwd-relative paths |
| 1 Kit **(done)** | `lintheme` 1.5.0 vendored (no gtk3) with the new `lintheme/gtk4` (all gtk3 components + shell, async `confirm`, maximize-safe layout modes), `icons.add_icon_dir`; 17 app icons in `resources/`, registered by `ui/icons.py` | 131 tests pass on a display (22 GTK tests skip cleanly without one); CSS parses in GTK 4 with zero errors |
| 2 Shell + Download **(done)** | `linmediadownloader.py`, `ui/` (app, window, poller, Download page in all states, ring, track list, messages), `modules/download/preview.py`, per-track states; `tools/shot_states.py` renders each state | 165 tests on a display; renders match the mockups; real window opens. Real downloads blocked here by YouTube's bot check (VPN exit IP) until browser sign-in lands |
| 3 Activity | Queue + history + links merged; one history file with a migration | Old history and links appear |
| 4 Library | Playlists, all files, tidy-names popover with preview, undo/redo, trash, player | Every 1.0 operation reachable |
| 5 Settings | Defaults, tidy-name words, tools (version + update), privacy, about, FAQ | Settings persist; no "are you sure" on leave |
| 6 Packaging | `.deb` deps: `python3-gi gir1.2-gtk-4.0 libgtk-4-media-gstreamer gstreamer1.0-plugins-good librsvg2-common fonts-ubuntu ffmpeg`; drop Flask, pywebview, WebKit2GTK; build `AppDir` from source | Clean install on a fresh Mint 22.3 |
| 7 Verify | `xvfb-run -a pytest`, headless screenshots of every state, keyboard-only pass, Orca pass, design review against the guide's §14 checklist | All checklist items pass |

## 7. Risks

- `Gtk.MediaFile` needs `libgtk-4-media-gstreamer`; without it playback silently does nothing.
  The installer must add it and the Library should say so if it's missing.
- GTK 4.14 has no CSS `var()`: colours are substituted from tokens (the kit already does this).
- yt-dlp breaks often against YouTube; the Error state and "Update yt-dlp" are part of the design,
  not an afterthought.
- Long playlists (hundreds of items) need `Gtk.ListView`, not a `Gtk.Box` of rows.
