# Decisions

### 2026-10-19: Panel icon over raw StatusNotifierItem D-Bus; close hides only while busy
- Reason: The user wants the app in the panel so it can be put away while music downloads. GTK 4 has no tray API;
  XApp.StatusIcon and AyatanaAppIndicator are GTK 3 libraries and cannot load in a GTK 4 process.
- Decision: ui/tray.py implements org.kde.StatusNotifierItem + com.canonical.dbusmenu with Gio (Cinnamon's
  xapp-sn-watcher, KDE, GNOME + AppIndicator extension). The icon is always there while the app runs; clicking it
  hides/shows the window. Closing the window hides it only while a download runs or waits (one notification says
  so); idle, closing quits as before, and Quit (menu, Ctrl+Q) always quits. Without a panel nothing changes.
- Impact: ui/tray.py, ui/app.py, ui/window.py.

### 2026-10-19: Several links in one paste are queued at once
- Reason: The user wants to paste different links for continuous downloading.
- Decision: Two or more links in any link field are all submitted with the current choices (no preview); a playlist
  page (…/playlist?list=) downloads whole, any other link as one video. One link is still read and previewed first.
- Impact: modules/download/links.py, ui/pages/download.py.

### 2026-10-19: Renaming lives on its own File Control page
- Reason: The user asked for a "File Control" page holding all file-renaming capabilities, moved out of the Library.
  The Tidy-names popover could only show one before/after pair; the word lists sat in Settings, away from the
  operations that use them.
- Decision: New rail page after Library: target (one playlist / all files), playlist rename, Tidy-names operations,
  full preview list, Undo/Redo/Apply in a fixed action bar, filler words and replacements. The Library keeps playing,
  trash, number colour, and gains search, a Show filter and tick-to-delete (to each playlist's trash, after a confirm
  that lists the files); its "Rename files" opens File Control on that playlist. Nothing renames without Apply.
- Impact: ui/pages/file_control.py, ui/pages/library.py, ui/pages/settings.py, ui/window.py.

### 2026-10-19: The window never widens itself
- Reason: The user: the app was "too wide and fixed" and widened "automatically as the data is downloaded".
- Decision: Opens at 1040×720. Every label holding data (titles, paths, captions) ellipsizes or wraps; button rows
  wrap; both halves of two-pane pages fit 960 px so the user can drag into single-column mode. Minimums are
  measured, not guessed (wide 933 px, single-column 795 px on 2026-10-19).
- Impact: see changes/2026-10-19_width-file-control-library-tools.md.

### 2026-10-19: Playlist numbers are plain coloured numbers, 1–99999
- Reason: User: remove the numbered badge, keep the number larger, limit the count to 99999.
- Decision: The number in the playlist's colour (20 px, 30 px in the header), no badge; order % 100000.
- Impact: ui/pages/library.py, modules/playlists.py (SEQ_WRAP), ui/style.py.

### 2026-10-18: Installers ship Deno from PyPI as yt-dlp's JS runtime
- Reason: YouTube downloads need a JS runtime for yt-dlp's challenge solver. yt-dlp needs node ≥ 22 or
  deno ≥ 2.3; Mint 22's apt nodejs is 18 (refused), and this machine only worked through an nvm node.
- Decision: requirements.txt adds `deno>=2.3` (the official PyPI wheel, a binary in venv/bin), so every
  install method gets a supported runtime without apt or a curl|sh step. access.find_js_runtime checks the
  venv first and skips node < 22. The app's code goes to ~/.local/opt/linmediadownloader (one command) or
  /opt/linmediadownloader (.deb), never the data folder, so uninstalling can never delete user data.
- Impact: requirements.txt, install.sh, clone-and-install.sh, packaging/build-deb.sh, modules/download/access.py.

### 2026-10-18: Pills carry no checkmark
- Reason: The user found the check icon in Done/Ready pills redundant ("the green pill and text label
  is enough") and asked for it gone from every pill.
- Decision: Success pills (Done, Ready) show colour + word only. Busy, attention and error pills keep
  their icon (spinner, clock, warning), so state is still not colour-only where it matters. Plain status
  lines outside pills keep their icon.
- Impact: ui/widgets/track_list.py, ui/pages/activity.py, ui/window.py; tests/test_ui_icons.py guards it.

### 2026-10-18: 2.0 is a native GTK 4 rewrite, in this repository
- Reason: The Flask + PyWebView UI breaks the Lin* stack (web view, CDN-loaded Bootstrap,
  10 pages) and caused the 2026-08-04 blank-window incident. A new repo would repeat the
  two-repo drift fixed on 2026-08-05 and strand every install.sh / .deb user.
- Decision: Rewrite the UI in Python + GTK 4.14 (no libadwaita) with vendored `lintheme`
  (Graphite Night), following linapptemplate's GUI Guide and the universal instruction set.
  Same repo: 1.x frozen as tag `v1.0.0` + branch `release/1.x`; work on `feat/2.0-gtk4`,
  merged when the user is satisfied; released as 2.0.0. Approved by the user with all eight
  recommendations in docs/design/GTK4-UPGRADE-PLAN.md section 5:
  1. network only through yt-dlp to pasted links ("local only" = local dependencies; online
     data sources are fine), 2. yt-dlp in the app venv, updated only on the user's click,
  3. build `lintheme/gtk4` here and offer it upstream, 4. status chip = tools + site
  reachability, 5. playlist badge colours limited to token colours, 6. drop browser mode and
  the Flask API, 7. name "LinMediaDownloader", 8. version 2.0.0.
- Impact: whole UI layer; packaging; docs. Plan + mockups in docs/design/.

### 2026-10-18: All user data lives in one XDG data folder
- Reason: 1.x resolved data/, logs/, downloads/, backups/ against the working directory, so
  menu and terminal launches kept separate histories, `install.sh --uninstall` (rm -rf of the
  install dir) deleted user data with the code, and the test suite wrote fake links into
  whatever folder pytest ran from.
- Decision: `modules/config/paths.py` owns every path: `~/.local/share/linmediadownloader`
  (`$XDG_DATA_HOME`, `LMD_DATA_DIR` override). First start copies (never moves) the newest
  1.x copy of each data file, skips corrupt JSON, never overwrites, writes a marker and runs
  once. Old ./downloads folders stay scanned by the playlist code. Tests set LMD_DATA_DIR to a
  temp dir in tests/conftest.py.
- Impact: settings.py, user_settings.py, logging_config.py, dedupe.py, playlists.py, browser_app.py.

### 2026-10-18: Download commands live in modules/download/jobs.py, not in Flask routes
- Reason: `routes/api.py` held business logic (option validation, link history, queue
  position, the cancel-and-record-partial step), which a GTK front end could not reuse.
- Decision: `jobs.submit_download / cancel_active_download / status_snapshot /
  queue_snapshot / clear_finished_jobs / normalize_options`; routes only translate HTTP.
- Impact: modules/download/jobs.py (new), modules/routes/api.py.

### 2026-10-18: App id org.mensuramedia.LinMediaDownloader names the window, icon and menu entry
- Reason: The user asked for a proper icon in the panel, Alt+Tab and the program menu. Cinnamon
  matches a window to its menu entry by WM_CLASS (StartupWMClass) or the GTK application id, and
  takes the icon from that entry or the window's own icon.
- Decision: One id everywhere: Gtk.Application id, GLib prgname (so WM_CLASS is the id), the
  .desktop file name, Icon= and StartupWMClass=, and the hicolor icon name. The icon follows the
  Lin* family (tile + bold Phosphor glyph + badge); the 1.x Heroicons icon (a foreign icon set) is
  not used by 2.0 (packaging/build-deb.sh still references it until Phase 6).
- Impact: resources/icons/hicolor/**, ui/app.py, linmediadownloader.py, packaging/install-menu.sh.

### 2026-10-18: Focus ring in the accent blue; status pill shows one word
- Reason: The user saw yellow borders on fields and buttons (the kit's focus colour #ffd75e, which
  GTK 4 shows on a focused entry even after a mouse click) and asked for no yellow borders; and
  asked for the header pill to read only "Ready" / "Downloading".
- Decision: The app's vendored tokens set focus = accent #4c9dff (contrast still ≥ 3:1 on bg and
  surface; an app-level departure from the kit's guide, recorded in lintheme/VENDORED.md). The pill
  shows the first word of each status sentence; the sentence stays as tooltip and accessible name.
- Impact: lintheme/tokens.py (app copy only), ui/window.py, ui/messages.py.

### 2026-10-18: A track is "done" only after yt-dlp's last post-processing step
- Reason: The user saw a track reported downloaded while its .webm was still there (conversion to
  MP3 and the source's deletion run after yt-dlp's download 'finished').
- Decision: DownloadProgress counts a file and marks it done in a postprocessor hook on
  'MoveFiles' (MoveFilesAfterDownloadPP), which yt-dlp runs last for every file after conversion,
  merging and deletion; in between the track is 'processing' ("Converting"). Also fixes 1.x
  counting a video+audio pair as two files. Verified on a real download.
- Impact: modules/download/media.py, ui/widgets/track_list.py, ui/pages/download.py, tests.

### 2026-10-18: YouTube access uses the user's own browser sign-in, found automatically
- Reason: YouTube answers this machine's NordVPN exit IP with "Sign in to confirm you're not a
  bot"; the 1.x android-client retry was refused too (seen in the first real 2.0 test). The
  2026-10-14 Brave investigation (mint-optimization/brave-video-decode.md) showed a signed-in
  profile gets through. The user asked for no manual step: detect browsers, see which is active,
  check for cookies and route the app accordingly.
- Decision: `modules/download/access.py` scans every Firefox-family (incl. LibreWolf, Flatpak/Snap)
  and Chromium-family profile, reads only cookie names and timestamps (never values) to find a
  current YouTube sign-in, prefers running browsers, then the most recent YouTube use, and gives
  yt-dlp `cookiesfrombrowser` (LibreWolf via the firefox reader with a profile path) plus a local
  JS runtime (`js_runtimes`; deno/node/bun/quickjs incl. nvm). The challenge solver comes from the
  local `yt-dlp-ejs` package (`yt-dlp[default]`), never `--remote-components` at run time.
  LMD_BROWSER_ACCESS=off disables it (a Settings switch comes in Phase 5); tests set it off.
- Verified 2026-10-18 on this machine: LibreWolf chosen over Brave and Firefox; "Me at the zoo"
  downloaded through the VPN as MP3 with status completed and no errors.
- Impact: modules/download/{access,preview,media,jobs}.py, requirements.txt, ui (sign-in note).

### 2026-10-18: lintheme 1.5.0 vendored, with a GTK 4 port built here
- Reason: The kit shipped GTK 3 components only; decision 3 of the 2.0 plan says build
  `lintheme/gtk4` here and offer it upstream.
- Decision: GLM drafted `lintheme/gtk4` in a local linapptemplate branch
  (`feat/gtk4-components`, commit 793f9d5, kit 1.5.0); Claude reviewed it on a real display and
  fixed five defects GLM could not see without one (icon pixel size, icon centring, short hints
  wrapping, layout mode stuck on "compact" after maximize, gallery window not attached to its
  app). The app vendors that kit without `gtk3/` (GTK 4 only); `lintheme/VENDORED.md` records the
  source. App-only icons stay in `resources/icons/phosphor/regular/` via `icons.add_icon_dir`.
  Known gap, both toolkits: the dropdown arrow is the system theme's, not a Phosphor caret.
  Upstreaming the branch to linapptemplate needs the user's go-ahead (push to another repo).
- Impact: lintheme/**, ui/icons.py, resources/icons/**, examples/gallery_gtk4.py, tests/test_kit_*.py.

### 2026-10-18: AppDir/ is not hand-synced on the 2.0 branch
- Reason: The 2026-07-31 sync rule exists only because AppDir/ is a committed copy; Phase 6
  replaces it with a build-from-source step, and syncing a half-ported tree has no user.
- Decision: On `feat/2.0-gtk4`, leave AppDir/ untouched until Phase 6 rebuilds it. The
  2026-07-31 rule still applies to `release/1.x`.
- Impact: AppDir/** (unchanged until Phase 6).

### 2026-08-05: MensuraMedia is the single canonical repository
- Reason: The project existed as two divergent GitHub repos with unrelated histories —
  `mikesdatawork/linux-media-downloader` (had a logging framework + the launch fix) and
  `MensuraMedia/linux-media-downloader` (feature-complete superset: job queue, playlists,
  chapters, dedupe, settings; the repo actually installed/published). Maintaining both
  caused drift and confusion about which version users ran.
- Decision: Consolidate onto **MensuraMedia** as canonical (it is the superset, is public,
  and is the tree the installer/menu launches). Ported the only unique assets from the
  mikesdatawork tree — the centralized logging framework and the launch-failure postmortem.
  Repointed the local dev checkout (`~/projects/linux_media_downloader`) to this remote.
  The mikesdatawork repo is read-only from here (pull-only access) and must be retired
  manually by its owner (archive + redirect notice).
- Impact: `modules/config/logging_config.py` (new), logging wiring across entrypoints/modules,
  `docs/troubleshooting/`, `install.sh`, `app.py`. Backups of the old tree: a full git
  bundle + an on-disk archive copy alongside the project.

### 2026-08-05: venv must use --system-site-packages for the PyWebView GUI backend
- Reason: The installed app showed a menu icon but no window. The installer built its venv
  without `--system-site-packages`; PyWebView's GTK backend needs system `PyGObject` (`gi`)
  + WebKit2GTK (apt-only, not pip-installable in an isolated venv), so `webview.start()`
  raised `WebViewException` and the process died in <1s. `Terminal=false` hid the traceback.
- Decision: Create the venv with `--system-site-packages` and verify the backend at install
  time; keep `WEBKIT_DISABLE_DMABUF_RENDERER=1` in `app.py` as defense-in-depth. venv and
  system Python are the same build, so exposing system packages is ABI-safe.
- Impact: `install.sh`, `app.py`. Full postmortem in `docs/troubleshooting/`.

### 2026-07-31: Route cancellation through accessor functions in settings.py
- Reason: `cancel_requested` was a module-level bool imported *by value* into both
  `media.py` and `api.py` (`from settings import cancel_requested`). Reassigning it in
  `api.py` rebound only `api.py`'s copy, so the download worker in `media.py` never saw
  the change — cancellation was silently a no-op across module boundaries.
- Decision: Keep the flag private to `settings.py` and expose `request_cancel()`,
  `reset_cancel()`, `is_cancel_requested()`. All modules call these, giving one source of
  truth. Mutable shared state (`current_download` dict, `download_history` list) can still
  be imported by reference because mutation-in-place is visible everywhere.
- Impact: `modules/config/settings.py`, `modules/download/media.py`, `modules/routes/api.py`.

### 2026-07-31: Raise DownloadCancelled from the progress hook instead of returning
- Reason: Returning from a `yt-dlp` progress hook does not abort the download; yt-dlp keeps
  going. The documented way to abort cleanly is to raise `yt_dlp.utils.DownloadCancelled`.
- Decision: The hook raises it on cancel; `download_media` catches it, marks the status
  `cancelled`, and skips the alternative-method retry (which would otherwise re-download).
- Impact: `modules/download/media.py`.

### 2026-07-31: Secret key is environment-overridable with a random fallback
- Reason: `SECRET_KEY` was hardcoded to `'ytmediabackup'`. The app is localhost-only so
  risk is low, but a committed secret is poor hygiene.
- Decision: `SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()`.
- Impact: `modules/config/settings.py`. No functional change (app does not rely on
  persistent server-side sessions).

### 2026-07-31: Keep AppDir/usr/bin/ in sync with top-level sources
- Reason: `AppDir/` is a committed full copy used for AppImage packaging. It held stale,
  buggy code and its own `.error` files, so a built AppImage would ship the old behavior.
- Decision: Sync changed runtime files into `AppDir/usr/bin/` on every runtime change until
  packaging is reworked to copy from source at build time (a future improvement).
- Impact: `AppDir/usr/bin/**`.
