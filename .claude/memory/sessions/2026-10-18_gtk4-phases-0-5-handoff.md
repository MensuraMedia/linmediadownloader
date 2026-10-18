---
date: 2026-10-18
session: GTK 4 upgrade, Phases 0–5 (handoff)
---
## State
- Branch `feat/2.0-gtk4` (pushed). 1.x frozen as tag `v1.0.0` + branch `release/1.x`.
- Phases 0–5 done: data dir + jobs, lintheme 1.5.3 (gtk4), shell + Download, Activity, Library, Settings.
- App runs from the menu entry (packaging/install-menu.sh, installed here): `venv/bin/python linmediadownloader.py`.
- The user's verdict: "most functionality is working; a few features still need work".

## How to work here
- Tests: `DISPLAY=:0 GSK_RENDERER=cairo venv/bin/python -m pytest -q` (263 pass); headless skips display tests.
  Commit only on exit code 0 (never pipe pytest through `tail` before checking it).
- Renders: `tools/shot_states.py --state {ready,downloading,done,error,narrow,activity,library,library-tidy,confirm-trash,settings} --out PNG`.
- Log: ~/.local/share/linmediadownloader/logs/app.log (environment, every download start/end, uncaught exceptions).
- Data dir ~/.local/share/linmediadownloader (`LMD_DATA_DIR`); downloads ~/Music/LinMediaDownloads (Settings).
- YouTube: VPN exit IP triggers the bot check; the app uses the signed-in browser automatically
  (LibreWolf Flatpak here) via a WAL-merged private cookie copy; JS runtime node v24 (nvm).
- Never delegate cookie/sign-in/security code to GLM; never run black on modules/.

## Key decisions (see decisions.md)
- No browser mode, no Flask in 2.0; network only through yt-dlp to pasted links.
- Status pill: one word (Ready / Downloading). Done = after the .webm is removed. Nothing saved = yellow dash ring.
- Equal panes; columns Status · Name · Length · Size; no yellow borders; lists use the app's colours.

## What's next
See pending.md "Backlog after Phase 5": Phase 6 packaging, Phase 7 verify, real-use checks of Settings,
queue hand-over, playback deps, file-name style decision. Waiting on the user: upstream the kit branch to
linapptemplate; `sudo apt install xvfb libgtk-4-media-gstreamer`.
