# 2026-10-18 — GTK 4 upgrade proposal and mockups

- Type: design / planning (no runtime change)
- Standards applied: linapptemplate GUI-GUIDE-AND-DESIGN-REFERENCE.md + docs/05-UX.md, 04-CSS.md,
  08-ICONS-AND-FONTS.md (Graphite Night tokens, Phosphor regular icons, Ubuntu font);
  universal-instruction-set (plan first, changelog, manifest, pending).
- Findings: Flask + PyWebView UI with Bootstrap from a CDN (not offline), 10 nav pages, backend
  already Flask-free outside modules/routes, cwd-relative data paths, distro yt-dlp too old,
  libgtk-4-media-gstreamer missing for playback.
- Files added: docs/design/GTK4-UPGRADE-PLAN.md, docs/design/mockups-gtk4/ (canvas.json + 9 .dc.html)
- Files changed: changelog.md, .claude/memory/pending.md
