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

## 2026-10-18 — GTK 4 upgrade (approved; Phases 0–1 done, Phase 2 next)
Plan + mockups: `docs/design/GTK4-UPGRADE-PLAN.md`, `docs/design/mockups-gtk4/`
(canvas: https://claude.ai/artifact/Xv1GvXnzBciwh6UqgYwC7w). All 8 departures approved (decisions.md).
Work on branch `feat/2.0-gtk4`. Phase 1 done (kit 1.5.0 vendored). Next: Phase 2 — shell + Download page.
- [ ] Offer linapptemplate branch `feat/gtk4-components` (local clone in a session scratchpad,
  commit 793f9d5) upstream — needs the user's OK; re-create from lintheme/ here if the clone is gone.
- [ ] Kit gap: GtkDropDown arrow comes from the system theme (both toolkits), not a Phosphor caret.
- [ ] Headless screenshots need `sudo apt install xvfb` (not installed); playback needs
  `libgtk-4-media-gstreamer` (Phase 4).
