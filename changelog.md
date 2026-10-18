# Changelog

Local, git-independent, append-only change log. ISO 8601 datetimes. Newest at the bottom.

| Date-Time | Change Description |
|-----------|-------------------|
| 2026-07-31T00:00:00 | Onboarded existing project; applied universal standards (agents, permissions, memory, rules) into .claude/ |
| 2026-07-31T00:00:01 | Fixed broken cross-module cancellation: routed cancel flag through settings accessor functions |
| 2026-07-31T00:00:02 | Progress hook now raises yt_dlp DownloadCancelled to actually abort; download_media handles it as 'cancelled' |
| 2026-07-31T00:00:03 | Repaired unreachable dead code in /api/cancel-download (history append was after the return) |
| 2026-07-31T00:00:04 | SECRET_KEY now env-overridable with random fallback instead of hardcoded value |
| 2026-07-31T00:00:05 | Removed unused imports (os in app.py, re/time in media.py, threading in browser_app.py) |
| 2026-07-31T00:00:06 | Removed stale .py.error backup files (root + AppDir); synced corrected sources into AppDir/usr/bin |
| 2026-07-31T00:00:07 | Added CLAUDE.md, changelog.md, .claudeignore, and .claude/memory structure |
| 2026-07-31T00:00:08 | Repointed git origin to MensuraMedia/linux-media-downloader (future work); kept mikesdatawork as upstream |
| 2026-07-31T00:00:09 | Added tests/test_app.py (15 offline unit + route tests); added requirements-dev.txt (pytest, pyflakes) |
| 2026-07-31T00:00:10 | Removed unused error_code assignments in media.py; pyflakes clean across runtime modules + tests |
| 2026-07-31T00:00:11 | Rewrote README into a robust, current form (architecture, structure, API, config, dev/test, packaging); synced AppDir copy |
| 2026-07-31T00:00:12 | Fixed per-file progress: frontend now uses server-computed progress; added byte-estimate + fragment fallbacks |
| 2026-07-31T00:00:13 | Added live current-file readout (size/%/speed), smooth playlist circle, 500ms polling |
| 2026-07-31T00:00:14 | Added Links History feature: /links page, /api/links-history, persisted links_history, YouTube-style cards |
| 2026-07-31T00:00:15 | Stopped tracking runtime data/*.json (history regenerated at runtime); added tests (19 total) |
| 2026-07-31T00:00:16 | UI: current-file bar moved below the blue track title (centered, fixed); removed the 'processing' label |
| 2026-07-31T00:00:17 | UI: replaced the redundant table 'Progress' column with a 'Length' (track duration) column; backend now exposes per-track duration |
| 2026-07-31T00:00:18 | Feature: 'Skip long files' filter for playlists (yt-dlp match_filter skips tracks > 6 min) |
| 2026-07-31T00:00:19 | Sidebar: renamed 'Backups' to 'History'; added 'Playlists' tab |
| 2026-07-31T00:00:20 | Feature: Playlists manager (list, rename folder, sortable Length/Filename/Size table, bulk ops) with path-safety guards; 28 tests |
| 2026-07-31T00:00:21 | Fix: playlist scan no longer walks into the home dir (only *_playlist folders contribute a parent root); regression test (29 total) |
| 2026-07-31T00:00:22 | Docs: added DOCUMENTATION.md (full technical reference with tables); linked from README |
| 2026-07-31T00:00:23 | Playlists: added file ops — remove filler words, truncate to 35, standard-font (ASCII), lower/UPPER/Title/Camel case |
| 2026-07-31T00:00:24 | Playlists: rename collisions now get a 4-char salt (no longer skipped); grouped ops UI with a gap before the table; 34 tests |
| 2026-08-01T09:00:00 | Playlists: filler-word removal now detects words inside camelCase (e.g. SongOfficialVideo -> Song) |
| 2026-08-01T09:05:00 | Playlists: added Undo/Redo (rename ops reversible; delete_long moves to .trash); state via /api/playlist-undo,-redo |
| 2026-08-01T09:10:00 | Playlists: large sequence badge (001, 002, …) on each list entry; 36 tests, live end-to-end verified |
| 2026-08-01T10:00:00 | Playlists: added Empty trash action (/api/playlist-empty-trash) to purge deleted files; 37 tests |
| 2026-08-01T10:30:00 | Playlists: sort newest-first (by mtime) so 001=newest; per-playlist badge colour picker (persisted, migrates on rename) |
| 2026-08-01T10:45:00 | Playlists: added 'Abbreviate duplicates' op (recurring tokens -> 4 chars); 41 tests, live verified |
| 2026-08-01T11:00:00 | Playlists: softened button hover to a subtle grey (matches the Back button) |
| 2026-08-01T12:00:00 | Home: unified download scope into one radio group (Single/All(N)/First 10-30); removed duplicate 'Full Playlist' |
| 2026-08-01T12:15:00 | Home: playlist-only options stay visible but grayed/disabled until a playlist is detected |
| 2026-08-01T12:30:00 | Playlists: added filler words (OST, soundtrack, score, OVA, ONA, AMV, PV, resolutions, etc.); 44 tests |
| 2026-08-01T13:00:00 | Playlists: reorganized text controls into minimal labeled columns (Files / Clean up / Transform / Case), matching Home |
| 2026-08-01T13:30:00 | Playlists: fixed action-button alignment — truncate long names (numbers/actions no longer compressed), tidy Undo/Redo header |
| 2026-08-01T14:00:00 | Feature: Player tab — audio/video player (seek/volume/skip/auto-next) over all downloaded files, with delete + add-to-folder curation; range streaming |
| 2026-08-01T14:15:00 | Fix: 'First N' now builds only N rows in the progress table (was showing the whole playlist); 50 tests |
| 2026-08-01T14:30:00 | Playlists: added filler words 'animated'/'animation'/'anime'; Title Case now capitalizes every word (across _ - . digits) |
| 2026-08-01T14:45:00 | Docs: added File Manager concept document (docs/concept-file-manager.md); 52 tests |
| 2026-08-01T15:00:00 | Feature: File Manager tab — app-recorded file grid, stats (dup names/same size), global text ops (one-undo), keyboard-controlled inline player, per-file delete; 56 tests |
| 2026-08-01T15:30:00 | Docs: added Ignore Duplicates concept (docs/concept-ignore-duplicates.md) — originals manifest + >=80% relevancy skip |
| 2026-08-01T16:00:00 | Home: state retention — reconnect to an in-progress download on load (rebuild table/circle/cancel, resume polling) |
| 2026-08-01T16:05:00 | API: /api/download refuses a second concurrent download (fixes stuck background process needing app restart); 57 tests |
| 2026-08-01T16:30:00 | Docs: added Chapter/Tracklist Split technical design (docs/concept-chapter-split.md) — recommends ffmpeg -c copy post-hoc with hybrid chapter source |
| 2026-08-01T17:00:00 | Feature: Chapter/Tracklist Split implemented — modules/download/chapters.py (parse chapters/description, ffmpeg -c copy), Home 'Split Multi-Chapter video' option; unlabeled -> NN_<video-title-summary>; output folder auto-listed in Playlists/File Manager |
| 2026-08-01T17:15:00 | Changed 'long file' threshold from 6 to 7 minutes everywhere (skip-long filter, delete-long, labels, docs) |
| 2026-08-01T17:30:00 | Fix(History): folder links now use the working .open-folder handler (dead openDirectory removed); page reads fresh from settings |
| 2026-08-01T17:35:00 | Fix(History): descending sort by download time; added timestamps to history entries; in-place history mutation (no stale refs) |
| 2026-08-01T17:45:00 | Fix(Split): works for playlist/radio URLs (forces single-video); reads chapters reliably |
| 2026-08-01T17:50:00 | Fix(Split): accurate progress + status during splitting — defers 'completed' until split done, reports per-track progress (65 tests) |
| 2026-08-01T18:00:00 | UI: File Manager grid fixed to 3 columns with 2px cell padding + gap |
| 2026-08-01T18:05:00 | UI: fixed Home progress-bar symmetry — bar now centers under the title (percentage moved below, no longer shifts the bar) |
| 2026-08-01T18:30:00 | Docs: added packaging & distribution guide (docs/packaging.md) — Linux (pipx/AppImage/.deb/Flatpak) + Windows (PyInstaller); linked from README + DOCUMENTATION |
| 2026-08-01T19:00:00 | Packaging: added Heroicons 'window' app icon + install-menu.sh (per-user Mint/Cinnamon menu entry); fixed AppDir .desktop, added AppRun, removed committed __pycache__ |
| 2026-08-02T09:00:00 | Docs: added INSTALL.md (full Linux + Windows setup) and ROADMAP.md (evolving product, categorized features); reinforced 'still evolving' language; fixed DOCUMENTATION roadmap (Chapter Split implemented) |
| 2026-08-02T10:00:00 | Feature: Ignore Duplicates — skip already-downloaded/≥80%-similar tracks via an original-title+id manifest (modules/download/dedupe.py); Home checkbox; 71 tests |
| 2026-08-02T10:15:00 | Packaging: one-command Debian/Ubuntu/Mint installer (install.sh) at top of README — installs deps, clones, venv, program-menu entry |
| 2026-08-02T11:00:00 | UI: added FAQ page (features/choices/pages, split explanation); sidebar renamed History→History Downloads, Links→History Links, added FAQ, reordered near About, left-aligned |
| 2026-08-02T11:10:00 | UI: squared corners on Playlists/Player/Links cards; added search to History + Playlists pages |
| 2026-08-02T11:15:00 | Fix: split downloads now record the tracks folder in History (folder link opens the split folder, not the root); URL input auto-clears on completion |
| 2026-08-02T12:00:00 | Feature: download queue — add links while one runs; they run one-after-another. New Pending page (/pending) + sidebar button showing queued/active/completed jobs |
| 2026-08-02T12:10:00 | Home: adding a link while downloading now queues it (no error); progress follows each job (job_id); 'See your download here' link to History on completion; input clears on submit |
| 2026-08-02T13:00:00 | Feature: Settings page — edit filler words + character replacements (modules/config/user_settings.py); drives Remove-filler + new 'Apply replacements' op across Playlists/File Manager; dedupe uses the same list |
| 2026-08-02T13:10:00 | FAQ: documented all text-control operations with descriptions + the Settings/Pending pages |
| 2026-08-02T14:00:00 | Packaging: added packaging/build-deb.sh — builds a valid .deb (/opt install, launcher, menu entry, icon; postinst venv w/ yt-dlp/pywebview). Verified with dpkg-deb; build/ + dist/ git-ignored |
| 2026-08-05T03:30:00 | Fix: reliable desktop launch — install.sh creates the venv with --system-site-packages (+ install-time GTK/WebKit2 import check) so PyWebView finds its GTK backend; app.py disables the WebKit2GTK DMABUF renderer and drops the fixed time.sleep(1) (make_server binds synchronously) — ~1s faster to window |
| 2026-08-05T03:40:00 | Feature: Home page video resolution picker — selecting Video reveals 720p/1080p (default 1080p); Audio unchanged (highest quality). video_quality threaded UI → /api/download → enqueue_download (job dict) → download_media (height-capped yt-dlp format) |
| 2026-08-05T03:50:00 | Feature: centralized logging (console + rotating logs/app.log) via modules/config/logging_config.py; setup_logging() at both entrypoints, per-module lmd.* loggers, 16 print() calls converted, yt-dlp routed via YTDLPLogger |
| 2026-08-05T04:00:00 | Repo consolidation: MensuraMedia established as the single canonical repo; the divergent mikesdatawork tree's unique assets (logging, launch postmortem) ported here; local dev checkout repointed to this remote |
| 2026-08-05T04:30:00 | Governance: upgraded the .claude/ framework to Universal Instruction Set v2026.04 — added lifecycle hooks (.claude/hooks/ + settings.json), slash commands (plan-first/build-test/session-end/route/team), agent-teams, routing-rules, and the missing skills; rewrote CLAUDE.md to the v2026.04 layout (accurate to this app's queue/accessor architecture). Additive only — all existing project memory (decisions, changes, sessions) preserved |
| 2026-10-18T11:00:00 | Design: GTK 4 upgrade proposal — docs/design/GTK4-UPGRADE-PLAN.md (examination of 1.0, 10→4 destinations, GTK 4.14 widget map, departures needing approval, phased plan) + 9 Graphite Night mockups (docs/design/mockups-gtk4/, published as a design canvas). No app code changed |
| 2026-10-18T14:20:00 | Repo: tagged v1.0.0 (171a512) and branched release/1.x for 1.x fixes; 2.0 work moves to feat/2.0-gtk4. Recorded the approved 2.0 decisions in decisions.md |
| 2026-10-18T14:30:00 | Phase 0: new modules/config/paths.py — all data in ~/.local/share/linmediadownloader (XDG, LMD_DATA_DIR override) with a one-time copy-only 1.x migration; settings/user_settings/logging/dedupe/playlists use it; nothing written to the cwd any more |
| 2026-10-18T14:35:00 | Phase 0: new modules/download/jobs.py — submit/cancel/status/queue logic moved out of routes/api.py so the GTK UI can reuse it; links_history now loads/trims in place like download_history |
| 2026-10-18T14:40:00 | Tests: tests/conftest.py isolates the data dir (the 1.x suite wrote fake links into ./data); tests/test_paths_jobs.py adds 13 tests (92 total, all pass) |
| 2026-10-18T14:50:00 | Docs: mockups added to documentation — docs/design/mockups-gtk4/README.md gallery + 9 PNG renders; README (2.0 preview, data folder), DOCUMENTATION §9/§13, ROADMAP, upgrade plan updated; Library mockup labels shortened so no button wraps |
| 2026-10-18T15:45:00 | Phase 1: vendored lintheme 1.5.0 (GTK 4 only, lintheme/VENDORED.md) with new lintheme/gtk4 (components + DashboardWindow on GTK 4.14, async confirm, maximize-safe layout modes) — drafted by GLM, reviewed on a real display, 5 defects fixed; icons.add_icon_dir for app icons |
| 2026-10-18T15:50:00 | Phase 1: 17 app Phosphor icons in resources/icons/phosphor/regular (+ MIT licence), ui/icons.py registers them and lists every icon 2.0 uses; tests/test_kit_*.py + test_ui_icons.py (131 tests on a display, 22 GTK tests skip headless) |
| 2026-10-18T16:20:00 | Phase 2 backend: modules/download/preview.py (entries + skip reasons, apply_options, classify_error), per-track states in current_download['tracks'], shared settings.LONG_SECONDS, 480p; 145 tests. Live check: YouTube bot-checks this IP even with yt-dlp 2026.08.19, so browser sign-in becomes required |
| 2026-10-18T17:40:00 | Phase 2: GTK 4 app — linmediadownloader.py entry point, ui/ (single-instance app with Ctrl+Return / Esc / Ctrl+L / Ctrl+Q, DashboardWindow with 4 destinations, status chip, 250 ms poller, Download page: ready / reading / downloading / done / can't reach, compact layout, Cairo progress ring, ListView track list, all copy in ui/messages.py), tools/shot_states.py — drafted by GLM in two rounds, reviewed on a real display, 5 defects fixed by Claude; kit 1.5.1 (no duplicate header title); 165 tests |
| 2026-10-18T18:10:00 | Download page (user test): a download that saved nothing now shows an attention ring with a dash, "Nothing was downloaded", the plain reason (from yt-dlp's recorded errors, new current_download['errors']) and Try again — never a success tick; no check icon in the action bar; no "Tracks" heading; Paste buttons keep their natural width; 167 tests |
| 2026-10-18T19:20:00 | YouTube access: modules/download/access.py finds every browser profile signed in to YouTube (cookie names/dates only), picks the running, most recently used one (LibreWolf here) and gives yt-dlp its cookies plus a local JS runtime (node); yt-dlp[default] brings the local challenge solver. Verified: real download through the VPN works. Sign-in shown under the link; bot-check copy updated |
| 2026-10-18T19:25:00 | Fix (from 1.x): the filename post-processor returned (info, None) instead of (files, info), so every download ended with "unhashable type: 'dict'"; Mix links (list=RD…) now read and download as the single video instead of enumerating ~758 suggestions; 178 tests |
| 2026-10-18T20:30:00 | Download page (user feedback): a track is Done only after yt-dlp's last post-processing step (MoveFiles) — the .webm is converted and deleted first (verified on a real download); 'Converting' pill meanwhile; video+audio pairs no longer count twice (1.x bug); status pill shows the word only (Ready / Downloading); equal-width panes; track columns Status · Name · Length · Size (≈ estimate for MP3 before, real size after); shorter skip pills; focus ring in the accent blue (no yellow) |
| 2026-10-18T21:10:00 | Phases 3–4: Activity (Now, Up next with remove, merged History with search, filters, actions, clear-older confirm; modules/history.py) and Library (playlists, all files, rename, badge colours, tidy names with live preview, undo/redo, trash confirm, GStreamer audio player bar, videos to the system player) — drafted by GLM in two rounds, display bugs fixed by Claude (missing return, unfilled template, test-bus clashes, test timestamps, popover render hang, tidy count); GLM's whole-file black reformat of modules/ reverted to the real changes; kit 1.5.2 (icons keep their size; confirm focuses the safe answer); 225 tests |
| 2026-10-18T21:45:00 | User test: Beethoven 7th downloaded but the ring froze (3 s download, then 30 s of MP3 conversion with no progress) and the file was hard to find (saved as Beethoven_7th_Symphony_Complete.mp3, not the shown title). Fixes: conversion progress from the growing MP3 vs length x 192 kbps (verified live: 5% to 95% over 28 s), ring = half download + half conversion per MP3 track, "Converting · n%" pill; done card says "Saved as <file>" with Show file (FileManager1 ShowItems, folder fallback); Play in Library opens a single file under All files and plays it; empty *_playlist folders removed after a download (and the one left in ~/Downloads by the failed Mix test); logging: start-up environment block, download start/end with options, saved paths and errors, conversion, uncaught exceptions from threads and GTK callbacks; 228 tests |
