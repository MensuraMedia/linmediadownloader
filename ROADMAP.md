# Roadmap

**Linux Media Downloader is an evolving project.** It's under active development and grows
over time — features are added, refined, and occasionally reworked based on real use. This
document lists what exists today and what's planned or under consideration. Nothing here is a
firm commitment or schedule; priorities shift as the product matures.

Legend: ✅ shipped · 🧭 designed (concept doc) · 🛠️ planned · 💡 idea / under consideration

---

## ✅ Shipped

- **Downloading** — YouTube audio (MP3) / video (MP4), single or full playlist.
- **Playlist download controls** — scope (Single / All (N) / First 10·20·30), **Skip long
  files (over 7 min)**, unified into one option group; grayed until a playlist is detected.
- **Real-time progress** — overall circle + centered per-file bar + **Length** column; live
  reconnect if you navigate away and back; only one download at a time.
- **Chapter / Tracklist Split** — split a long multi-chapter video into per-track files
  (embedded chapters or description tracklist; unlabeled → `NN_<video-title>`).
- **History** — completed downloads, newest first, with working "open folder" links.
- **Links history** — every submitted URL, YouTube-style cards, search, re-use.
- **Playlists manager** — rename, sortable Length/Filename/Size table, bulk text ops
  (clean, remove filler/special, replace spaces, truncate, standard-font, abbreviate dupes,
  case changes, number prefix), Undo/Redo, `.trash` + Empty trash, fixed colored sequence badges.
- **Player** — audio/video player + curation (delete, add-to-folder) over all files.
- **File Manager** — dense 3-column grid of app files, stats (duplicate names / same size),
  global text ops (one-undo), inline keyboard-controlled player, per-file delete.
- **Ignore Duplicates** — skip already-downloaded / ≥80%-similar tracks via a hidden manifest
  of original (pre-rename) titles + video ids.
- **Desktop integration** — native window (`app.py`), **one-command Debian installer**
  (`install.sh`), Linux program-menu installer + icon; packaging guide for Linux & Windows.

---

## 🛠️ Planned

- **2.0: native GTK 4 rewrite** — Python + GTK 4 with the Lin* theme (Graphite Night), four
  destinations instead of ten pages, no web view or local web server, everything installed
  locally. In progress on `feat/2.0-gtk4`; 1.x is tagged `v1.0.0`.
  → [mockups](docs/design/mockups-gtk4/README.md) · [plan](docs/design/GTK4-UPGRADE-PLAN.md)
- **Packaged builds** — `.deb` builder shipped (`packaging/build-deb.sh`); still to do: finish
  the AppImage, a Windows PyInstaller `.exe` (+ installer), and auto-publish to GitHub
  Releases (CI). → [docs/packaging.md](docs/packaging.md)
- **`pyproject.toml`** — enable `pipx install git+…` one-line installs.
- **YouTube cookie support** — a UI option to pass browser cookies (`--cookies-from-browser`)
  to get past bot-checks on rate-limited networks.
- **Keep yt-dlp current** — self-update / version indicator (it changes often against YouTube).
- **Automated integration test + CI** — a real-download smoke test and GitHub Actions builds.
- **More sources** — Vimeo, SoundCloud, and other yt-dlp-supported sites.

---

## 💡 Under consideration

- Enhanced backup & restore of a curated library.
- Cached durations for very large folders (avoid per-file `ffprobe` on open).
- Download queue (multiple jobs) with the concurrency guard relaxed safely.
- Precise (re-encode) chapter-split mode toggle for gapless cuts.
- Content-hash duplicate detection (beyond name/size heuristics).
- Optional user authentication / profiles.
- Silence-detection track boundaries when no tracklist exists (heuristic; unreliable).
- Theming / more customization options.

---

*Have an idea? Open an issue or PR — see the README's Contributing section. This roadmap will
keep changing as the app evolves.*
