#!/bin/bash
#
# install-menu.sh — add LinMediaDownloader (2.0, GTK 4) to the application menu
# (Linux Mint / Cinnamon, GNOME, XFCE — any XDG-compliant desktop).
#
# Per-user install (no root). Points the launcher at THIS checkout and uses its
# venv's python if one exists, otherwise system python3. Installs the app icon under
# the app id, so the menu, the panel and the Alt+Tab switcher all show it: the
# window's class and GTK application id are the same id (see ui/app.py).
#
# Usage:   ./packaging/install-menu.sh
# Remove:  ./packaging/install-menu.sh --uninstall

set -euo pipefail

APP_ID="org.mensuramedia.LinMediaDownloader"
APP_NAME="LinMediaDownloader"

# Repo root = parent of this script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DESKTOP_DIR="$HOME/.local/share/applications"
ICON_ROOT="$HOME/.local/share/icons/hicolor"
ICON_DIR="$ICON_ROOT/scalable/apps"
DESKTOP_FILE="$DESKTOP_DIR/$APP_ID.desktop"
ICON_FILE="$ICON_DIR/$APP_ID.svg"
ICON_SRC="$REPO_DIR/resources/icons/hicolor/scalable/apps/$APP_ID.svg"

refresh_caches() {
    command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP_DIR" || true
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -fv "$DESKTOP_FILE" "$ICON_FILE"
    refresh_caches
    echo "Removed $APP_NAME from the application menu."
    exit 0
fi

# Choose the interpreter: prefer the project venv, else system python3
if [ -x "$REPO_DIR/venv/bin/python" ]; then
    PYTHON="$REPO_DIR/venv/bin/python"
else
    PYTHON="$(command -v python3 || true)"
fi
[ -n "$PYTHON" ] || { echo "Error: python3 not found."; exit 1; }
[ -f "$ICON_SRC" ] || { echo "Error: icon not found at $ICON_SRC"; exit 1; }

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"
install -m 644 "$ICON_SRC" "$ICON_FILE"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Media Downloader
Comment=Download videos, music and playlists, and keep your library tidy
Exec=$PYTHON $REPO_DIR/linmediadownloader.py
Path=$REPO_DIR
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Video;GTK;
Keywords=youtube;download;media;music;video;playlist;mp3;
StartupNotify=true
StartupWMClass=$APP_ID
EOF

chmod 644 "$DESKTOP_FILE"
refresh_caches

echo "Installed '$APP_NAME' to the application menu."
echo "  launcher : $DESKTOP_FILE"
echo "  icon     : $ICON_FILE"
echo "  runs     : $PYTHON $REPO_DIR/linmediadownloader.py"
