# Installation & Setup

## LinMediaDownloader 2.0 (GTK 4) — Linux

The quick ways (one command, `.deb`, clone and install) are at the top of the
**[README](README.md#-install)**. This section is the manual route, for other distributions or
when you want to see every step.

**Needs:** Python 3.10+, GTK 4.10+ with PyGObject, ffmpeg. Optional: GStreamer for playback in
the Library, the Ubuntu font.

| Distribution | System packages |
|---|---|
| Debian / Ubuntu / Mint | `sudo apt install git python3-venv python3-gi python3-gi-cairo gir1.2-gtk-4.0 librsvg2-common ffmpeg libgtk-4-media-gstreamer gstreamer1.0-plugins-good fonts-ubuntu` |
| Fedora | `sudo dnf install git python3-gobject gtk4 librsvg2 ffmpeg-free gstreamer1-plugins-good` |
| Arch | `sudo pacman -S git python-gobject gtk4 librsvg ffmpeg gst-plugins-good` |

(The Fedora and Arch lines are untested; the installers support Debian-based systems.)

```bash
git clone --branch feat/2.0-gtk4 https://github.com/MensuraMedia/linmediadownloader.git
cd linmediadownloader
python3 -m venv --system-site-packages venv     # GTK comes from the system's PyGObject
venv/bin/pip install -U -r requirements.txt     # yt-dlp (+ its YouTube solver) and Deno
venv/bin/python linmediadownloader.py           # start it
./packaging/install-menu.sh                     # optional: program menu entry + icon
```

`-U` matters: the venv sees system packages, and an old distro yt-dlp would otherwise count as
installed. Windows is not supported by 2.0 (GTK 4 app for Linux); use 1.x there.

---

## 1.x (Flask + web view)

The rest of this file describes **1.x**, kept as tag `v1.0.0` and branch `release/1.x`.

How to install and run **Linux Media Downloader** 1.x as a desktop application on **Linux** and
**Windows**. For turning it into a distributable package (AppImage, .deb, Windows installer),
see [docs/packaging.md](docs/packaging.md). For what's coming next, see [ROADMAP.md](ROADMAP.md).

---

## What you need (all platforms)

| Requirement | Why |
|-------------|-----|
| **Python 3.8+** | Runs the app |
| **`Flask`, `yt-dlp`, `pywebview`** | Web server, downloader, native window (`requirements.txt`) |
| **A PyWebView GUI backend** | Renders the native window (see per-OS below) |
| **`ffmpeg` / `ffprobe` on PATH** | Audio extraction, chapter splitting, durations |

Two ways to run:
- **`python3 app.py`** → native desktop **window** (own title bar/controls, no browser).
- **`python3 browser_app.py`** → headless fallback at `http://127.0.0.1:5000` (servers / no display).

---

## Linux

### 1. Install system dependencies

**Debian / Ubuntu / Linux Mint:**
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg \
                 python3-gi gir1.2-webkit2-4.1 libgirepository1.0-dev
```
(The last three provide the GTK/WebKit backend PyWebView needs. Alternatively use Qt:
`pip install "pywebview[qt]"`.)

**Fedora:**
```bash
sudo dnf install python3 python3-pip ffmpeg python3-gobject webkit2gtk4.1
```

**Arch:**
```bash
sudo pacman -S python python-pip ffmpeg python-gobject webkit2gtk
```

### 2. Get the code and install Python deps

```bash
git clone https://github.com/MensuraMedia/linux-media-downloader.git
cd linux-media-downloader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt        # or requirements-dev.txt for tests
```

### 3. Run

```bash
python3 app.py            # native window
# or
python3 browser_app.py    # browser mode → http://127.0.0.1:5000
```

### 4. Add it to the program menu (Mint / Cinnamon / GNOME / XFCE)

```bash
./packaging/install-menu.sh              # per-user, no root; own icon
./packaging/install-menu.sh --uninstall  # remove
```
Then search **"Linux Media Downloader"** in the menu; pin it if you like. Launch opens the
native window; closing it exits the app.

---

## Windows

### 1. Install prerequisites

- **Python 3.8+** — [python.org](https://www.python.org/downloads/); at install time tick
  **"Add python.exe to PATH"**. (Or `winget install Python.Python.3.12`.)
- **Edge WebView2 runtime** — PyWebView's Windows backend. Preinstalled on Windows 10/11;
  if missing, install "Microsoft Edge WebView2 Runtime" (or `winget install Microsoft.EdgeWebView2Runtime`).
- **ffmpeg** — must be on `PATH`:
  ```powershell
  winget install Gyan.FFmpeg        # or:  choco install ffmpeg
  ```
  Verify in a new terminal: `ffmpeg -version`.

### 2. Get the code and install Python deps

```powershell
git clone https://github.com/MensuraMedia/linux-media-downloader.git
cd linux-media-downloader
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run

```powershell
python app.py            # native window
# or
python browser_app.py    # browser mode → http://127.0.0.1:5000
```

### 4. Make a Start-menu / desktop shortcut

Create a shortcut so it launches like any Windows app (no terminal window):

1. Right-click the desktop → **New → Shortcut**.
2. Location (adjust the path to your checkout):
   ```
   "C:\path\to\linux-media-downloader\venv\Scripts\pythonw.exe" "C:\path\to\linux-media-downloader\app.py"
   ```
   Using **`pythonw.exe`** (not `python.exe`) launches with **no console window**.
3. Name it **Linux Media Downloader**, Finish.
4. Right-click the shortcut → **Properties**:
   - **Start in:** `C:\path\to\linux-media-downloader`
   - **Change Icon…** → browse to a `.ico` (convert `packaging/linux-media-downloader.svg`
     to `.ico`, e.g. via an online converter or ImageMagick `magick`), or keep the default.
5. Copy the shortcut into
   `%AppData%\Microsoft\Windows\Start Menu\Programs` so it appears in the Start menu.

> For a proper double-click installer (no Python/terminal at all), build a standalone `.exe`
> with PyInstaller — see [docs/packaging.md](docs/packaging.md) §3.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `app.py` errors about GTK/WebKit/no backend | Install the GUI backend (Linux §1) or `pip install "pywebview[qt]"`; on Windows install WebView2. |
| Downloads fail / "Sign in to confirm you're not a bot" | YouTube rate-limits some IPs; pass browser cookies (yt-dlp `--cookies-from-browser`) — planned as a UI option. |
| Audio won't convert / split does nothing | `ffmpeg` not on PATH — install it and reopen the terminal. |
| Downloads stop working after a while | Update yt-dlp: `pip install -U yt-dlp` (it changes often against YouTube). |
| No window on a server / SSH session | No display — use `python3 browser_app.py` and open the URL. |

---

## Running the tests (optional)

```bash
pip install -r requirements-dev.txt
pytest -q          # offline test suite
pyflakes modules tests
```
