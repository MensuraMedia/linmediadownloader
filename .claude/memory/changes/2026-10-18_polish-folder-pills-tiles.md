---
date: 2026-10-18
scope: Post-Phase-5 polish from the user's testing
---
## Changes
1. **Open folder goes to the playlist's folder** — `ui/pages/download.py`: `_saved_folder()` (common
   folder of the saved files) drives `open_done_folder()` and the done bar's "Downloaded n tracks to …".
   Root cause: both used the base download folder (`output_dir`), while playlists save into their own
   `<title>_playlist` sub-folder.
2. **No checkmark in any pill** — `ui/widgets/track_list.py` (Done), `ui/pages/activity.py` (Done),
   `ui/window.py` (header pill shows "Ready" without an icon; busy/attention/error keep theirs).
   Plain status lines (link "found", Settings tool rows) keep their icon: they are not pills.
3. **Activity tiles: icon centred** — `ui/pages/activity.py` `_tinted_tile`. Root cause: a GTK 4 Box
   gives a child its natural width only, so `halign CENTER` did nothing; the icon now expands, and the
   tile's own expand is pinned off so the expand does not spread to the row (titles stay at the left).
## Tests
tests/test_ui_download.py (open folder, Ready pill, chip label by type), tests/test_ui_activity.py
(tile centre, no expand), tests/test_ui_icons.py (no check icon in pill tables). 268 pass on DISPLAY=:0.
## Commits
11b5935, 902039f, 5e4aa8e
