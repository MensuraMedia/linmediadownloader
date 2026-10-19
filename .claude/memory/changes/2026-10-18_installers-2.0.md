---
date: 2026-10-18
scope: Phase 6 — 2.0 installers and README
---
## Files
- install.sh — rewritten for 2.0: apt deps (GTK 4, ffmpeg, optional GStreamer/font), clones to
  ~/.local/opt/linmediadownloader (marker `.lmd-installer-clone`) or installs a checkout in place, venv with
  `pip install -U -r requirements.txt`, environment check (GTK ≥ 4.10, yt-dlp, Deno, ffmpeg), menu entry;
  update = re-run; uninstall keeps data and never deletes a user's own checkout. LMD_DIR/LMD_BRANCH/LMD_REPO/LMD_SKIP_APT.
- clone-and-install.sh (new) — full clone to ~/projects/linmediadownloader (or a given folder), then install.sh in place.
- packaging/build-deb.sh — package `linmediadownloader` 2.0.0 (version from ./VERSION), /opt, launcher, app-id
  desktop file + icon, Depends/Recommends for GTK 4, postinst venv (needs network), no 1.x web code.
- packaging/install-menu.sh — Categories without Network (validator: listed twice). 1.x icon removed.
- requirements.txt — 2.0 runtime only: yt-dlp[default], deno>=2.3. Flask moved to requirements-dev (1.x tests).
- modules/download/access.py — the venv's own deno first; node older than 22 skipped (yt-dlp's minimum; Mint apt nodejs is 18).
- modules/tools.py, ui/messages.py — "Update yt-dlp" only where the venv is writable (the .deb's is root's).
- README.md — rewritten for 2.0, Install first (one command, .deb, clone and install); 2.0 screenshots.
- INSTALL.md, docs/packaging.md — 2.0 pointers; the rest marked 1.x.
## Root causes found on the way
- Mint's apt nodejs (18) is below yt-dlp's node minimum (22): a PATH node would have been chosen and refused.
## Verification
271 tests on a display. Installers trialled with HOME in a scratch folder and LMD_REPO=file://… (no sudo).
.deb: dpkg-deb -I/-c, desktop-file-validate, unpacked + venv + window opened from the packaged code.
