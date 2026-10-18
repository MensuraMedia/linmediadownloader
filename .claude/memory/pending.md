# Pending / Unresolved Items

Opportunities identified during the 2026-07-31 review but intentionally **not** changed
(to keep the optimization pass low-risk). Revisit when scope allows:

- [x] **cwd-relative paths** (fixed 2026-10-18 on feat/2.0-gtk4: modules/config/paths.py) — `settings.py` builds `HISTORY_FILE`, `downloads/`, and
  `backups/` from `os.getcwd()`. Launching the app from a different directory splits state.
  Anchor these to a fixed app-data dir (e.g. `~/.local/share/linux-media-downloader`).
- [ ] **AppDir duplication** — the packaging staging tree is a committed copy of the whole
  app. Prefer copying from source at build time so it cannot drift. Currently synced by hand.
- [x] **Automated tests (tier 1)** — `tests/test_app.py` now covers `sanitize_filename`,
  the cancel wiring (incl. an end-to-end HTTP cancel), the progress hook, and the `/api/*`
  routes. 15 tests, offline. Still TODO: an integration smoke test that does one real
  yt-dlp download, and wiring `pytest` into the `test-agent` skill + CI.
- [ ] **Playlist-in-single URL parsing** in `media.py` (`get_video_info`) uses fragile
  string splitting on `list=`. Consider `urllib.parse` for robustness.
- [ ] **Blocking `time.sleep(1)`** in `app.py` before opening the window — could poll the
  server's readiness instead.

## 2026-08-02 — Download state memory (needs a planning session)
User reports navigating away from Home and back can still lose the in-progress download view
in some cases (resumeActiveDownload reconnects only for starting/downloading/processing).
Natural companion updates to design together: what to show for a download that FINISHED while
away, persisting the last result across an app restart, and clearing/curating the progress
table on a new download. Treat as a small design pass before implementing. (Input box now
auto-clears on successful completion; that part is done.)

## 2026-10-18 — GTK 4 upgrade (approved; Phases 0–5 done)
Plan + mockups: `docs/design/GTK4-UPGRADE-PLAN.md`, `docs/design/mockups-gtk4/`
(canvas: https://claude.ai/artifact/Xv1GvXnzBciwh6UqgYwC7w). All 8 departures approved (decisions.md).
Work on branch `feat/2.0-gtk4`. Phases 0–5 done (kit 1.5.3). Next: Phase 6 — packaging. Handoff: sessions/2026-10-18_gtk4-phases-0-5-handoff.md
- [ ] Offer linapptemplate branch `feat/gtk4-components` (local clone in a session scratchpad,
  commit 793f9d5) upstream — needs the user's OK; re-create from lintheme/ here if the clone is gone.
- [ ] Kit gap: GtkDropDown arrow comes from the system theme (both toolkits), not a Phosphor caret.
- [x] **Browser sign-in** — done 2026-10-18 (modules/download/access.py, automatic). Settings
  choice of profile done in Phase 5.
- [ ] Installer (Phase 6): install `yt-dlp[default]` (brings yt-dlp-ejs) with `pip install -U`, and
  make sure a JS runtime exists (here: node v24 from nvm, not a distro package; Mint's apt
  `nodejs` is v18 — check yt-dlp's minimum before relying on it).
- [ ] Installer (Phase 6): the venv sees system packages, so `pip install yt-dlp` is skipped
  when the distro's 2024.04.09 is present — use `pip install -U yt-dlp` and check the version.
- [ ] Headless screenshots need `sudo apt install xvfb` (not installed); playback needs
  `libgtk-4-media-gstreamer` (Phase 4).

### Backlog after Phase 5 (2026-10-18, user: "most functionality is working; a few features still need work")
- [ ] **Phase 6 — packaging**: build-deb.sh and install.sh for 2.0 (deps `python3-gi gir1.2-gtk-4.0
  libgtk-4-media-gstreamer gstreamer1.0-plugins-good librsvg2-common fonts-ubuntu ffmpeg`); drop Flask,
  PyWebView, WebKit2GTK, routes/, templates/, static/, app.py, browser_app.py; rebuild AppDir from source;
  build-deb.sh still points at the 1.x Heroicons icon — use resources/icons/hicolor/…/org.mensuramedia.LinMediaDownloader.svg.
- [ ] **Phase 7 — verify**: `xvfb-run -a pytest`, headless renders of every state, keyboard-only pass,
  Orca pass, design review against the guide's §14 checklist; then merge feat/2.0-gtk4 → main, tag v2.0.0.
- [ ] Real-use check of Settings: Change… folder dialog, Check for update (needs network), Save diagnostics,
  sign-in choice of a specific profile — tested with fakes only, not yet clicked by the user.
- [ ] Download page: a queued second link ("Queue another link") — check the hand-over from one finished
  download to the next on a real playlist (the counts line and ring reset).
- [ ] Library player: playback needs `libgtk-4-media-gstreamer` (not installed here); untested by ear.
- [ ] Offered, not decided: keep YouTube titles as file names (spaces, Japanese characters) instead of
  1.x underscore sanitising.
- [ ] Old 1.x "alternative method" retry in media.py: now only runs when entries are really missing; review
  whether it is still needed at all with cookies working.
- [ ] Cookie copies: per process under $XDG_RUNTIME_DIR/linmediadownloader/session-<pid>/ (fixed 2026-10-18 after
  test runs deleted a live download's copy); watch the log for "could not find firefox cookies database".
