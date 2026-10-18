# Linux Media Downloader

**Linux Media Downloader** is a lightweight desktop application for downloading media
content (currently YouTube) for personal, educational, or non-commercial use. It pairs a
small **Flask** backend with a **PyWebView** native window, delegating all downloading to
the excellent [**yt-dlp**](https://github.com/yt-dlp/yt-dlp) library.

## ⚡ Install on Debian / Ubuntu / Linux Mint — one command

```bash
curl -fsSL https://raw.githubusercontent.com/MensuraMedia/linux-media-downloader/main/install.sh | bash
```

Installs everything (Python, ffmpeg, the GUI backend), sets up the app, and adds it to your
**program menu** with its own icon — then launch **"Linux Media Downloader"** like any other
app. Re-run to update; `bash ~/.local/share/linux-media-downloader/install.sh --uninstall` to
remove. Other platforms / manual setup: **[INSTALL.md](INSTALL.md)**.

> **Repository note:** This project is maintained at
> **[`MensuraMedia/linux-media-downloader`](https://github.com/MensuraMedia/linux-media-downloader)**.
> It originated at `mikesdatawork/linux-media-downloader` (kept as the `upstream` remote).
>
> **Full technical reference:** see [DOCUMENTATION.md](DOCUMENTATION.md).

---

## 📋 Table of Contents

- [Project Status](#-project-status)
- [Features](#-features)
- [Screenshot](#-screenshot)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Running the App](#-running-the-app)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Development & Testing](#-development--testing)
- [AppImage Packaging](#-appimage-packaging-linux)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)
- [Disclaimer](#-disclaimer)

---

## 🚧 Project Status

- **In Development** — this product is **still evolving**; it's under active development and
  grows over time, so expect frequent updates and refinements. See **[ROADMAP.md](ROADMAP.md)**.
- **Current support** — YouTube videos and playlists, powered by `yt-dlp`.
- **Setup** — full install steps for **Linux and Windows** are in **[INSTALL.md](INSTALL.md)**.

---

## ✨ Features

- **YouTube video & playlist download** — single videos or entire playlists.
- **Audio or video mode** — audio extracted to MP3 (192 kbps) or full video as MP4.
- **Real-time progress** — an overall progress circle (which folds in the current file's
  fraction for smooth movement) plus a live progress bar centered beneath the current
  track's title; the download table lists each track's **Length** (duration). Byte,
  estimate, and fragment fallbacks keep the bar accurate.
- **Cancel in progress** — abort an active download cleanly at any time.
- **Download history** — the last 100 downloads persisted to `data/download_history.json`.
- **Links history** — a scrollable, YouTube-style record of every link you've submitted
  (thumbnails, badges, search, open/copy/re-use), on its own **Links** tab.
- **Skip long files** — when a playlist is detected, optionally skip any track over
  7 minutes so they're never downloaded.
- **Ignore Duplicates** — skip tracks you've already downloaded, matched by video id and by
  original (pre-rename) title with ≥80% relevancy (so `Beach_Original_music` ≈ `Original Beach
  Music`), using a hidden manifest built as you download.
- **Playlists manager** — a **Playlists** tab listing every downloaded playlist (folders
  with more than one track). Rename a playlist (renames its folder), then drill in to a
  sortable table (Length / Filename / Size) with bulk operations: delete all long files
  (>7 min), clean up names, remove special characters, replace spaces with underscores,
  remove filler words (music/mix/remaster/live/4k/hd/months/…), truncate to 35 chars,
  normalize to a standard font (ASCII), change case (lower/UPPER/Title/Camel), and add a
  number prefix, and abbreviate duplicate strings (`Predator_Soundtrack_Track01` →
  `Pred_Soun_Track01`). Filler-word removal works even inside camelCase names
  (`SongOfficialVideo` → `Song`). Name collisions are resolved with a 4-character salt, and
  every operation is **undoable** (delete moves files to `.trash`, purgeable via Empty
  trash). Playlists carry a **fixed** sequence badge (assigned newest-highest, wraps
  `999`→`000`), sorted latest-added first, with per-playlist badge colours you can pick.
- **Playlist download controls** — a single scope choice (Single Video / All (N) / First
  10 / 20 / 30) plus a **Skip long files** filter, in clean columns. Playlist-only options
  stay visible but grayed-out until a playlist is detected.
- **Player & curation** — a **Player** tab with an audio/video player (play, seek/fast-
  forward, volume, skip ±10s, auto-next) over a searchable list of every downloaded file.
  Delete a file you don't want, or **add it to a new folder** as you listen to build a
  curated playlist on the fly.
- **File Manager** — a dense grid of every app-recorded file with stats (duplicate names,
  same size), the full set of global text operations (one-undo across all folders), and an
  inline keyboard-controlled player (→ +5s, ← −2s, ↑/↓ volume, Delete = stop & delete).
- **Folder selection & open** — choose a download directory and open it in your file manager.
- **Filename sanitization** — output names are normalized (alphanumeric + underscores).
- **Two ways to run** — native desktop window *or* an ordinary web browser.

---

## 🖼️ Screenshot

![Main UI](screenshots/mbs-main-ui.png)

### Coming in 2.0: native GTK 4

Version 2.0 is a full rewrite as a native GTK 4 app (no web view, no browser), with four
destinations (Download, Activity, Library, Settings) instead of ten pages. Work happens on the
`feat/2.0-gtk4` branch; 1.x stays available as the `v1.0.0` tag and the `release/1.x` branch.

![2.0 Download page mockup](docs/design/mockups-gtk4/images/Main.png)

All nine mockups: **[docs/design/mockups-gtk4](docs/design/mockups-gtk4/README.md)** ·
plan: **[GTK4-UPGRADE-PLAN.md](docs/design/GTK4-UPGRADE-PLAN.md)**

---

## 🏗️ Architecture

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| Native shell | **PyWebView** (`app.py`) | Renders the UI in a desktop window |
| Browser fallback | **Flask** dev server (`browser_app.py`) | Same UI at `http://127.0.0.1:5000` |
| Web server | **Flask** blueprints | Serves UI pages and a JSON API |
| Download engine | **yt-dlp** | Extraction, download, audio post-processing |

Shared runtime state (the current download and the history list) lives as module-level
singletons in `modules/config/settings.py`. Because these are **mutable and imported by
reference**, mutation is visible across modules. Scalar flags (such as the cancellation
flag) are accessed **only** through accessor functions — `request_cancel()`,
`reset_cancel()`, and `is_cancel_requested()` — so a signal from the API thread is reliably
seen by the download worker thread.

### Request flow

```
Browser / WebView  ──HTTP──▶  Flask (api.py, ui.py)
                                  │
                                  ▼
                      start_download_thread()  ──▶  worker thread
                                  │                     │
                                  ▼                     ▼
                          current_download  ◀──  yt-dlp + progress_hook
                          (polled via /api/download-status)
```

---

## 📁 Project Structure

```
linux-media-downloader/
├── app.py                     # Entry point: native PyWebView window
├── browser_app.py             # Entry point: browser fallback (Flask :5000)
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Dev/test dependencies (pytest, pyflakes)
├── modules/
│   ├── config/settings.py     # Config, shared state, history, cancel helpers
│   ├── download/media.py      # yt-dlp orchestration, progress hook, worker thread
│   ├── routes/api.py          # JSON API blueprint (/api/*)
│   ├── routes/ui.py           # Page-rendering blueprint (/, /backups, …)
│   └── utils/file_utils.py    # Filename sanitization, open-folder
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS and JS assets
├── data/download_history.json # Persisted history (last 100)
├── tests/test_app.py          # Offline unit + route tests
└── AppDir/                    # AppImage packaging staging tree
```

---

## ⚙️ Requirements

- **Python 3.8+**
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)
- [`Flask`](https://flask.palletsprojects.com/)
- [`pywebview`](https://pywebview.flowrl.com/) *(native window only)*
- [`ffmpeg`](https://ffmpeg.org/) on your `PATH` *(required for audio extraction / merging)*

> **Running as a standalone app window (not a browser):** `python3 app.py` opens the UI in a
> native PyWebView window — its own title bar and taskbar icon, no browser chrome. PyWebView
> needs a GUI backend installed:
> - **Linux (GTK):** `sudo apt install python3-gi gir1.2-webkit2-4.1 libgirepository1.0-dev`
> - **Linux (Qt) alternative:** `pip install "pywebview[qt]"`
> - **Windows:** Edge WebView2 (preinstalled on Win 10/11).
>
> On a headless machine (no display) use the browser fallback: `python3 browser_app.py` →
> open `http://127.0.0.1:5000`. Packaged builds (see [docs/packaging.md](docs/packaging.md))
> bundle the backend so end users get the standalone window with no setup.

**Add it to the Linux Mint / Cinnamon program menu** (per-user, no root), with its own icon:

```bash
./packaging/install-menu.sh              # adds "Linux Media Downloader" to the menu
./packaging/install-menu.sh --uninstall  # remove it
```
It launches `app.py` as a native window (min/maximize/close controls); closing exits the app.

---

## 📦 Installation

> Quick start below. For **full Linux + Windows setup** (system deps, GUI backend, menu
> entry, Start-menu shortcut, troubleshooting) see **[INSTALL.md](INSTALL.md)**.

```bash
git clone https://github.com/MensuraMedia/linux-media-downloader.git
cd linux-media-downloader

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt   # runtime only
# or, for development:
pip install -r requirements-dev.txt
```

Install `ffmpeg` via your system package manager, e.g.:

```bash
sudo apt install ffmpeg           # Debian/Ubuntu/Mint
```

---

## ▶️ Running the App

**Native desktop window:**

```bash
python3 app.py
```

**Browser mode** (no GUI toolkit required — good for servers/headless):

```bash
python3 browser_app.py
# then open http://127.0.0.1:5000
```

Flask binds only to `127.0.0.1` (localhost); the app is not exposed to your network.

---

## 🖱️ Usage

1. Paste a YouTube **video or playlist URL**.
2. Choose **Audio** (MP3) or **Video** (MP4).
3. Choose **Single** (just the video) or **Playlist** (all videos).
4. Pick a **download folder** (defaults to your XDG Downloads directory).
5. Click **Download** — watch live progress; **Cancel** stops it cleanly.
6. Use **Open Folder** to reveal your files, and the **Backups/History** tab to review
   past downloads.

### JSON API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/check-url` | Detect whether a URL is a single video or a playlist |
| `GET`  | `/api/get-default-path` | Return the default download directory |
| `POST` | `/api/download` | Start a download in a background thread |
| `POST` | `/api/cancel-download` | Signal the active download to stop |
| `GET`  | `/api/download-status` | Poll current download status/progress |
| `GET`  | `/api/links-history` | Return submitted-links history, newest first |
| `POST` | `/api/clear-links-history` | Clear the links history |
| `GET`  | `/api/playlists` | List downloaded playlists (folders with >1 track) |
| `POST` | `/api/playlist-files` | List a playlist's files (length / name / size) |
| `POST` | `/api/rename-playlist` | Rename a playlist folder |
| `POST` | `/api/playlist-operation` | Bulk file op (delete_long / clean / remove_special / replace_spaces / number_prefix) |
| `POST` | `/api/open-folder` | Open a folder in the system file manager |

`/api/download` also accepts `skip_long: true` to skip tracks over 7 minutes.

Pages: `/` (Home), `/backups` (History), `/playlists` (Playlists), `/links` (Links), `/about`.

---

## 🔧 Configuration

| Setting | How | Default |
|---------|-----|---------|
| Flask secret key | `SECRET_KEY` env var | random per run (`os.urandom`) |
| Download folder | Selected in UI / `output_dir` in `/api/download` | XDG Downloads → `~/Downloads` → `<data dir>/downloads` |
| Data folder | `LMD_DATA_DIR` env var | `~/.local/share/linmediadownloader` (`$XDG_DATA_HOME`) |
| History file | `<data dir>/download_history.json` | last 100 entries |
| Audio codec/quality | `modules/download/media.py` | MP3 @ 192 kbps |

```bash
# Optional: pin a stable secret key
export SECRET_KEY="your-own-secret"
python3 browser_app.py
```

---

## 🧪 Development & Testing

The test suite is **offline** — it never performs a real download.

```bash
pip install -r requirements-dev.txt

pytest -q                # run the suite (15 tests)
pyflakes modules tests   # lint for unused imports / undefined names
```

Tests cover filename sanitization, the cancellation wiring (including an end-to-end HTTP
cancel through the Flask test client), the progress hook's completion/abort paths,
secret-key hygiene, and the `/api/*` routes.

> **Note:** When changing runtime code, keep the `AppDir/usr/bin/` copy in sync with the
> top-level sources — it is what an AppImage build ships.

---

## 🖥️ AppImage Packaging (Linux)

The `AppDir/` tree stages the app for packaging as a portable **AppImage** for Debian,
Ubuntu, Mint, and similar distributions.

**Recommended storage location:** keep the built AppImage in `~/Applications` (create the
folder if needed) to keep user-level apps organized.

> **Build a .deb** (Debian/Ubuntu/Mint): `./packaging/build-deb.sh` → install with
> `sudo apt install ./dist/linux-media-downloader_1.0.0_all.deb`.
>
> **Full packaging guide** — Linux (pipx-from-git, AppImage, .deb, Flatpak) and Windows
> (PyInstaller): see [docs/packaging.md](docs/packaging.md).

---

## 🛣️ Roadmap

> **This product is still evolving.** It's under active development and grows over time —
> features are added and refined based on real use. The full, categorized roadmap (shipped /
> designed / planned / ideas) lives in **[ROADMAP.md](ROADMAP.md)**.

Next up: **2.0, a native GTK 4 rewrite** — see the
[mockups](docs/design/mockups-gtk4/README.md). Also coming: packaged installers (AppImage / .deb / Windows `.exe`),
one-line `pipx` install, YouTube cookie support, more sources (Vimeo, SoundCloud), and CI. See [ROADMAP.md](ROADMAP.md) for the rest.

---

## 🤝 Contributing

Contributions are welcome — please open an issue or pull request to discuss ideas.
Run `pytest` and `pyflakes` before submitting, and keep the `AppDir/` copy in sync.

---

## 🚫 License

Free for personal, educational, or non-commercial use only.
**Commercial use is strictly prohibited without prior written permission.**
See [LICENSE](LICENSE) for details.

---

## 📢 Disclaimer

This project is not affiliated with YouTube or any other media provider. Please respect the
terms of service of every platform you use with this tool, and only download content you
are legally permitted to.
