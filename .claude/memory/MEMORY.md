# MEMORY.md — Project Memory Index
# Keep under 200 lines. One entry per line. Link to detail files.

## Session Logs
<!-- Add newest first -->
- [2026-10-18 GTK 4 Phases 0–5 handoff](sessions/2026-10-18_gtk4-phases-0-5-handoff.md) — 2.0 state, how to test/render, what's next
- [2026-07-31 onboarding + optimization](sessions/2026-07-31_onboarding-and-optimization.md) — Applied universal standards; fixed cancel bug, dead code, cleanup

## Changes
<!-- Add newest first -->
- [2026-10-18 Phases 3–5](changes/2026-10-18_phase3-5-activity-library-settings.md) — Activity, Library, Settings; per-process cookie copies; skips count as handled
- [2026-08-02 deb package](changes/2026-08-02_deb-package.md) — .deb builder (packaging/build-deb.sh); /opt install, launcher, menu, postinst venv
- [2026-08-02 settings page](changes/2026-08-02_settings-page.md) — User-editable filler words + char replacements; Apply-replacements op; FAQ text-ops
- [2026-08-02 download queue + pending](changes/2026-08-02_download-queue-pending.md) — Queue links while one runs; Pending page
- [2026-08-02 ignore-dupes + debian install](changes/2026-08-02_ignore-dupes-and-debian-install.md) — Ignore Duplicates (original-name+id manifest); one-command install.sh for Debian
- [2026-08-01 history + split fixes](changes/2026-08-01_history-and-split-fixes.md) — History folder links + descending sort; split works on radio URLs + accurate progress/status
- [2026-08-01 chapter split + 7min](changes/2026-08-01_chapter-split-and-7min.md) — Chapter/tracklist split (ffmpeg -c copy, unlabeled→NN_summary); long-file threshold 6→7 min
- [2026-08-01 state retention](changes/2026-08-01_state-retention.md) — Home reconnects to an in-progress download; /api/download rejects concurrent downloads
- [2026-08-01 file manager](changes/2026-08-01_file-manager.md) — File Manager tab (app-file grid, stats, global ops, keyboard player)
- [2026-08-01 player + firstN fix](changes/2026-08-01_player-and-firstN-fix.md) — Player/curation page (stream, delete, add-to-folder); First-N table row cap fix
- [2026-08-01 unified scope + gray + filler](changes/2026-08-01_unified-scope-gray-filler.md) — One download-scope radio group, grayed-until-detected options, more filler words
- [2026-08-01 fixed seq + limit + 3col](changes/2026-08-01_fixed-seq-limit-3col.md) — Fixed sequence badges (wrap 999→000), top-N download limit, 3-column Home layout
- [2026-08-01 trash/color/sort/abbreviate](changes/2026-08-01_trash-color-sort-abbreviate.md) — Empty-trash, newest-first sort, badge colors, abbreviate-dupes, subtle hover
- [2026-08-01 undo/redo + camelCase filler + seq](changes/2026-08-01_undo-redo-camelcase-seq.md) — Undo/Redo (delete→.trash), camelCase filler detection, 001/002 badges
- [2026-07-31 playlist filename ops](changes/2026-07-31_playlist-filename-ops.md) — remove-filler/truncate/standard-font/case ops, 4-char collision salt, grouped ops UI
- [2026-07-31 skip-long + playlists manager](changes/2026-07-31_skip-long-and-playlists-manager.md) — Skip-long filter, History rename, Playlists manager (list/rename/ops) + path-safety; DOCUMENTATION.md
- [2026-07-31 progress + links history](changes/2026-07-31_progress-fix-and-links-history.md) — Per-file progress fix, live readout, Links History feature, runtime-data untracking
- [2026-07-31 cancel + cleanup](changes/2026-07-31_cancel-fix-and-cleanup.md) — Cross-module cancel fix, dead-code repair, unused imports, secret key, AppDir sync

## Decisions
- [Decision Log](decisions.md) — Architectural and design decisions

## Project Context
<!-- User info, project goals, references -->
- Onboarded from https://github.com/mikesdatawork/linux-media-downloader on 2026-07-31.
- Tech stack: Python / Flask (blueprints) + PyWebView + yt-dlp. Localhost-only desktop app.
- Two entry points: app.py (native window), browser_app.py (browser fallback).

## Feedback & Preferences
<!-- User corrections, confirmed approaches -->
- Alterations must follow the `-universal-*` instruction set (copy-and-adapt into `.claude/`).
