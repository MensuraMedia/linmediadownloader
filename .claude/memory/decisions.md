# Decisions

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
