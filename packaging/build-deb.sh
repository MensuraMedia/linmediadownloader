#!/usr/bin/env bash
#
# build-deb.sh — build the LinMediaDownloader 2.0 .deb (GTK 4).
#
#   ./packaging/build-deb.sh
#
# Produces dist/linmediadownloader_<version>_all.deb (version from ./VERSION).
#
# The package puts the app in /opt/linmediadownloader, a launcher in
# /usr/bin/linmediadownloader, and the menu entry + icon under the app id
# org.mensuramedia.LinMediaDownloader (so the panel and Alt+Tab show the icon).
# GTK 4, PyGObject and ffmpeg come from apt (Depends). yt-dlp and Deno change too
# often for apt, so postinst installs them into /opt/linmediadownloader/venv
# (--system-site-packages, for the system's PyGObject); that step needs a network
# connection. User data stays in ~/.local/share/linmediadownloader; downloads in
# ~/Music/LinMediaDownloads. Removing the package removes neither.
#
set -euo pipefail

PKG="linmediadownloader"
APP_ID="org.mensuramedia.LinMediaDownloader"
ARCH="all"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"
BUILD_DIR="$REPO_DIR/build/deb"
ROOT="$BUILD_DIR/$PKG"
APP_DIR="$ROOT/opt/$PKG"
DIST="$REPO_DIR/dist"

echo "==> Cleaning build tree"
rm -rf "$BUILD_DIR"
mkdir -p "$APP_DIR" "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/doc/$PKG" "$DIST"

echo "==> Copying the 2.0 application (no 1.x web UI: routes, templates, static)"
for item in linmediadownloader.py VERSION requirements.txt modules ui lintheme resources; do
    cp -r "$REPO_DIR/$item" "$APP_DIR/"
done
rm -rf "$APP_DIR/modules/routes"
find "$APP_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$APP_DIR" -name '*.pyc' -delete
find "$APP_DIR" -type d -exec chmod 755 {} +
find "$APP_DIR" -type f -exec chmod 644 {} +
cp "$REPO_DIR/LICENSE.md" "$ROOT/usr/share/doc/$PKG/copyright"
cp "$REPO_DIR/README.md" "$ROOT/usr/share/doc/$PKG/README.md"

INSTALLED_KB=$(du -sk "$ROOT" | cut -f1)

echo "==> DEBIAN/control"
cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: sound
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-venv, python3-pip, python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, librsvg2-common, ffmpeg
Recommends: libgtk-4-media-gstreamer, gstreamer1.0-plugins-good, fonts-ubuntu
Installed-Size: $INSTALLED_KB
Maintainer: MensuraMedia <mensuramedia@gmail.com>
Homepage: https://github.com/MensuraMedia/linmediadownloader
Description: Download music, videos and playlists, and keep your library tidy
 LinMediaDownloader is a native GTK 4 desktop app built on yt-dlp. Paste a link
 to a video or playlist to save it as MP3 or MP4, split long videos into their
 chapters, skip long files and ones you already have, then play, rename and
 tidy the results in the Library. Uses your own browser's YouTube sign-in,
 found automatically. No accounts, no telemetry.
 .
 Installing runs pip to put yt-dlp and Deno in the app's own environment, so it
 needs a network connection.
EOF

echo "==> Launcher"
cat > "$ROOT/usr/bin/$PKG" <<EOF
#!/bin/sh
# Start LinMediaDownloader. Code in /opt; data in ~/.local/share/linmediadownloader.
exec /opt/$PKG/venv/bin/python /opt/$PKG/linmediadownloader.py "\$@"
EOF
chmod 755 "$ROOT/usr/bin/$PKG"

echo "==> Menu entry + icon"
cp "$REPO_DIR/resources/icons/hicolor/scalable/apps/$APP_ID.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cat > "$ROOT/usr/share/applications/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=LinMediaDownloader
GenericName=Media Downloader
Comment=Download videos, music and playlists, and keep your library tidy
Exec=$PKG
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Video;GTK;
Keywords=youtube;download;media;music;video;playlist;mp3;
StartupNotify=true
StartupWMClass=$APP_ID
EOF
chmod 644 "$ROOT/usr/share/applications/$APP_ID.desktop" "$ROOT/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"

echo "==> postinst: the app's Python environment"
cat > "$ROOT/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e
APP="/opt/$PKG"
if [ "\$1" = "configure" ]; then
    echo "Setting up LinMediaDownloader's Python environment (yt-dlp, Deno)…"
    python3 -m venv --system-site-packages "\$APP/venv"
    "\$APP/venv/bin/pip" install --quiet --disable-pip-version-check --upgrade pip || true
    # -U: the venv sees system packages; a distro's old yt-dlp must not count as installed
    if ! "\$APP/venv/bin/pip" install --quiet --disable-pip-version-check --upgrade -r "\$APP/requirements.txt"; then
        echo "Could not download yt-dlp/Deno (no network?). Run: sudo dpkg-reconfigure $PKG" >&2
        exit 1
    fi
    command -v update-desktop-database >/dev/null && update-desktop-database -q || true
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    echo "LinMediaDownloader is installed. Start it from your program menu."
fi
exit 0
EOF
chmod 755 "$ROOT/DEBIAN/postinst"

echo "==> prerm: remove the environment postinst made"
cat > "$ROOT/DEBIAN/prerm" <<EOF
#!/bin/sh
set -e
rm -rf /opt/$PKG/venv
find /opt/$PKG -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
exit 0
EOF
chmod 755 "$ROOT/DEBIAN/prerm"

echo "==> Building"
OUT="$DIST/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$ROOT" "$OUT" >/dev/null

echo
echo "✅ Built: $OUT"
echo "   Install:  sudo apt install ./$(realpath --relative-to="$PWD" "$OUT")"
echo "   Remove:   sudo apt remove $PKG   (downloads and settings are kept)"
