# 2026-10-18 — 2.0 Phase 2: GTK 4 window and the Download page

- Branch feat/2.0-gtk4. Backend part (Claude, commit b302e20): modules/download/preview.py
  (preview_link, apply_options, classify_error, summarize), current_download['tracks'],
  settings.LONG_SECONDS, 480p.
- UI (GLM session lmd-phase2-ui, 2 rounds, ~2,600 lines): linmediadownloader.py, ui/app.py,
  ui/window.py, ui/poller.py, ui/messages.py, ui/style.py, ui/pages/download.py,
  ui/widgets/{ring,track_list}.py, tools/shot_states.py, tests/test_ui_{download,messages}.py.
- Defects found by Claude on the real display and fixed by Claude:
  1. app icons not registered when the window is built outside the entry point (all UI tests
     errored) — ui/window.py registers them;
  2. Escape bound app-wide would swallow Esc in dialogs/popovers — `cancel` action enabled only
     while downloading (DownloadPage.state property + on_state);
  3. cancel test used a bare Gtk.Application without the app's actions — real App, module scope;
  4. ring text raised in its draw func every frame (Pango.FontDescription.new(str)) and sized in
     points — from_string + set_absolute_size(px);
  5. GTK 4 header showed a duplicate centred title — kit 1.5.1 set_title_widget(Gtk.Box()).
- Visual review round (fixed by GLM from Claude's screenshots + brief): counts disagreed across
  ring/chip/action bar (now one merged view of preview skips + download-time skips), done ring,
  row alignment, error banner content, error action bar copy, Save-to button width, compact
  chip text and preview strip, VPN hint in the bot-check message.
- Verified: 165 tests on a display (127 + 38 skipped headless); five renders match the mockups;
  entry point opens the window from another cwd and writes only to the data folder.
- Not verified: a real download — YouTube refuses this machine's VPN exit IP (bot check).
