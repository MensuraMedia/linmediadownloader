---
date: 2026-10-18
scope: Phases 3–5 (Activity, Library, Settings) + sign-in robustness
---
## Files
- ui/pages/activity.py, modules/history.py — Now / Up next / History, filters, clear older.
- ui/pages/library.py, ui/player.py, ui/widgets/player_bar.py, modules/playlists.py — playlists, tidy names with preview, undo/redo, trash, player. Long playlist titles ellipsize (they set the window minimum to 1241 px).
- ui/pages/settings.py, modules/config/{settings,user_settings}.py, modules/tools.py — Settings page; download folder default ~/Music/LinMediaDownloads.
- modules/download/access.py — cookie copies per process and per call; cleanup only own/dead-process copies.
- modules/download/media.py — skipped entries count as handled (no needless re-download).
- ui/pages/download.py — Download another flow; no counts line above the track list while downloading/done.
- lintheme 1.5.3 — lists follow the theme.
## Verification
263 tests pass on DISPLAY=:0 (171 + 90 skipped headless). Real downloads verified: single, playlist (Akira, 7 saved + 3 skipped), chapter split.
## Origin
Activity, Library and Settings drafted by GLM (session lmd-phase2-ui); reviewed and fixed by Claude on a real display.
