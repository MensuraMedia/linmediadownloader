#!/usr/bin/env python3
# modules/config/paths.py
# Every on-disk location the app uses, in one place.
#
# User data lives in the XDG data directory (~/.local/share/linmediadownloader),
# never relative to the current directory: before 2.0 the app wrote data/,
# logs/ and downloads/ wherever it was launched from, so a menu launch and a
# terminal launch kept separate histories. Code and data are now separate too,
# so reinstalling or uninstalling the app never touches the user's data.
#
# Overrides (tests, development):
#   LMD_DATA_DIR    use this directory instead of the XDG one
#   LMD_NO_MIGRATE  set to skip copying 1.x data files on first run

import os
import json
import shutil
import logging
from datetime import datetime

logger = logging.getLogger('lmd.paths')

APP_ID = 'linmediadownloader'

# Code root (the folder holding app.py); 1.x kept data/ here when launched from it.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _data_home():
    override = os.environ.get('LMD_DATA_DIR')
    if override:
        return os.path.abspath(os.path.expanduser(override))
    xdg = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
    return os.path.join(xdg, APP_ID)


DATA_DIR = _data_home()
LOG_DIR = os.path.join(DATA_DIR, 'logs')
# Last-resort download folder, used only when the user has no Downloads folder.
FALLBACK_DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')

# Every JSON file the app persists (1.x kept the same names under data/).
DATA_FILES = (
    'download_history.json',
    'links_history.json',
    'app_settings.json',
    'download_manifest.json',
    'playlist_colors.json',
    'playlist_seq.json',
)

MIGRATION_MARKER = os.path.join(DATA_DIR, 'migrated-from-1.x.json')


def data_file(name):
    """Absolute path of a persisted data file."""
    return os.path.join(DATA_DIR, name)


def legacy_roots():
    """Folders where 1.x may have kept data/ and downloads/, most likely first.

    1.x resolved them against the working directory: the deb and install.sh
    launchers cd'd into ~/.local/share/linux-media-downloader, the menu entry
    from install-menu.sh into the code folder, and a terminal launch anywhere.
    """
    xdg = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
    roots = [os.path.join(xdg, 'linux-media-downloader'), BASE_DIR, os.getcwd()]
    seen, out = set(), []
    for r in roots:
        r = os.path.realpath(r)
        if r not in seen and r != os.path.realpath(DATA_DIR):
            seen.add(r)
            out.append(r)
    return out


def legacy_download_dirs():
    """Existing 1.x ./downloads folders, so the Library still finds old files."""
    return [d for d in (os.path.join(r, 'downloads') for r in legacy_roots()) if os.path.isdir(d)]


def _newest_legacy_copy(name):
    """The most recently modified 1.x copy of a data file, or None."""
    found = [p for p in (os.path.join(r, 'data', name) for r in legacy_roots()) if os.path.isfile(p)]
    return max(found, key=os.path.getmtime) if found else None


def migrate_legacy_data():
    """Copy 1.x data files into DATA_DIR once. Never moves or deletes the originals.

    A file already present in DATA_DIR always wins. Returns {name: source path}
    for the files copied this call.
    """
    if os.environ.get('LMD_NO_MIGRATE') or os.path.exists(MIGRATION_MARKER):
        return {}
    copied = {}
    for name in DATA_FILES:
        target = data_file(name)
        if os.path.exists(target):
            continue
        src = _newest_legacy_copy(name)
        if not src:
            continue
        try:
            with open(src) as f:
                json.load(f)  # never carry a corrupt file forward
            shutil.copy2(src, target)
            copied[name] = src
        except Exception as e:
            logger.warning('Not migrating %s: %s', src, e)
    try:
        with open(MIGRATION_MARKER, 'w') as f:
            json.dump({'at': datetime.now().isoformat(timespec='seconds'), 'copied': copied}, f, indent=2)
    except OSError as e:
        logger.error('Could not write migration marker: %s', e)
    if copied:
        logger.info('Copied %d data file(s) from 1.x: %s', len(copied), ', '.join(sorted(copied)))
    return copied


def prepare():
    """Create the data folders and run the one-time 1.x migration."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    migrate_legacy_data()


prepare()
