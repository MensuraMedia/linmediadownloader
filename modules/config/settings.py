#!/usr/bin/env python3
# modules/config/settings.py
# Configuration settings for YT Media Backup

import os
import logging

from modules.config import paths

logger = logging.getLogger('lmd.settings')

# App settings
# Prefer an externally provided key; fall back to a per-run random key.
# The app is localhost-only, but a hardcoded secret is still poor practice.
SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

# Get the system's Downloads folder path
def get_downloads_folder():
    """Get the path to the user's Downloads folder"""
    # Try to use the XDG_DOWNLOAD_DIR environment variable first
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config')
    xdg_user_dirs = os.path.join(xdg_config_home, 'user-dirs.dirs')
    
    if os.path.exists(xdg_user_dirs):
        with open(xdg_user_dirs, 'r') as f:
            for line in f:
                if line.startswith('XDG_DOWNLOAD_DIR'):
                    path = line.split('=')[1].strip().strip('"').replace('$HOME', os.path.expanduser('~'))
                    if os.path.exists(path):
                        return path
    
    # Fall back to ~/Downloads if it exists
    home_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    if os.path.exists(home_downloads):
        return home_downloads
    
    # Last resort: a downloads folder inside the app's data directory
    os.makedirs(paths.FALLBACK_DOWNLOADS_DIR, exist_ok=True)
    return paths.FALLBACK_DOWNLOADS_DIR

# Default download path
default_download_path = get_downloads_folder()

# Global state variables
download_history = []
current_download = {
    'output_path': '',
    'status': None, 
    'progress': 0,  # Individual file progress
    'total_progress': 0,  # Overall playlist progress
    'message': '',
    'current_file': '',
    'total_files': 0,
    'completed_files': 0,
    'is_playlist': False,
    'playlist_title': '',
    'selected_mode': 'single'
}

# Global control variables
download_thread = None
cancel_requested = False
window = None

# Download queue — jobs waiting to run (and finished ones, for the Pending page).
# Each job: {id, url, output_dir, download_type, playlist_mode, skip_long, limit,
#            split_chapters, ignore_dupes, title, status, queued_at}
download_queue = []


# Cancellation helpers.
# `cancel_requested` is a module-level bool. Because other modules imported it
# by value (`from settings import cancel_requested`), reassigning it in one
# module never reached the others and cancellation silently did nothing.
# Routing all access through these functions keeps a single source of truth.
def request_cancel():
    """Signal the active download to stop."""
    global cancel_requested
    cancel_requested = True


def reset_cancel():
    """Clear the cancel flag before starting a new download."""
    global cancel_requested
    cancel_requested = False


def is_cancel_requested():
    """Return True if the user has requested cancellation."""
    return cancel_requested

# Import JSON module for history persistence
import json

# Path to store download history
HISTORY_FILE = paths.data_file('download_history.json')

# Function to save history (limited to 100 entries)
def save_download_history():
    """Save download history to JSON file, keeping only the 100 most recent entries"""
    # Mutate in place (never rebind) so other modules' imported references stay valid.
    if len(download_history) > 100:
        download_history[:] = download_history[-100:]

    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(download_history, f, indent=2)
    except Exception as e:
        logger.error('Error saving download history: %s', e)

# Function to load history
def load_download_history():
    """Load download history from JSON file (in place, never rebind)"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                download_history[:] = json.load(f)
        except Exception as e:
            logger.error('Error loading download history: %s', e)
            download_history[:] = []
    else:
        download_history[:] = []

# Load history when this module is imported
load_download_history()


# ── Links history ────────────────────────────────────────────────────────────
# A running record of every link submitted for download, independent of the
# download-history above. Persisted so it survives restarts.
from datetime import datetime

links_history = []
LINKS_HISTORY_FILE = paths.data_file('links_history.json')


def save_links_history():
    """Persist links history to JSON, keeping the 500 most recent entries."""
    # Mutate in place (never rebind) so other modules' imported references stay valid.
    if len(links_history) > 500:
        links_history[:] = links_history[-500:]
    try:
        with open(LINKS_HISTORY_FILE, 'w') as f:
            json.dump(links_history, f, indent=2)
    except Exception as e:
        logger.error('Error saving links history: %s', e)


def load_links_history():
    """Load links history from JSON file (in place, never rebind)."""
    if os.path.exists(LINKS_HISTORY_FILE):
        try:
            with open(LINKS_HISTORY_FILE, 'r') as f:
                links_history[:] = json.load(f)
        except Exception as e:
            logger.error('Error loading links history: %s', e)
            links_history[:] = []
    else:
        links_history[:] = []


def add_link_history(url, download_type='audio', playlist_mode='single', title=None):
    """Record a submitted link at download time. Returns the created entry."""
    entry = {
        'url': url,
        'title': title or url,
        'download_type': download_type,
        'playlist_mode': playlist_mode,
        'status': 'started',
        'timestamp': datetime.now().isoformat(timespec='seconds'),
    }
    links_history.append(entry)
    save_links_history()
    return entry


def update_last_link_history(title=None, status=None):
    """Enrich the most recent link entry once the title/result is known."""
    if not links_history:
        return
    entry = links_history[-1]
    if title:
        entry['title'] = title
    if status:
        entry['status'] = status
    save_links_history()


# Load links history when this module is imported
load_links_history()
