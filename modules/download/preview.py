#!/usr/bin/env python3
# modules/download/preview.py
# Read a link before downloading: what it is, every entry with its length, and which
# entries the current options would skip (same rules as the download's match filter),
# so the Download page can show the result before anything is fetched.

import logging
import re

import yt_dlp

from modules.config.logging_config import YTDLPLogger
from modules.config.settings import LONG_SECONDS
from modules.download import dedupe

logger = logging.getLogger('lmd.preview')

# yt-dlp error text -> a kind the UI can explain in plain words (most specific first)
_ERROR_KINDS = (
    ('bot_check', re.compile(r'confirm you.?re not a bot|sign in to confirm', re.I)),
    ('rate_limited', re.compile(r'HTTP Error 429|too many requests', re.I)),
    ('unavailable', re.compile(r'video unavailable|private video|has been removed|members-only'
                               r'|not available in your country|does not exist', re.I)),
    ('unsupported', re.compile(r'unsupported url|is not a valid url', re.I)),
    ('network', re.compile(r'unable to download webpage|getaddrinfo|name or service not known'
                           r'|timed out|connection (refused|reset)|network is unreachable', re.I)),
)


def classify_error(message):
    """One of bot_check, rate_limited, unavailable, unsupported, network, unknown"""
    for kind, pattern in _ERROR_KINDS:
        if pattern.search(message or ''):
            return kind
    return 'unknown'


def _extract(url):
    """Flat extraction: titles, ids and lengths without downloading or resolving formats"""
    opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'logger': YTDLPLogger(logging.getLogger('lmd.ytdlp.preview')),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _playlist_url(url):
    """The playlist behind a watch?v=…&list=… link, or None"""
    m = re.search(r'[?&]list=([\w-]+)', url or '')
    if not m or not ('youtube.com' in url or 'youtu.be' in url):
        return None
    return 'https://www.youtube.com/playlist?list=' + m.group(1)


def _entry(index, item, skip_long, ignore_dupes):
    item = item or {}
    duration = item.get('duration')
    skip = None
    if skip_long and duration is not None and duration > LONG_SECONDS:
        skip = 'long'
    elif ignore_dupes and dedupe.is_duplicate(item):
        skip = 'duplicate'
    return {
        'index': index,
        'id': item.get('id') or '',
        'title': item.get('title') or item.get('url') or f'Item {index}',
        'duration': duration,
        'url': item.get('url') or item.get('webpage_url') or '',
        'skip': skip,
    }


def preview_link(url, skip_long=False, ignore_dupes=False):
    """Describe a link: {'kind': 'video'|'playlist', 'title', 'entries': [...], 'error'}.

    A watch link that also names a playlist is read as the playlist, with
    'video_title' set, so the page can offer "This video" or the whole list.
    On failure 'error' is {'kind': classify_error(...), 'detail': yt-dlp's text}.
    """
    result = {'url': url, 'kind': 'video', 'title': '', 'video_title': '', 'entries': [], 'error': None}
    try:
        info = _extract(url)
        list_url = None if info.get('_type') == 'playlist' else _playlist_url(url)
        if list_url:
            try:
                listing = _extract(list_url)
                if listing.get('_type') == 'playlist':
                    result['video_title'] = info.get('title') or ''
                    result['playlist_url'] = list_url
                    info = listing
            except Exception as e:  # the video alone is still downloadable
                logger.info('Playlist behind %s could not be read: %s', url, e)
        if info.get('_type') == 'playlist':
            result['kind'] = 'playlist'
            result['title'] = info.get('title') or 'Playlist'
            items = [e for e in (info.get('entries') or []) if e]
        else:
            result['title'] = info.get('title') or 'Video'
            items = [info]
        result['entries'] = [_entry(i, e, skip_long, ignore_dupes) for i, e in enumerate(items, 1)]
    except Exception as e:
        detail = str(e)
        result['error'] = {'kind': classify_error(detail), 'detail': detail}
        logger.warning('Could not read %s: %s', url, detail)
    return result


def apply_options(preview, skip_long=False, ignore_dupes=False):
    """Re-mark which entries would be skipped after an option changes (no network)"""
    for e in preview.get('entries') or []:
        e['skip'] = _entry(e['index'], e, skip_long, ignore_dupes)['skip']
    return preview


def summarize(preview):
    """Counts the page shows: total, to download, skipped by reason, total seconds"""
    entries = preview.get('entries') or []
    return {
        'count': len(entries),
        'to_download': sum(1 for e in entries if not e['skip']),
        'skipped_long': sum(1 for e in entries if e['skip'] == 'long'),
        'skipped_duplicate': sum(1 for e in entries if e['skip'] == 'duplicate'),
        'seconds': sum(e['duration'] or 0 for e in entries),
    }
