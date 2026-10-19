#!/usr/bin/env python3
# modules/tools.py
# The two outside tools the app depends on, as the Settings page shows them: yt-dlp
# (updated only when the user asks) and ffmpeg (from the system) — plus the
# diagnostics bundle for bug reports.

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime

from modules.config import paths

logger = logging.getLogger('lmd.tools')


def ytdlp_version():
    """yt-dlp's version, or None when it is missing"""
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:
        return None


def ffmpeg_version():
    """'7.0.2-static' style version and path, or (None, None) when ffmpeg is missing"""
    path = shutil.which('ffmpeg')
    if not path:
        return None, None
    try:
        first = subprocess.run([path, '-version'], capture_output=True, text=True, timeout=10).stdout.split('\n')[0]
        return (first.split()[2] if len(first.split()) > 2 else first), path
    except Exception:
        return 'unknown', path


def can_update_ytdlp():
    """yt-dlp lives in the app's own venv (not a system package) and this user may write
    there: the .deb's venv in /opt belongs to root, so it is updated with the package"""
    if sys.prefix == getattr(sys, 'base_prefix', sys.prefix):
        return False
    return os.access(sys.prefix, os.W_OK)


def update_ytdlp():
    """pip-install the newest yt-dlp (with its local challenge solver) into the app's venv.

    Runs only when the user presses "Update yt-dlp" (no silent updates). Returns
    {'ok', 'before', 'after', 'output'}; the new version is used from the next
    download that starts after a restart of the app.
    """
    before = ytdlp_version()
    if not can_update_ytdlp():
        return {'ok': False, 'before': before, 'after': before,
                'output': 'yt-dlp here belongs to a system package or to all users; update it with your package manager.'}
    cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', '--disable-pip-version-check', 'yt-dlp[default]']
    logger.info('Updating yt-dlp: %s', ' '.join(cmd))
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        out = (run.stdout + run.stderr)[-4000:]
        after = subprocess.run([sys.executable, '-c', 'import yt_dlp; print(yt_dlp.version.__version__)'],
                               capture_output=True, text=True, timeout=60).stdout.strip() or before
        ok = run.returncode == 0
    except Exception as e:
        out, after, ok = str(e), before, False
    logger.info('yt-dlp update %s: %s -> %s', 'done' if ok else 'failed', before, after)
    return {'ok': ok, 'before': before, 'after': after, 'output': out}


def save_diagnostics(target_path):
    """A zip for a bug report: the logs, versions and settings. Never cookies or history.

    Returns the path written.
    """
    from modules.config import user_settings
    from modules.download import access

    info = {
        'created': datetime.now().isoformat(timespec='seconds'),
        'python': platform.python_version(),
        'platform': platform.platform(),
        'yt_dlp': ytdlp_version(),
        'ffmpeg': ffmpeg_version()[0],
        'sign_in': access.current().describe(),  # browser name and runtime only
        'settings': {k: v for k, v in user_settings.get_settings().items() if k != 'filler_words'},
        'data_dir': paths.DATA_DIR,
    }
    with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('environment.json', json.dumps(info, indent=2))
        for name in sorted(os.listdir(paths.LOG_DIR)) if os.path.isdir(paths.LOG_DIR) else []:
            if name.startswith('app.log'):
                z.write(os.path.join(paths.LOG_DIR, name), os.path.join('logs', name))
    logger.info('Saved diagnostics to %s', target_path)
    return target_path
