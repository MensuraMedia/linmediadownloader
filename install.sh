#!/usr/bin/env bash
#
# LinMediaDownloader 2.0 — installer for Debian / Ubuntu / Linux Mint (GTK 4).
#
#   One command (downloads the code for you):
#     curl -fsSL https://raw.githubusercontent.com/MensuraMedia/linmediadownloader/feat/2.0-gtk4/install.sh | bash
#
#   From a checkout (installs that checkout in place, for development):
#     ./install.sh
#
# Installs the system packages (Python, GTK 4, ffmpeg, GStreamer), the app's own Python
# environment (yt-dlp with its YouTube solver, and Deno as the JS runtime), then adds
# LinMediaDownloader to the program menu with its icon. Re-run to update.
#
#   Uninstall:  bash ~/.local/opt/linmediadownloader/install.sh --uninstall
#               (your downloads, settings and history are kept)
#
# Environment: LMD_DIR (install folder), LMD_BRANCH (git branch), LMD_REPO (git URL),
#              LMD_SKIP_APT=1 (skip apt).
#
set -euo pipefail

APP_NAME="LinMediaDownloader"
REPO_URL="${LMD_REPO:-https://github.com/MensuraMedia/linmediadownloader.git}"
# 2.0 lives on this branch until it is merged into main (then: main)
BRANCH="${LMD_BRANCH:-feat/2.0-gtk4}"
DEFAULT_DIR="$HOME/.local/opt/linmediadownloader"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/linmediadownloader"
MARKER=".lmd-installer-clone"  # marks a folder this installer cloned (safe to delete on uninstall)

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mNote:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

# Run from a checkout (./install.sh) → use it in place; piped from curl → clone/update LMD_DIR
SELF_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
if [ -n "${LMD_DIR:-}" ]; then
    INSTALL_DIR="$LMD_DIR"
elif [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/linmediadownloader.py" ]; then
    INSTALL_DIR="$SELF_DIR"
else
    INSTALL_DIR="$DEFAULT_DIR"
fi

# ── Uninstall ─────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--uninstall" ]; then
    say "Removing the menu entry and icon…"
    if [ -x "$INSTALL_DIR/packaging/install-menu.sh" ]; then
        "$INSTALL_DIR/packaging/install-menu.sh" --uninstall || true
    fi
    if [ -f "$INSTALL_DIR/$MARKER" ]; then
        say "Deleting $INSTALL_DIR …"
        rm -rf "$INSTALL_DIR"
    else
        say "Keeping $INSTALL_DIR (a checkout you made yourself; delete it by hand if you like)."
    fi
    say "Uninstalled. Your downloads and $DATA_DIR were not touched."
    exit 0
fi
[ -z "${1:-}" ] || die "Unknown option: $1 (use --uninstall, or no option to install/update)"

# ── Preconditions ─────────────────────────────────────────────────────────────
command -v apt-get >/dev/null || [ "${LMD_SKIP_APT:-}" = 1 ] || \
    die "This installer targets Debian/Ubuntu/Mint (apt-get not found). See INSTALL.md for other systems."
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null; then SUDO="sudo"; else [ "${LMD_SKIP_APT:-}" = 1 ] || die "Need sudo to install system packages."; fi
fi

# ── 1. System packages ────────────────────────────────────────────────────────
if [ "${LMD_SKIP_APT:-}" != 1 ]; then
    say "Installing system packages (may ask for your password)…"
    $SUDO apt-get update -qq
    $SUDO apt-get install -y --no-install-recommends \
        git python3 python3-venv python3-pip python3-gi python3-gi-cairo \
        gir1.2-gtk-4.0 librsvg2-common ffmpeg
    # Nice to have: playback in the Library (GStreamer) and the Ubuntu font. Installed when
    # this release has them; the app works without them.
    for pkg in libgtk-4-media-gstreamer gstreamer1.0-plugins-good fonts-ubuntu; do
        if apt-cache show "$pkg" >/dev/null 2>&1; then
            $SUDO apt-get install -y --no-install-recommends "$pkg" || warn "could not install $pkg (optional)"
        else
            warn "$pkg is not available on this release (optional)"
        fi
    done
fi

# ── 2. The code ───────────────────────────────────────────────────────────────
if [ "$INSTALL_DIR" = "${SELF_DIR:-}" ] && [ ! -f "$INSTALL_DIR/$MARKER" ]; then
    # your own checkout: install it as it is (no pull, so your work is never touched)
    say "Installing the checkout at $INSTALL_DIR in place…"
elif [ -d "$INSTALL_DIR/.git" ]; then
    say "Updating $INSTALL_DIR …"
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH" && \
        git -C "$INSTALL_DIR" checkout -q -B "$BRANCH" FETCH_HEAD || warn "could not update; keeping the current code"
else
    say "Downloading $APP_NAME ($BRANCH) into $INSTALL_DIR …"
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    touch "$INSTALL_DIR/$MARKER"
fi
[ -f "$INSTALL_DIR/linmediadownloader.py" ] || die "$INSTALL_DIR does not hold LinMediaDownloader 2.0 (linmediadownloader.py missing)."

# ── 3. The app's Python environment ───────────────────────────────────────────
say "Setting up the Python environment (yt-dlp, Deno)…"
# --system-site-packages: GTK 4 comes through the system's PyGObject (python3-gi), which
# pip cannot install. The venv and the system Python are the same build.
python3 -m venv --system-site-packages "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade --disable-pip-version-check pip
# -U: the venv sees system packages, and a distro's old yt-dlp would otherwise count as installed
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade --disable-pip-version-check -r "$INSTALL_DIR/requirements.txt"

# Check before claiming success, so a broken environment fails here and not at launch
say "Checking GTK 4, yt-dlp and Deno…"
"$INSTALL_DIR/venv/bin/python" - <<'PY' || die "The environment check failed (see above)."
import shutil, subprocess, sys, os
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
if (Gtk.get_major_version(), Gtk.get_minor_version()) < (4, 10):
    sys.exit(f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()} is too old (4.10 or newer needed)")
import yt_dlp
deno = os.path.join(os.path.dirname(sys.executable), "deno")
version = subprocess.run([deno, "--version"], capture_output=True, text=True).stdout.split("\n")[0]
print(f"   GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()} · yt-dlp {yt_dlp.version.__version__} · {version}"
      f" · ffmpeg {'found' if shutil.which('ffmpeg') else 'MISSING'}")
PY

# ── 4. Program menu + icon ────────────────────────────────────────────────────
say "Adding $APP_NAME to your program menu…"
chmod +x "$INSTALL_DIR/packaging/install-menu.sh" "$INSTALL_DIR/install.sh"
"$INSTALL_DIR/packaging/install-menu.sh" >/dev/null

# A 1.x install stays where it is; say how to remove it so the menu has one downloader
if [ -d "$HOME/.local/share/linux-media-downloader/.git" ]; then
    warn "The old 1.x app is still installed. Remove it with:"
    warn "  bash ~/.local/share/linux-media-downloader/install.sh --uninstall"
    warn "(2.0 has already copied its history and settings.)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
cat <<EOF

✅ Installed $APP_NAME $(cat "$INSTALL_DIR/VERSION" 2>/dev/null || echo 2.0).

  • Start it from your program menu ("$APP_NAME"), or run:
        $INSTALL_DIR/venv/bin/python $INSTALL_DIR/linmediadownloader.py
  • Downloads go to ~/Music/LinMediaDownloads (change it in Settings).
  • Update:     bash $INSTALL_DIR/install.sh
  • Uninstall:  bash $INSTALL_DIR/install.sh --uninstall
EOF
