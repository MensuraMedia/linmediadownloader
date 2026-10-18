#!/usr/bin/env python3
# modules/download/jobs.py
# Front-end-neutral download commands and state snapshots.
#
# The Flask routes (1.x UI) and the GTK window (2.0) both call these, so neither
# owns download logic. Snapshots return plain copies: a UI thread can read them
# while the worker thread keeps mutating the shared state in settings.py.

import logging
from datetime import datetime

from modules.config import settings
from modules.config.settings import current_download, download_queue, request_cancel
from modules.download import preview
from modules.download.media import enqueue_download

logger = logging.getLogger('lmd.jobs')

VIDEO_QUALITIES = ('480', '720', '1080')
DEFAULT_VIDEO_QUALITY = '1080'

_QUEUE_FIELDS = ('id', 'url', 'title', 'status', 'download_type', 'playlist_mode', 'queued_at')
_UNFINISHED = ('queued', 'active')


def normalize_options(data):
    """Validated download options from a loosely typed dict (JSON body, UI state)."""
    data = data or {}
    quality = str(data.get('video_quality', DEFAULT_VIDEO_QUALITY))
    if quality not in VIDEO_QUALITIES:
        quality = DEFAULT_VIDEO_QUALITY
    try:
        limit = int(data.get('limit', 0) or 0)
    except (TypeError, ValueError):
        limit = 0
    return {
        'output_dir': data.get('output_dir') or settings.default_download_path,
        'download_type': data.get('download_type', 'audio'),
        'playlist_mode': data.get('playlist_mode', 'single'),
        'skip_long': bool(data.get('skip_long', False)),
        'limit': limit,
        'split_chapters': bool(data.get('split_chapters', False)),
        'ignore_dupes': bool(data.get('ignore_dupes', False)),
        'video_quality': quality,
    }


def submit_download(url, options=None):
    """Record the link, queue the job and start it if nothing is running.

    Returns {'status': 'started', 'job_id'} or {'status': 'queued', 'job_id',
    'position'} (position among jobs still waiting, 1-based).
    """
    url = preview.strip_mix(url)  # a Mix is one video plus endless suggestions
    opts = normalize_options(options)
    # Title is filled in later, once the worker resolves it.
    settings.add_link_history(url, opts['download_type'], opts['playlist_mode'])
    job = enqueue_download(url, opts['output_dir'], opts['download_type'], opts['playlist_mode'],
                           opts['skip_long'], opts['limit'], opts['split_chapters'],
                           opts['ignore_dupes'], video_quality=opts['video_quality'])
    if job.get('status') == 'active':
        return {'status': 'started', 'job_id': job['id']}
    position = sum(1 for j in download_queue if j.get('status') == 'queued' and j['id'] <= job['id'])
    return {'status': 'queued', 'job_id': job['id'], 'position': position}


def cancel_active_download():
    """Stop the running download and record what it got so far in history."""
    request_cancel()
    current_download['status'] = 'cancelled'
    current_download['message'] = 'Download cancelled by user'

    title = current_download.get('playlist_title') or current_download.get('current_file')
    if not title:
        return
    settings.download_history.append({
        'url': '',  # not known here
        'output_dir': current_download.get('output_path', ''),
        'download_type': current_download.get('selected_mode', 'unknown'),
        'is_playlist': current_download.get('is_playlist', False),
        'title': title,
        'status': 'completed_with_errors',  # shown as "Partial"
        'timestamp': datetime.now().isoformat(timespec='seconds'),
    })
    settings.save_download_history()


def status_snapshot():
    """Copy of the current download state plus how many jobs are still waiting."""
    data = dict(current_download)
    data['queue_pending'] = sum(1 for j in download_queue if j.get('status') == 'queued')
    return data


def queue_snapshot():
    """Queued, active and finished jobs, oldest first."""
    return [{k: j.get(k) for k in _QUEUE_FIELDS} for j in list(download_queue)]


def remove_queued(job_id):
    """Drop one waiting job from the queue. Only status 'queued' can be removed
    (an active download is stopped through cancel_active_download, not here).
    Returns True when the job was removed."""
    for job in download_queue:
        if job.get('id') == job_id and job.get('status') == 'queued':
            download_queue.remove(job)
            return True
    return False


def clear_finished_jobs():
    """Drop finished, failed and cancelled jobs from the queue. Returns how many remain."""
    download_queue[:] = [j for j in download_queue if j.get('status') in _UNFINISHED]
    return len(download_queue)
