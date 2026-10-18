#!/usr/bin/env python3
# modules/download/dedupe.py
# "Ignore Duplicates": skip tracks already downloaded, matched against a manifest
# of ORIGINAL (pre-rename) titles + video ids. See docs/concept-ignore-duplicates.md.

import os
import re
import json
import difflib
import logging

from modules.config import paths, user_settings

logger = logging.getLogger('lmd.dedupe')

# Words dropped during normalization (in addition to FILLER_WORDS + years)
STOPWORDS = {
    'the', 'a', 'an', 'of', 'my', 'your', 'this', 'that', 'to', 'and', 'or',
    'in', 'on', 'for', 'with', 'is', 'it', 'by', 'at', 'from',
}

SIMILARITY_THRESHOLD = 0.80          # ≥ this token/string similarity ⇒ duplicate
MANIFEST_FILE = paths.data_file('download_manifest.json')
MANIFEST_MAX = 5000

_manifest = []   # [{'id':.., 'title':.., 'tokens':[...], 'timestamp':..}]


def _tokens(title):
    """Normalize a title to an order-independent set of meaningful tokens."""
    words = re.split(r'[^0-9a-z]+', (title or '').lower())
    filler = user_settings.get_filler_words()
    out = set()
    for w in words:
        if not w or w in STOPWORDS or w in filler:
            continue
        if re.fullmatch(r'(?:19|20)\d{2}', w):   # a year
            continue
        out.add(w)
    return out


def _norm_str(title):
    return ' '.join(sorted(_tokens(title)))


def similarity(title_a, tokens_b, norm_b):
    """Max of token-set Dice and difflib ratio between a title and a manifest entry."""
    a = _tokens(title_a)
    b = set(tokens_b or [])
    if a and b:
        inter = len(a & b)
        dice = 2 * inter / (len(a) + len(b))
        if a == b:
            return 1.0
    else:
        dice = 0.0
    seq = difflib.SequenceMatcher(None, _norm_str(title_a), norm_b or '').ratio()
    # Require ≥2 tokens on each side for a fuzzy (non-exact) match to avoid
    # single generic-word false positives.
    score = max(dice, seq)
    if score < 1.0 and (len(a) < 2 or len(b) < 2):
        return 0.0
    return score


# ── manifest persistence ──────────────────────────────────────────────────────
def load_manifest():
    global _manifest
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE) as f:
                data = json.load(f)
                _manifest = data if isinstance(data, list) else []
        except Exception:
            _manifest = []
    else:
        _manifest = []
    return _manifest


def save_manifest():
    if len(_manifest) > MANIFEST_MAX:
        _manifest[:] = _manifest[-MANIFEST_MAX:]
    try:
        os.makedirs(os.path.dirname(MANIFEST_FILE), exist_ok=True)
        with open(MANIFEST_FILE, 'w') as f:
            json.dump(_manifest, f, indent=2)
    except Exception as e:
        logger.error('Error saving download manifest: %s', e)


def record_download(info_dict, timestamp=None):
    """Record a downloaded item by its ORIGINAL title + video id (call before rename)."""
    # _manifest is mutated in place (append) — no `global` needed.
    info_dict = info_dict or {}
    vid = info_dict.get('id')
    title = info_dict.get('title') or ''
    if not title and not vid:
        return
    if vid and any(e.get('id') == vid for e in _manifest):
        return                      # already recorded
    _manifest.append({
        'id': vid,
        'title': title,
        'tokens': sorted(_tokens(title)),
        'timestamp': timestamp,
    })
    save_manifest()


def is_duplicate(info_dict, threshold=SIMILARITY_THRESHOLD):
    """True if this item matches something already in the manifest."""
    info_dict = info_dict or {}
    vid = info_dict.get('id')
    title = info_dict.get('title') or ''
    for e in _manifest:
        if vid and e.get('id') and e['id'] == vid:
            return True             # exact source identity
    if not title:
        return False
    for e in _manifest:
        if similarity(title, e.get('tokens'), _norm_str(e.get('title', ''))) >= threshold:
            return True
    return False


# Load on import
load_manifest()
