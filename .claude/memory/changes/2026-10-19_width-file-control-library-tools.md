---
name: width-file-control-library-tools
description: Window width fix, Open folder highlighting, File Control page, Library search/filter/tick-delete, plain playlist numbers
metadata:
  type: project
---

# 2026-10-19 — Window width, File Control, Library tools

## User requests
1. "The width of the app is too wide and fixed … expand as needed by the user, not automatically as the data is downloaded."
2. "Open folder" should highlight the folder (or the file).
3. Main checkmark (done ring) 50 % smaller.
4. Library numbers: no badge, just the number, larger; count limited to 99999.
5. New "File Control" page with all renaming, moved out of the Library.
6. Library: tick/select files and delete; search and filter.

## Root causes
- **Width growth**: GTK windows never shrink below their content's minimum. Activity history rows showed the
  save folder in a caption with no ellipsizing, and the page Stack measures every page, so each new history
  entry with a long path raised the whole window's minimum (1254 px measured) — on any page.
- **Fixed width**: the Download page's halves are homogeneous (min = 2 × wider half); the done card's three
  buttons (one row) and the track row's fixed bar made it 1052 px; Settings' two columns 990 px. With the rail,
  wide mode needed more than the 960 px breakpoint, so the window could never be dragged into single-column mode.
- **Test opened Nemo**: show_items was unpatched in a test, so gdbus asked the real file manager to show a
  temp path (the user saw "Could not find …/Classics_playlist"). tests/conftest.py now refuses every
  file-manager call unless a test patches it.

## Files
- ui/window.py (DEFAULT_W/H 1040×720, File Control page, open_in_file_control), ui/pages/activity.py (caption
  ellipsize), ui/pages/download.py (LABEL_W, button_flow, folder label, open_done_folder → show_items, wrap note),
  ui/pages/settings.py (tidy card removed, wraps, columns rebalanced), ui/widgets/track_list.py (ROW_GAP, BAR_W,
  LENGTH_CHARS, SIZE_CHARS), ui/widgets/button_flow.py (new), ui/widgets/player_bar.py (140 px title),
  ui/widgets/ring.py (CHECK_SCALE 0.5), ui/style.py (seq, check, field-label, trough rules),
  ui/pages/file_control.py (new), ui/pages/library.py (FileTable, numbers, renaming removed), ui/messages.py,
  ui/icons.py ("files"), ui/app.py, modules/utils/file_utils.py (show_items), modules/playlists.py (SEQ_WRAP),
  tools/shot_states.py (file-control state replaces library-tidy), README.md (Alt+1…5).
- Tests: conftest.py (file-manager guard), test_ui_file_control.py (new, 15), test_ui_library.py, test_ui_settings.py,
  test_ui_download.py, test_app.py (wrap at 99999). 286 pass.

## Verified
- Measured window minimums with a tree-walking script (long titles and paths): wide 933 px, single-column 795 px.
- Renders of download/done/downloading/library/file-control/settings/narrow checked by eye.
- Not verified by hand: ShowItems selecting a folder in Nemo on the real desktop (Nemo implements it; fallback opens
  the folder); deleting ticked files on real files (backend delete_media_file unchanged, moves to .trash).

## Round 5 (same day): panel icon, queueing several links, half-size done graphic
- User: "ensure there is an icon present in the panel / systray so users can minimize the app as music is being
  downloaded"; "paste in different links so music downloads are queued for continuous downloading"; the check was
  halved but "it was the full graphic that needed to be reduced".
- Root cause of the ring miss: I scaled only the check stroke inside the 168 px ring; ProgressRing now takes a
  scale and the done ring is ProgressRing(scale=0.5) (DONE_RING_SCALE); the progress ring keeps 168 px.
- Files: ui/tray.py (new), ui/app.py (tray, close-to-panel, _window()), ui/window.py (tray status from set_chip),
  modules/download/links.py (new), ui/pages/download.py (queue_links, _queue_if_many, _queued_options, queue list),
  ui/widgets/ring.py (scale), ui/messages.py; tests: test_tray.py, test_links.py, test_ui_download.py (+5). 297 pass.
- Not verified: the icon's look in the panel (captured only as a changed 40 px region; my screen grab's colours were
  unreadable), hiding a real window during a real download, the desktop notification.
