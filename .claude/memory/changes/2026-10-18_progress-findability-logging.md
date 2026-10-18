# 2026-10-18 — Conversion progress, findable files, logging

- Reported by the user (screenshot): progress did not build with the download; the downloaded file
  could not be found; asked for proper logging.
- Root causes (from the app log): the 41 min track downloaded in 3 s and then converted to MP3 for
  30 s, which yt-dlp reports no progress for, so the ring jumped and froze. The file was saved, then
  the 1.x sanitiser renamed it ("Beethoven - 7th Symphony (Complete) ✔.mp3" to
  "Beethoven_7th_Symphony_Complete.mp3"); nothing in the UI or the log named the final file; "Play
  in Library" only knew playlist folders. A failed Mix attempt had left an empty *_playlist folder
  (1.x creates it before downloading and never removes it).
- Fixes: media.conversion_progress() (MP3 size vs duration x 192 kbps) reported by
  jobs.status_snapshot as phase 'converting'; ring/track/file bar use it; set_track keeps the final
  path; done card "Saved as" + Show file (file_utils.show_file via org.freedesktop.FileManager1);
  window.open_in_library + LibraryPage.show_file; media._remove_if_empty; logging in
  linmediadownloader.py (environment, uncaught exceptions) and media.py (start/end, conversion,
  saved paths, errors).
- Verified: real download of the same video sampled every 2 s: conversion 5% to 95% then Saved;
  228 tests on a display.
- Files: modules/download/{media,jobs}.py, modules/utils/file_utils.py, ui/pages/{download,library}.py,
  ui/window.py, ui/widgets/track_list.py, ui/messages.py, linmediadownloader.py, tests.
