#!/usr/bin/env python3
# modules/config/user_settings.py
# User-editable settings that drive the text-control operations across the app
# (filler words to remove, character replacements). Persisted to app_settings.json
# in the app data directory (see modules/config/paths.py).

import os
import json
import logging

from modules.config import paths

logger = logging.getLogger('lmd.user_settings')

# Default filler words removed by the "Remove filler words" operation and used when
# normalizing titles for duplicate detection. Users can add/remove these on the
# Settings page; their saved list overrides these defaults.
DEFAULT_FILLER_WORDS = {
    'music', 'mix', 'remaster', 'remastered', 'live', '4k', '8k', 'hd', 'uhd',
    'hq', 'original', 'remix', 'cover', 'official', 'video', 'audio', 'visualizer',
    'lyric', 'lyrics', 'full', 'album', 'version', 'feat', 'ft', 'explicit',
    'clean', 'mv', 'edit', 'extended', 'radio',
    # soundtrack / anime / release qualifiers
    'ost', 'soundtrack', 'score', 'theme', 'ova', 'ona', 'amv', 'pv', 'op', 'ed',
    'animated', 'animation', 'anime',
    'instrumental', 'inst', 'nightcore', 'sped', 'slowed', 'reverb', '8d',
    'bonus', 'deluxe', 'remux', 'bluray', 'bd', 'dvd', 'hdr',
    '1080p', '720p', '480p', '2160p',
    # months (full + abbreviations)
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
    'september', 'october', 'november', 'december',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec',
}

SETTINGS_FILE = paths.data_file('app_settings.json')

_settings = None   # lazy-loaded cache


def _defaults():
    return {
        'filler_words': sorted(DEFAULT_FILLER_WORDS),
        # each replacement: {"from": "x", "to": "y"} applied to file base names
        'char_replacements': [],
    }


def load_settings():
    global _settings
    data = _defaults()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            if isinstance(saved.get('filler_words'), list):
                data['filler_words'] = saved['filler_words']
            if isinstance(saved.get('char_replacements'), list):
                data['char_replacements'] = saved['char_replacements']
        except Exception as e:
            logger.error('Error loading app settings: %s', e)
    _settings = data
    return _settings


def get_settings():
    return _settings if _settings is not None else load_settings()


def save_settings(new_settings):
    """Persist a full settings dict (validated/normalized)."""
    global _settings
    data = _defaults()
    fw = new_settings.get('filler_words')
    if isinstance(fw, list):
        data['filler_words'] = sorted({str(w).strip().lower() for w in fw if str(w).strip()})
    cr = new_settings.get('char_replacements')
    if isinstance(cr, list):
        clean = []
        for r in cr:
            frm = str((r or {}).get('from', ''))
            to = str((r or {}).get('to', ''))
            if frm:
                clean.append({'from': frm, 'to': to})
        data['char_replacements'] = clean
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error('Error saving app settings: %s', e)
    _settings = data
    return _settings


def get_filler_words():
    """Effective set of filler words (user's saved list, or the defaults)."""
    return set(get_settings().get('filler_words') or DEFAULT_FILLER_WORDS)


def get_char_replacements():
    """List of (from, to) character/string replacements."""
    return [(r['from'], r.get('to', '')) for r in get_settings().get('char_replacements', [])
            if r.get('from')]
