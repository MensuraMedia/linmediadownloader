# Packaging & Distribution Guide

> **2.0 (GTK 4):** use `install.sh`, `clone-and-install.sh` or `packaging/build-deb.sh` — see the
> [README](../README.md#-install). This guide describes **1.x** (Flask + PyWebView), kept on `release/1.x`.

How to turn Linux Media Downloader into an installable desktop application for **Linux**
and **Windows**. Grounded in the current repo (there is already a partial `AppDir/` AppImage
scaffold and a `.desktop` file).

---

## 0. It is already a desktop app

`app.py` runs the UI in a **native PyWebView window** — that is the desktop application
(`browser_app.py` is the headless/browser fallback). "Packaging" is about letting people
**install and launch it** without manually installing Python and dependencies.

Every route below wraps the same two runtime needs:
- **Python 3.8+** with `Flask`, `yt-dlp`, `pywebview` (+ a PyWebView GUI backend:
  GTK/Qt/WebKit on Linux, EdgeWebView2 on Windows).
- **ffmpeg / ffprobe** on `PATH` — used for audio extraction, chapter splitting, and
  duration reads. **System-Python routes must declare it; self-contained routes must bundle it.**

---

## 1. Current scaffold & its gaps

```
AppDir/
├── usr/bin/…                 # a full copy of the app (kept in sync with the source)
└── usr/share/applications/linux-media-downloader.desktop
```

`linux-media-downloader.desktop`:
```ini
[Desktop Entry]
Name=Linux Media Downloader
Exec=python3 /usr/bin/app.py
Icon=linux-media-downloader
Type=Application
Categories=AudioVideo;Utility;
```

**Gaps to close before it builds:**
- No **`AppRun`** entry script (AppImage requires it).
- No **icon** file (`.desktop` references `linux-media-downloader` but none is shipped).
- `Exec=python3 /usr/bin/app.py` assumes a system Python and absolute path — won't work
  inside an AppImage sandbox; should call the bundled interpreter / `AppRun`.
- No **bundled Python or ffmpeg** — the AppImage would still depend on the host.
- Committed **`__pycache__`** under `AppDir/usr/bin/` should be removed and git-ignored.

---

## 1b. Add it to the program menu (Linux Mint / Cinnamon) — no packaging needed

You can make the app appear in the Mint menu against your current checkout, launchable and
closeable like any other app, with its own icon — without building a package:

```bash
./packaging/install-menu.sh        # install (per-user, no root)
./packaging/install-menu.sh --uninstall
```

What it does:
- Writes `~/.local/share/applications/linux-media-downloader.desktop` pointing at this repo's
  `app.py` (using `venv/bin/python` if a venv exists, else system `python3`).
- Installs the icon (`packaging/linux-media-downloader.svg`, the Heroicons "window" glyph on
  the app-blue tile) into `~/.local/share/icons/hicolor/scalable/apps/`.
- Refreshes the desktop/icon caches.

Then search **"Linux Media Downloader"** in the Mint menu (right-click → *Add to panel* /
*Add to desktop* to pin it). Launching runs `app.py`, which opens the **native PyWebView
window** with normal min/maximize/close controls; closing the window exits the app (and saves
history via the `atexit` hook). The window's taskbar icon association uses `StartupWMClass`;
if Cinnamon shows a generic icon there, log out/in once so the new `.desktop` is indexed.

> Requires a PyWebView GUI backend (see README Requirements) and `ffmpeg`. This per-user
> launcher is for a dev/source checkout; the packaged routes below install the menu entry
> and icon system-wide automatically.

## 2. Linux — routes by effort

### 2A. pipx / pip from git  ← simplest "install from git"

Add packaging metadata and a console entry point, then anyone installs with one line.

`pyproject.toml` (new):
```toml
[project]
name = "linux-media-downloader"
version = "1.0.0"
requires-python = ">=3.8"
dependencies = ["Flask", "yt-dlp", "pywebview"]

[project.scripts]
mbs = "app:main"        # `mbs` on PATH launches the native window

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"
```

Install / run:
```bash
pipx install git+https://github.com/MensuraMedia/linux-media-downloader.git
mbs
```
- ✅ Trivial for the user; updates via `pipx upgrade`.
- ⚠️ Requires system Python, a PyWebView GUI backend, and **ffmpeg** (`sudo apt install ffmpeg`).
- Needs `MANIFEST.in`/package-data config so `templates/` and `static/` ship with the wheel
  (or move them under a package dir).

### 2B. AppImage  ← single portable download, no install

A one-file executable the user downloads, marks executable, and runs — the classic
"download from git Releases and run" experience.

Steps:
1. Fix the scaffold (§1): add `AppRun`, an icon (`linux-media-downloader.png` at AppDir root),
   correct the `.desktop` `Exec`.
2. Bundle Python + deps into `AppDir` (e.g. `linuxdeploy` + its `python` plugin — already
   named in `.gitignore`), and drop a **static ffmpeg** binary into `AppDir/usr/bin/`.
3. Build:
   ```bash
   ./linuxdeploy-x86_64.AppImage --appdir AppDir \
       --desktop-file AppDir/usr/share/applications/linux-media-downloader.desktop \
       --icon-file linux-media-downloader.png --output appimage
   ```
4. Ship `Linux_Media_Downloader-x86_64.AppImage` on the GitHub **Releases** page.

Minimal `AppRun`:
```bash
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$PATH"     # bundled ffmpeg
exec "$HERE/usr/bin/python3" "$HERE/usr/bin/app.py" "$@"
```
- ✅ No install, portable across distros; store in `~/Applications`.
- ⚠️ Largest artifact; must bundle a GUI/WebKit backend for PyWebView.

### 2C. .deb package  ← standard Debian/Ubuntu/Mint install  ✅ IMPLEMENTED

**Build it:**
```bash
./packaging/build-deb.sh        # → dist/linux-media-downloader_1.0.0_all.deb
sudo apt install ./dist/linux-media-downloader_1.0.0_all.deb
```

What the package does (`packaging/build-deb.sh`):
- Installs the app under `/opt/linux-media-downloader`, adds `/usr/bin/linux-media-downloader`
  (a launcher that runs the app but keeps user data under
  `~/.local/share/linux-media-downloader`), a menu entry, and the icon.
- `Depends:` `python3 (>=3.8), python3-venv, python3-pip, ffmpeg, python3-gi,
  python3-gi-cairo, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0` — so `apt` pulls ffmpeg and the
  WebKit GUI backend automatically.
- **postinst** creates a venv (`--system-site-packages`, so PyGObject/WebKit come from apt)
  and `pip install`s `Flask`, `yt-dlp`, `pywebview` — keeping `yt-dlp` current instead of a
  stale apt version. **prerm** removes that venv on uninstall.
- Architecture `all` (pure Python). Build artifacts land in `build/` and `dist/` (git-ignored);
  publish the `.deb` on the GitHub **Releases** page.

- ✅ Feels native; menu integration + dependency resolution via `apt`.
- ⚠️ postinst needs network (to pip-install yt-dlp/pywebview) and Debian-family only.

### 2D. Flatpak / Snap  ← sandboxed, cross-distro, auto-updating

A `flatpak` manifest or `snapcraft.yaml` builds a sandboxed bundle publishable to Flathub /
Snap Store with automatic updates. Most robust distribution, most build overhead; the sandbox
needs explicit filesystem permission for the user's download folder.

---

## 3. Windows

**PyInstaller** freezes the app into a standalone `.exe`:
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "MediaBackupSystem" \
    --add-data "templates;templates" --add-data "static;static" \
    --add-binary "ffmpeg.exe;." app.py
```
- Produces `dist/MediaBackupSystem.exe` — no Python needed on the target.
- PyWebView uses the **Edge WebView2** runtime (present on Win10/11).
- Bundle `ffmpeg.exe` (via `--add-binary`) so splitting/extraction works offline.
- Optional: wrap with **Inno Setup** or **NSIS** for a Start-menu installer + uninstaller.
- `cx_Freeze` is an alternative if PyInstaller antivirus false-positives are a problem.

---

## 4. Recommendation

| Goal | Use |
|------|-----|
| Fastest "install from git" for technical users | **2A – pipx** |
| A downloadable file that "just runs" on any Linux | **2B – AppImage** (finish the scaffold) |
| Feels native on Ubuntu/Mint, menu integration | **2C – .deb** |
| Store presence + auto-updates | **2D – Flatpak** |
| Windows | **PyInstaller** (+ Inno Setup for an installer) |

A practical rollout: **pipx (2A)** first (cheapest, immediately usable), then **AppImage (2B)**
for a friendly Releases download, then **.deb (2C)** for Debian-family menus. All three can
publish from the same GitHub Releases page.

---

## 5. Cross-cutting checklist

- [ ] Bundle or declare **ffmpeg/ffprobe** (every route).
- [ ] Ship a **PyWebView GUI backend** (GTK/Qt/WebKit on Linux; WebView2 on Windows).
- [ ] Keep **`yt-dlp` current** — it breaks often against YouTube; prefer pip over distro pkgs,
      and consider a self-update or a "yt-dlp version" note in About.
- [ ] Anchor **runtime data** to a fixed app-data dir (`~/.local/share/linux-media-downloader`)
      instead of the cwd, so an installed app doesn't scatter `data/`, `downloads/` (already
      flagged in the roadmap).
- [ ] Add an **icon** asset; remove committed `__pycache__` from `AppDir/`.
- [ ] Automate builds in **GitHub Actions** → attach artifacts to Releases.
